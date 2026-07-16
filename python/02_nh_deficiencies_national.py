"""
02_nh_deficiencies_national.py
NH Health and Fire Safety Deficiencies -- national citation-level dataset.

Sources: CMS Provider Data -- Nursing Home Care Compare
  Health Deficiencies   r5ix-sfxw  dist: 327a1777-6c39-5872-9874-c18728c3c104
  Fire Safety Deficiencies ifjz-ge4w dist: 490c3ffa-b0c6-5dd1-9ca6-ed1d8cc84bdc
  Both: state filter = "state"

One row per citation per survey per facility.

Joins:
  reference_ftag_citations.csv (F/K/E prefix + tag_number --> description, category)
  facility_master_national.csv (ccn --> facility identity and geography)

Adds:
  severity_level    1-4 integer (1=No Harm Min, 2=No Harm >Min, 3=Actual Harm, 4=IJ)
  scope             Isolated / Pattern / Widespread
  severity_desc     human-readable severity description
  is_immediate_jeopardy   True if scope_severity in J/K/L (severity_level == 4)
  is_actual_harm          True if severity_level >= 3
  is_abuse_neglect        True if category == 'Freedom from Abuse, Neglect, and Exploitation...'
  is_infection_control    True if category == 'Infection Control Deficiencies'
  is_resident_rights      True if category == 'Resident Rights Deficiencies'

Caching:
  Raw API results cached to output_reference/cache/*.csv.gz (8-day TTL)
  Re-run reuses cache; pass --refresh to force re-fetch

Outputs:
  output_reference/nh_health_deficiencies_national.csv
  output_reference/nh_fire_deficiencies_national.csv

Pre-registered assertions:
  Health total:   [350,000 -- 800,000]  (estimate: ~35 deficiences x 14,695 facilities x 1.2 surveys)
  Health HI:      [1,300 -- 1,700]
  Fire total:     [100,000 -- 300,000]
  Fire HI:        [170 -- 240]
  HI IJ count:    [0 -- 50]   (immediate jeopardy is rare)
  Abuse/neglect tags in HI: any
"""

import datetime, gzip, json, pathlib, sys, time, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
CACHE_DIR  = OUTPUT_DIR / "cache"

OUTPUT_HEALTH = OUTPUT_DIR / "nh_health_deficiencies_national.csv"
OUTPUT_FIRE   = OUTPUT_DIR / "nh_fire_deficiencies_national.csv"
FTAG_FILE     = OUTPUT_DIR / "reference_ftag_citations.csv"

CACHE_HEALTH       = CACHE_DIR / "nh_health_deficiencies_raw.csv.gz"
CACHE_FIRE         = CACHE_DIR / "nh_fire_deficiencies_raw.csv.gz"
CHECKPOINT_HEALTH  = CACHE_DIR / "nh_health_deficiencies_checkpoint.csv.gz"
CHECKPOINT_FIRE    = CACHE_DIR / "nh_fire_deficiencies_checkpoint.csv.gz"
CACHE_MAX_DAYS     = 8
CHECKPOINT_INTERVAL = 100   # save checkpoint every N pages

HEALTH_DIST = "327a1777-6c39-5872-9874-c18728c3c104"
FIRE_DIST   = "490c3ffa-b0c6-5dd1-9ca6-ed1d8cc84bdc"
BASE_URL    = "https://data.cms.gov/provider-data/api/1/datastore/query/{dist_id}"
PAGE_SIZE   = 1_000

FORCE_REFRESH = "--refresh" in sys.argv

# CMS scope/severity grid (A-L)
SCOPE_SEVERITY = {
    "A": (1, "Isolated",    "No Actual Harm - Minimal Potential"),
    "B": (1, "Pattern",     "No Actual Harm - Minimal Potential"),
    "C": (1, "Widespread",  "No Actual Harm - Minimal Potential"),
    "D": (2, "Isolated",    "No Actual Harm - Potential > Minimal"),
    "E": (2, "Pattern",     "No Actual Harm - Potential > Minimal"),
    "F": (2, "Widespread",  "No Actual Harm - Potential > Minimal"),
    "G": (3, "Isolated",    "Actual Harm"),
    "H": (3, "Pattern",     "Actual Harm"),
    "I": (3, "Widespread",  "Actual Harm"),
    "J": (4, "Isolated",    "Immediate Jeopardy"),
    "K": (4, "Pattern",     "Immediate Jeopardy"),
    "L": (4, "Widespread",  "Immediate Jeopardy"),
}


