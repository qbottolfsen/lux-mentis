"""
04_nh_quality_measures_national.py
NH Quality Measures -- national MDS, Claims-based, and QRP combined.

Sources: CMS Provider Data -- Nursing Home Care Compare
  MDS QM:    djen-97ju  dist: ebd11612-e160-581b-bd87-79db44cc43cd
  Claims QM: ijh5-nb2v  dist: dc0b509a-d96c-5eeb-b71b-9679ee42847f
  QRP:       fykj-qjee  dist: df617e1b-0840-535e-b24f-0d04a7ff05a4

Reference:
  reference_measure_intervals.csv  (measure_code --> collection period)

Three separate output files (different column schemas per source):
  output_reference/nh_mds_qm_national.csv        (17 measures x facility, Q1-Q4 scores)
  output_reference/nh_claims_qm_national.csv      (4 risk-adjusted measures x facility)
  output_reference/nh_qrp_national.csv            (57 QRP measures x facility; not all facilities)

Caching: raw API results cached to output_reference/cache/*.csv.gz (8-day TTL)
         Pass --refresh to force re-fetch.

Pre-registered assertions:
  MDS QM total:     [150,000 -- 400,000]  (est: 17 measures x ~14,000 facilities)
  MDS QM HI:        [650 -- 800]           (42 facilities x 17 measures = 714 expected)
  Claims QM total:  [30,000 -- 100,000]
  Claims QM HI:     [150 -- 200]           (42 facilities x 4 measures = 168 expected)
  QRP total:        [200,000 -- 900,000]   (57 measures x ~14,000+ facilities)
  QRP HI:           [2,000 -- 2,600]       (42 CCNs x 57 measures = 2,394 confirmed)
"""

import datetime, json, pathlib, sys, time, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")
try:
    import pyarrow  # noqa: F401
except ImportError:
    sys.exit("pyarrow required: pip install pyarrow")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
CACHE_DIR  = OUTPUT_DIR / "cache"

OUTPUT_MDS    = OUTPUT_DIR / "nh_mds_qm_national.parquet"
OUTPUT_CLAIMS = OUTPUT_DIR / "nh_claims_qm_national.parquet"
OUTPUT_QRP    = OUTPUT_DIR / "nh_qrp_national.parquet"

MEASURE_INTERVALS_FILE = OUTPUT_DIR / "reference_measure_intervals.csv"

DATASETS = {
    "mds_qm":    ("ebd11612-e160-581b-bd87-79db44cc43cd", CACHE_DIR / "nh_mds_qm_raw.csv.gz"),
    "claims_qm": ("dc0b509a-d96c-5eeb-b71b-9679ee42847f", CACHE_DIR / "nh_claims_qm_raw.csv.gz"),
    "qrp":       ("df617e1b-0840-535e-b24f-0d04a7ff05a4", CACHE_DIR / "nh_qrp_raw.csv.gz"),
}

BASE_URL     = "https://data.cms.gov/provider-data/api/1/datastore/query/{dist_id}"
PAGE_SIZE    = 1_000
CACHE_DAYS   = 8
FORCE_REFRESH = "--refresh" in sys.argv

ASSERT = {
    # (nat_lo, nat_hi, hi_lo, hi_hi) — nat bounds at 95%/106% of confirmed 2026-07-22
    "mds_qm":    (237_300, 265_000, 650,  800),   # confirmed 249,815
    "claims_qm": (55_800,  62_000,  150,  200),   # confirmed 58,780
    "qrp":       (795_700, 880_000, 2000, 2600),  # confirmed 837,615
}


# ── Utility ────────────────────────────────────────────────────────────────────

def cache_valid(path: pathlib.Path) -> bool:
    if FORCE_REFRESH or not path.exists():
        return False
    age = datetime.datetime.now() - datetime.datetime.fromtimestamp(path.stat().st_mtime)
    return age.days < CACHE_DAYS