# ── Fetch / Cache ──────────────────────────────────────────────────────────────

def cache_valid(path: pathlib.Path) -> bool:
    if FORCE_REFRESH or not path.exists():
        return False
    age = datetime.datetime.now() - datetime.datetime.fromtimestamp(path.stat().st_mtime)
    return age.days < CACHE_MAX_DAYS


def fetch_page_with_retry(url: str, payload: bytes, max_retries: int = 6) -> dict:
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = min(10 * (2 ** attempt), 120)
                print(f"    HTTP {e.code} (attempt {attempt+1}/{max_retries}); retry in {wait}s ...")
                time.sleep(wait)
            else:
                raise
        except (urllib.error.URLError, OSError) as e:
            if attempt < max_retries - 1:
                wait = min(10 * (2 ** attempt), 120)
                print(f"    Network error (attempt {attempt+1}/{max_retries}); retry in {wait}s ...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("fetch_page_with_retry exhausted retries")


def fetch_all_pages(dist_id: str, label: str,
                    checkpoint_path: pathlib.Path | None = None) -> list:
    url = BASE_URL.format(dist_id=dist_id)

    # Resume from checkpoint if available
    all_rows: list = []
    if checkpoint_path and checkpoint_path.exists() and not FORCE_REFRESH:
        cp_df = pd.read_csv(checkpoint_path, compression="gzip", dtype=str).fillna("")
        all_rows = cp_df.to_dict("records")
        print(f"  {label}: resuming from checkpoint ({len(all_rows):,} rows already fetched)")

    start_offset = len(all_rows)

    # Probe total count
    probe = fetch_page_with_retry(url, json.dumps({"limit": 1, "offset": 0}).encode())
    total_count = probe.get("count", "?")
    count_str = f"{total_count:,}" if isinstance(total_count, int) else str(total_count)
    print(f"  {label}: reported count = {count_str}  starting offset = {start_offset:,}")

    offset = start_offset
    page = start_offset // PAGE_SIZE

    while True:
        page += 1
        payload = json.dumps({"limit": PAGE_SIZE, "offset": offset}).encode()
        data = fetch_page_with_retry(url, payload)
        rows = data.get("results", [])
        if not rows:
            break
        all_rows.extend(rows)

        if page % CHECKPOINT_INTERVAL == 0:
            if checkpoint_path:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(all_rows).to_csv(checkpoint_path, index=False, compression="gzip")
            print(f"    page {page:4}  offset={offset:7,}  total={len(all_rows):,}  [checkpoint saved]")
        elif page % 50 == 0 or len(rows) < PAGE_SIZE:
            print(f"    page {page:4}  offset={offset:7,}  total={len(all_rows):,}")

        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(1.0)   # 1s between pages -- reduce server load

    print(f"  {label}: fetched {len(all_rows):,} rows total")
    return all_rows


def load_or_fetch(cache_path: pathlib.Path, checkpoint_path: pathlib.Path,
                  dist_id: str, label: str) -> pd.DataFrame:
    if cache_valid(cache_path):
        print(f"  {label}: loading from cache ({cache_path.name})")
        return pd.read_csv(cache_path, compression="gzip", dtype=str).fillna("")
    print(f"  {label}: fetching from API ...")
    rows = fetch_all_pages(dist_id, label, checkpoint_path)
    df = pd.DataFrame(rows).fillna("")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False, compression="gzip")
    # Delete checkpoint after successful full cache write
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        print(f"  {label}: checkpoint removed (full cache written)")
    print(f"  {label}: cached to {cache_path.name}")
    return df


# ── Load F-tag reference ───────────────────────────────────────────────────────

if not FTAG_FILE.exists():
    sys.exit(f"F-tag reference not found: {FTAG_FILE}\n"
             "Run reference_ftag_citations.py first.")

ftag = pd.read_csv(FTAG_FILE, dtype=str).fillna("")
# Build lookup: (prefix, tag_number) -> (description, category)
ftag_lookup = {
    (r["tag_prefix"].strip().upper(), r["tag_number"].strip()): {
        "ftag_description": r["description"],
        "ftag_category":    r["category"],
    }
    for _, r in ftag.iterrows()
}
print(f"F-tag reference loaded: {len(ftag_lookup):,} codes")
print()