def fetch_page(url: str, payload: bytes, max_retries: int = 6) -> dict:
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = min(10 * (2 ** attempt), 120)
                print(f"    HTTP {e.code}; retry in {wait}s ...")
                time.sleep(wait)
            else:
                raise
        except (urllib.error.URLError, OSError) as e:
            if attempt < max_retries - 1:
                wait = min(10 * (2 ** attempt), 120)
                print(f"    Network error; retry in {wait}s ...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("exhausted retries")


def load_dataset(label: str, dist_id: str, cache_path: pathlib.Path) -> pd.DataFrame:
    url = BASE_URL.format(dist_id=dist_id)

    if cache_valid(cache_path):
        print(f"  {label}: loading from cache")
        return pd.read_csv(cache_path, compression="gzip", dtype=str).fillna("")

    print(f"  {label}: fetching from API ...")
    probe = fetch_page(url, json.dumps({"limit": 1, "offset": 0}).encode())
    total = probe.get("count", "?")
    print(f"    reported count = {total:,}" if isinstance(total, int) else f"    count = {total}")

    all_rows = []
    offset = 0
    page = 0
    while True:
        page += 1
        data = fetch_page(url, json.dumps({"limit": PAGE_SIZE, "offset": offset}).encode())
        rows = data.get("results", [])
        if not rows:
            break
        all_rows.extend(rows)
        if page % 100 == 0 or len(rows) < PAGE_SIZE:
            print(f"    page {page:4}  offset={offset:7,}  total={len(all_rows):,}")
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.5)

    df = pd.DataFrame(all_rows).fillna("")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False, compression="gzip")
    print(f"  {label}: {len(df):,} rows fetched and cached")
    return df


def find_col(cols, *substrings, required=True, exclude=None):
    for c in cols:
        if all(s.lower() in c.lower() for s in substrings):
            if exclude and any(e.lower() in c.lower() for e in exclude):
                continue
            return c
    if required:
        raise ValueError(
            f"Required column not found. Searched for: {substrings!r}. "
            f"Available: {sorted(cols)}"
        )
    return None


# ── Load measure intervals reference ──────────────────────────────────────────

if MEASURE_INTERVALS_FILE.exists():
    mi = pd.read_csv(MEASURE_INTERVALS_FILE, dtype=str).fillna("")
    # Build lookup: measure_code -> {from_date, through_date, period_desc}
    mi_lookup = {
        r["measure_code"].strip(): {
            "collection_from":    r.get("data_collection_period_from_date", ""),
            "collection_through": r.get("data_collection_period_through_date", ""),
            "period_desc":        r.get("measure_date_range", ""),
        }
        for _, r in mi.iterrows()
    }
    print(f"Measure intervals loaded: {len(mi_lookup)} codes")
else:
    mi_lookup = {}
    print("WARNING: reference_measure_intervals.csv not found; period context will be empty")
print()


# ── Transform: MDS Quality Measures ───────────────────────────────────────────

def transform_mds(df_raw: pd.DataFrame) -> pd.DataFrame:
    cols = list(df_raw.columns)
    print(f"  MDS QM columns ({len(cols)}): {cols[:8]} ...")

    CCN       = find_col(cols, "cms_certification_number", required=False) or find_col(cols, "ccn")
    NAME      = find_col(cols, "provider_name", required=False)
    STATE     = find_col(cols, "state")
    MEAS_CODE = find_col(cols, "measure_code", required=False) or find_col(cols, "measure_id")
    MEAS_DESC = find_col(cols, "measure_description", required=False) or find_col(cols, "measure_name", required=False)
    RES_TYPE  = find_col(cols, "resident_type", required=False) or find_col(cols, "stay_type")
    Q1        = find_col(cols, "q1", required=False) or find_col(cols, "quarter_1")
    Q2        = find_col(cols, "q2", required=False) or find_col(cols, "quarter_2")
    Q3        = find_col(cols, "q3", required=False) or find_col(cols, "quarter_3")
    Q4        = find_col(cols, "q4", required=False) or find_col(cols, "quarter_4")
    AVG       = find_col(cols, "four_quarter_average", required=False) or find_col(cols, "average_score")
    FIVE_STAR = find_col(cols, "used_in_qm_five_star", required=False) or find_col(cols, "used_in_five_star", required=False)
    FOOTNOTE  = find_col(cols, "footnote", required=False)

    def g(row, col):
        return str(row.get(col, "")).strip() if col else ""

    out = []
    for _, r in df_raw.iterrows():
        row = r.to_dict()
        code = g(row, MEAS_CODE)
        interval = mi_lookup.get(code, {})
        out.append({
            "ccn":               g(row, CCN),
            "provider_name":     g(row, NAME),
            "state":             g(row, STATE),
            "measure_code":      code,
            "measure_desc":      g(row, MEAS_DESC),
            "resident_type":     g(row, RES_TYPE),
            "q1_score":          g(row, Q1),
            "q2_score":          g(row, Q2),
            "q3_score":          g(row, Q3),
            "q4_score":          g(row, Q4),
            "four_qtr_avg":      g(row, AVG),
            "used_in_five_star": g(row, FIVE_STAR),
            "footnote":          g(row, FOOTNOTE),
            "collection_from":   interval.get("collection_from", ""),
            "collection_through":interval.get("collection_through", ""),
        })
    return pd.DataFrame(out)


# ── Transform: Claims QM ───────────────────────────────────────────────────────

def transform_claims(df_raw: pd.DataFrame) -> pd.DataFrame:
    cols = list(df_raw.columns)
    print(f"  Claims QM columns ({len(cols)}): {cols[:8]} ...")

    CCN       = find_col(cols, "cms_certification_number", required=False) or find_col(cols, "ccn")
    NAME      = find_col(cols, "provider_name", required=False)
    STATE     = find_col(cols, "state")
    MEAS_CODE = find_col(cols, "measure_code", required=False) or find_col(cols, "measure_id")
    MEAS_DESC = find_col(cols, "measure_description", required=False) or find_col(cols, "measure_name", required=False)
    RES_TYPE  = find_col(cols, "resident_type", required=False) or find_col(cols, "stay_type")
    ADJ_SCORE = find_col(cols, "adjusted_score", required=False) or find_col(cols, "risk_adjusted")
    OBS_SCORE = find_col(cols, "observed_score", required=False)
    EXP_SCORE = find_col(cols, "expected_score", required=False)
    FIVE_STAR = find_col(cols, "used_in_qm_five_star", required=False) or find_col(cols, "used_in_five_star", required=False)
    FOOTNOTE  = find_col(cols, "footnote", required=False)

    def g(row, col):
        return str(row.get(col, "")).strip() if col else ""

    out = []
    for _, r in df_raw.iterrows():
        row = r.to_dict()
        code = g(row, MEAS_CODE)
        interval = mi_lookup.get(code, {})
        out.append({
            "ccn":               g(row, CCN),
            "provider_name":     g(row, NAME),
            "state":             g(row, STATE),
            "measure_code":      code,
            "measure_desc":      g(row, MEAS_DESC),
            "resident_type":     g(row, RES_TYPE),
            "adjusted_score":    g(row, ADJ_SCORE),
            "observed_score":    g(row, OBS_SCORE),
            "expected_score":    g(row, EXP_SCORE),
            "used_in_five_star": g(row, FIVE_STAR),
            "footnote":          g(row, FOOTNOTE),
            "collection_from":   interval.get("collection_from", ""),
            "collection_through":interval.get("collection_through", ""),
        })
    return pd.DataFrame(out)


# ── Transform: QRP ────────────────────────────────────────────────────────────

def transform_qrp(df_raw: pd.DataFrame) -> pd.DataFrame:
    cols = list(df_raw.columns)
    print(f"  QRP columns ({len(cols)}): {cols[:8]} ...")

    CCN       = find_col(cols, "cms_certification_number", required=False) or find_col(cols, "ccn")
    NAME      = find_col(cols, "provider_name", required=False)
    STATE     = find_col(cols, "state")
    COUNTY    = find_col(cols, "county", required=False)
    MEAS_CODE = find_col(cols, "measure_code", required=False) or find_col(cols, "measure_id")
    SCORE     = find_col(cols, "score")
    FOOTNOTE  = find_col(cols, "footnote", required=False)
    START     = find_col(cols, "start_date", required=False)
    END       = find_col(cols, "end_date", required=False)

    def g(row, col):
        return str(row.get(col, "")).strip() if col else ""

    out = []
    for _, r in df_raw.iterrows():
        row = r.to_dict()
        code = g(row, MEAS_CODE)
        interval = mi_lookup.get(code, {})
        out.append({
            "ccn":               g(row, CCN),
            "provider_name":     g(row, NAME),
            "state":             g(row, STATE),
            "county":            g(row, COUNTY),
            "measure_code":      code,
            "score":             g(row, SCORE),
            "footnote":          g(row, FOOTNOTE),
            "start_date":        g(row, START),
            "end_date":          g(row, END),
            "collection_from":   interval.get("collection_from", ""),
            "collection_through":interval.get("collection_through", ""),
        })
    return pd.DataFrame(out)