# ── Column discovery ───────────────────────────────────────────────────────────

def find_col(cols, *substrings, exclude=None):
    for c in cols:
        if all(s.lower() in c.lower() for s in substrings):
            if exclude and any(e.lower() in c.lower() for e in exclude):
                continue
            return c
    return None


def map_deficiency_cols(raw_cols: list) -> dict:
    return {
        "ccn":           find_col(raw_cols, "cms_certification_number") or find_col(raw_cols, "ccn"),
        "name":          find_col(raw_cols, "provider_name"),
        "state":         find_col(raw_cols, "state"),
        "city":          find_col(raw_cols, "city"),
        "zip":           find_col(raw_cols, "zip"),
        "survey_date":   find_col(raw_cols, "survey_date") or find_col(raw_cols, "inspection_date"),
        "prefix":        find_col(raw_cols, "deficiency_prefix"),
        "category":      find_col(raw_cols, "deficiency_category"),
        "tag_number":    find_col(raw_cols, "deficiency_tag_number") or find_col(raw_cols, "tag_number"),
        "tag_desc":      find_col(raw_cols, "deficiency_description") or find_col(raw_cols, "short_description"),
        "scope_sev":     find_col(raw_cols, "scope_severity"),
        "corrected":     find_col(raw_cols, "corrected"),
        "is_standard":   find_col(raw_cols, "standard"),
        "is_complaint":  find_col(raw_cols, "complaint"),
        "is_ic":         find_col(raw_cols, "infection_control"),
    }


# ── Transform ──────────────────────────────────────────────────────────────────

def transform(df_raw: pd.DataFrame, source_label: str) -> pd.DataFrame:
    raw_cols = list(df_raw.columns)
    COL = map_deficiency_cols(raw_cols)

    print(f"\n  {source_label} column mapping:")
    for k, v in COL.items():
        status = v or "NOT FOUND"
        print(f"    {k:<16} {status}")

    def g(row, key):
        col = COL.get(key)
        return str(row.get(col, "")).strip() if col else ""

    out = []
    for _, r in df_raw.iterrows():
        row = r.to_dict()
        prefix    = g(row, "prefix").upper()
        tag_num   = g(row, "tag_number")
        scope_sev = g(row, "scope_sev").upper()

        sev_info  = SCOPE_SEVERITY.get(scope_sev, (None, "", ""))
        sev_level, scope_label, sev_desc = sev_info

        ftag_info = ftag_lookup.get((prefix, tag_num), {
            "ftag_description": g(row, "tag_desc"),
            "ftag_category":    g(row, "category"),
        })
        category = ftag_info["ftag_category"]

        out.append({
            "ccn":                     g(row, "ccn"),
            "provider_name":           g(row, "name"),
            "state":                   g(row, "state"),
            "city":                    g(row, "city"),
            "zip":                     g(row, "zip"),
            "survey_date":             g(row, "survey_date"),
            "tag_prefix":              prefix,
            "tag_number":              tag_num,
            "prefix_tag":              f"{prefix}-{tag_num}" if prefix and tag_num else "",
            "tag_description":         ftag_info["ftag_description"],
            "category":                category,
            "scope_severity_code":     scope_sev,
            "severity_level":          "" if sev_level is None else sev_level,
            "scope":                   scope_label,
            "severity_desc":           sev_desc,
            "deficiency_corrected":    g(row, "corrected"),
            "is_standard":             g(row, "is_standard"),
            "is_complaint":            g(row, "is_complaint"),
            "is_infection_control":    g(row, "is_ic"),
            # Priority flags
            "is_immediate_jeopardy":   str(scope_sev in ("J", "K", "L")),
            "is_actual_harm":          str(sev_level is not None and sev_level >= 3),
            "is_abuse_neglect":        str("abuse" in category.lower() or "neglect" in category.lower()),
            "is_infection_ctrl_cat":   str("infection control" in category.lower()),
            "is_resident_rights":      str("resident rights" in category.lower()),
            "is_quality_care":         str("quality of life" in category.lower()),
        })

    return pd.DataFrame(out)


# ── Main ───────────────────────────────────────────────────────────────────────