# ── Main ───────────────────────────────────────────────────────────────────────

print("=" * 70)
print("MDS Quality Measures")
print("=" * 70)
df_mds_raw = load_dataset("mds_qm", *DATASETS["mds_qm"])
df_mds = transform_mds(df_mds_raw)

print()
print("=" * 70)
print("Claims-based Quality Measures")
print("=" * 70)
df_claims_raw = load_dataset("claims_qm", *DATASETS["claims_qm"])
df_claims = transform_claims(df_claims_raw)

print()
print("=" * 70)
print("SNF QRP Provider Data")
print("=" * 70)
df_qrp_raw = load_dataset("qrp", *DATASETS["qrp"])
df_qrp = transform_qrp(df_qrp_raw)


# ── Assertions ─────────────────────────────────────────────────────────────────

print()
print("Assertions ...")

def check(label, df, nat_lo, nat_hi, hi_lo, hi_hi):
    n     = len(df)
    hi_n  = len(df[df["state"] == "HI"]) if "state" in df.columns else 0
    ok_n  = nat_lo <= n <= nat_hi
    ok_hi = hi_lo  <= hi_n <= hi_hi
    status = "PASS" if (ok_n and ok_hi) else "FAIL"
    print(f"  {status}: {label:<20}  national={n:,}  HI={hi_n}")
    if not ok_n:
        raise AssertionError(f"FAILED: {label} national {n:,} outside [{nat_lo:,}, {nat_hi:,}]")
    if not ok_hi:
        raise AssertionError(f"FAILED: {label} HI {hi_n} outside [{hi_lo}, {hi_hi}]")

check("MDS QM",    df_mds,    *ASSERT["mds_qm"])
check("Claims QM", df_claims, *ASSERT["claims_qm"])
check("QRP",       df_qrp,    *ASSERT["qrp"])


# ── Summary ────────────────────────────────────────────────────────────────────

print()
print("MDS QM -- HI measure averages (four-quarter avg, top 10):")
hi_mds = df_mds[df_mds["state"] == "HI"].copy()
hi_mds["four_qtr_avg_num"] = pd.to_numeric(hi_mds["four_qtr_avg"], errors="coerce")
hi_mds_agg = (hi_mds.groupby(["measure_code", "measure_desc"])
              ["four_qtr_avg_num"].mean().reset_index()
              .sort_values("four_qtr_avg_num", ascending=False).head(10))
for _, r in hi_mds_agg.iterrows():
    print(f"  {r['measure_code']:<6} {str(r['measure_desc'])[:55]:<55} {r['four_qtr_avg_num']:.1f}")

print()
print("Claims QM -- HI adjusted scores:")
hi_claims = df_claims[df_claims["state"] == "HI"].copy()
hi_claims_agg = (hi_claims.groupby(["measure_code", "measure_desc"])
                 ["adjusted_score"].apply(
                     lambda x: pd.to_numeric(x, errors="coerce").mean()).reset_index())
for _, r in hi_claims_agg.iterrows():
    val = r["adjusted_score"]
    val_str = f"{val:.2f}" if pd.notna(val) else "N/A"
    print(f"  {r['measure_code']:<6} {str(r['measure_desc'])[:55]:<55} {val_str}")

print()
hi_qrp = df_qrp[df_qrp["state"] == "HI"]
print(f"QRP -- HI unique CCNs reporting: {hi_qrp['ccn'].nunique()} "
      f"  measures per CCN: {len(hi_qrp) / hi_qrp['ccn'].nunique():.1f}")


# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df_mds.to_parquet(OUTPUT_MDS, index=False, engine="pyarrow")
df_claims.to_parquet(OUTPUT_CLAIMS, index=False, engine="pyarrow")
df_qrp.to_parquet(OUTPUT_QRP, index=False, engine="pyarrow")

print()
print(f"MDS QM:    {OUTPUT_MDS}  ({len(df_mds):,} rows, {len(df_mds.columns)} cols)")
print(f"Claims QM: {OUTPUT_CLAIMS}  ({len(df_claims):,} rows)")
print(f"QRP:       {OUTPUT_QRP}  ({len(df_qrp):,} rows)")
print()
print("Join keys:")
print("  ccn           -->  facility_master, nh_provider_info, nh_deficiencies")
print("  measure_code  -->  reference_measure_intervals (collection period)")