print("=" * 70)
print("NH Health Deficiencies -- national")
print("=" * 70)
df_health_raw = load_or_fetch(CACHE_HEALTH, CHECKPOINT_HEALTH, HEALTH_DIST, "Health Deficiencies")
df_health = transform(df_health_raw, "Health Deficiencies")

print()
print("=" * 70)
print("NH Fire Safety Deficiencies -- national")
print("=" * 70)
df_fire_raw = load_or_fetch(CACHE_FIRE, CHECKPOINT_FIRE, FIRE_DIST, "Fire Safety Deficiencies")
df_fire = transform(df_fire_raw, "Fire Safety Deficiencies")


# ── Assertions ─────────────────────────────────────────────────────────────────

print()
print("Assertions ...")

def assert_range(name, value, lo, hi):
    if not (lo <= value <= hi):
        raise AssertionError(f"FAILED: {name} = {value:,} outside [{lo:,}, {hi:,}]")
    print(f"  PASS: {name} = {value:,}")

h_total = len(df_health)
h_hi    = len(df_health[df_health["state"] == "HI"])
f_total = len(df_fire)
f_hi    = len(df_fire[df_fire["state"] == "HI"])
h_ij_hi = len(df_health[(df_health["state"] == "HI") & (df_health["is_immediate_jeopardy"] == "True")])

assert_range("Health deficiencies total",  h_total, 350_000, 800_000)
assert_range("Health deficiencies HI",     h_hi,    1_300,   1_700)
assert_range("Fire deficiencies total",    f_total, 100_000, 300_000)
assert_range("Fire deficiencies HI",       f_hi,    170,     240)
assert_range("HI immediate jeopardy (H)",  h_ij_hi, 0,       50)


# ── Summary ────────────────────────────────────────────────────────────────────

print()
print("Health deficiency summary (national):")
ij_n  = (df_health["is_immediate_jeopardy"] == "True").sum()
ah_n  = (df_health["is_actual_harm"] == "True").sum()
ab_n  = (df_health["is_abuse_neglect"] == "True").sum()
ic_n  = (df_health["is_infection_ctrl_cat"] == "True").sum()
print(f"  Immediate jeopardy (J/K/L):  {ij_n:6,} ({ij_n/h_total*100:.2f}%)")
print(f"  Actual harm (G/H/I+):        {ah_n:6,} ({ah_n/h_total*100:.2f}%)")
print(f"  Abuse/neglect citations:      {ab_n:6,}")
print(f"  Infection control citations:  {ic_n:6,}")

print()
print("Top 10 categories (health, national):")
top_cats = df_health["category"].value_counts().head(10)
for cat, cnt in top_cats.items():
    print(f"  {str(cat):<55} {cnt:6,}")

print()
print("Hawaii health deficiencies by severity:")
for sev, grp in df_health[df_health["state"] == "HI"].groupby("severity_desc"):
    print(f"  {str(sev):<45} {len(grp):4}")

print()
print(f"Hawaii facilities with immediate jeopardy: {h_ij_hi}")
if h_ij_hi > 0:
    ij_hi = df_health[(df_health["state"] == "HI") & (df_health["is_immediate_jeopardy"] == "True")]
    print(ij_hi[["ccn", "provider_name", "survey_date", "prefix_tag",
                  "tag_description", "scope_severity_code"]].to_string(index=False))

print()
print("Hawaii abuse/neglect deficiencies:")
ab_hi = df_health[(df_health["state"] == "HI") & (df_health["is_abuse_neglect"] == "True")]
if len(ab_hi) == 0:
    print("  None found")
else:
    print(ab_hi[["ccn", "provider_name", "survey_date", "prefix_tag",
                  "scope_severity_code", "severity_desc"]].to_string(index=False))


# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df_health.to_csv(OUTPUT_HEALTH, index=False)
df_fire.to_csv(OUTPUT_FIRE, index=False)

print()
print(f"Health deficiencies: {OUTPUT_HEALTH}")
print(f"  Rows: {len(df_health):,}  Cols: {len(df_health.columns)}")
print(f"Fire deficiencies:   {OUTPUT_FIRE}")
print(f"  Rows: {len(df_fire):,}  Cols: {len(df_fire.columns)}")
print()
print("Join keys:")
print("  ccn          -->  facility_master_national.csv")
print("  ccn          -->  nh_provider_info_national.csv (Five-Star context)")
print("  prefix_tag   -->  reference_ftag_citations.csv (already merged)")
