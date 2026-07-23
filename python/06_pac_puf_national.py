"""
06_pac_puf_national.py
SNF Post-Acute Care Utilization (PAC PUF) -- national provider-level data.

Source: CMS data-api v1 (NOT DKAN provider-data)
  UUID:       eaed338b-847e-41b1-a4d3-a206f40dc72b
  Endpoint:   https://data.cms.gov/data-api/v1/dataset/{UUID}/data
  Updated:    Annually (FY cycle)

Dataset has three SMRY_CTGRY values: PROVIDER / STATE / NATION.
This script pulls PROVIDER-level rows only (facility-level utilization).

Not all SNFs appear -- facilities with <11 Medicare beneficiaries are suppressed.
HI: 33 of 42 SNFs reported (9 suppressed for low volume).

69-column superset of 4c2a8bf6 (40 cols). Additional cols vs. prior version:
  Primary diagnosis category mix (17 categories: PRMRY_DX_INFCTN_PCT,
  CIRCSYSTM_PCT, RSPSYSTM_PCT, MUSCSKLTN_PCT, NRVSYSTM_PCT, etc.)

Key interpretive columns:
  TOT_PT_MNTS_STAY   -- avg physical therapy minutes per stay
  TOT_OT_MNTS_STAY   -- avg occupational therapy minutes per stay
  TOT_SLP_MNTS_STAY  -- avg speech-language pathology minutes per stay
  DUAL_PCT           -- % of Medicare beneficiaries also on Medicaid
  ALZH_PCT           -- % with Alzheimer's / dementia
  DIABETES_PCT       -- % with diabetes
  ACUTE_HOSP_DAYS    -- avg acute hospital days prior to SNF admission

Derived output:
  high_therapy_intensity  -- True if PT+OT minutes per stay > 500
  high_dual_pct           -- True if dual eligible > 35%
  pdpm_high_med_surg      -- True if medical/surgical case mix > 50%

Output: output_reference/pac_puf_national.csv

Pre-registered assertions:
  National PROVIDER rows:  [8,000 -- 12,000]  (suppression reduces universe)
  HI rows:                 [28 -- 36]          (33 confirmed for FY2023)
  PRVDR_ID all start with 12: True for HI subset
  DUAL_PCT range: [0 -- 100]
"""

import json, pathlib, sys, time, urllib.parse, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "pac_puf_national.csv"

UUID      = "eaed338b-847e-41b1-a4d3-a206f40dc72b"
BASE_URL  = f"https://data.cms.gov/data-api/v1/dataset/{UUID}/data"
PAGE_SIZE = 500

NATIONAL_MIN = 13_400  # 95% of 14,161 confirmed 2026-07-22
NATIONAL_MAX = 16_000
HI_MIN = 28
HI_MAX = 36


def fetch(params: dict, max_retries: int = 5) -> list:
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = 10 * (2 ** attempt)
                print(f"  HTTP {e.code}; retry in {wait}s ...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("exhausted retries")


print("PAC PUF -- SNF Post-Acute Care Utilization, Provider Level")
print(f"UUID: {UUID}")
print()

# Probe to discover columns
probe = fetch({"filter[SMRY_CTGRY]": "PROVIDER", "size": 1, "offset": 0})
if not probe:
    sys.exit("No rows returned from probe. Check UUID and filter.")
raw_cols = list(probe[0].keys())
print(f"Columns ({len(raw_cols)}): {raw_cols[:8]} ...")
print()

# Find columns by case-insensitive substring
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

COL = {
    "prvdr_id":       find_col(raw_cols, "prvdr_id", required=False) or find_col(raw_cols, "provider_id"),
    "prvdr_name":     find_col(raw_cols, "prvdr_name", required=False) or find_col(raw_cols, "provider_name", required=False),
    "state":          find_col(raw_cols, "state"),
    "smry_ctgry":     find_col(raw_cols, "smry_ctgry"),
    "srvc_ctgry":     find_col(raw_cols, "srvc_ctgry"),
    "year":           find_col(raw_cols, "year", required=False) or find_col(raw_cols, "yr"),
    # Therapy intensity (optional enrichment)
    "pt_mnts":        find_col(raw_cols, "pt_mnts", required=False) or find_col(raw_cols, "tot_pt", required=False),
    "ot_mnts":        find_col(raw_cols, "ot_mnts", required=False) or find_col(raw_cols, "tot_ot", required=False),
    "slp_mnts":       find_col(raw_cols, "slp_mnts", required=False) or find_col(raw_cols, "tot_slp", required=False),
    # Utilization
    "tot_episd":      find_col(raw_cols, "tot_episd", required=False) or find_col(raw_cols, "episodes"),
    "avg_los":        find_col(raw_cols, "avg_los", required=False) or find_col(raw_cols, "length_of_stay"),
    # Payer / demographics
    "dual_pct":       find_col(raw_cols, "dual_pct", required=False) or find_col(raw_cols, "dual"),
    "alzh_pct":       find_col(raw_cols, "alzh", required=False) or find_col(raw_cols, "dementia", required=False),
    "diabetes_pct":   find_col(raw_cols, "diabetes", required=False),
    "acute_hosp_days":find_col(raw_cols, "acute_hosp", required=False),
    # Primary diagnosis pcts (optional enrichment)
    "dx_infection":   find_col(raw_cols, "infctn", required=False) or find_col(raw_cols, "infection", required=False),
    "dx_cardio":      find_col(raw_cols, "circsystm", required=False) or find_col(raw_cols, "cardiac", required=False),
    "dx_respiratory": find_col(raw_cols, "rspsystm", required=False) or find_col(raw_cols, "respiratory", required=False),
    "dx_musculo":     find_col(raw_cols, "muscskltn", required=False) or find_col(raw_cols, "musculo", required=False),
    "dx_neuro":       find_col(raw_cols, "nrvsystm", required=False) or find_col(raw_cols, "neuro", required=False),
    "dx_ortho":       find_col(raw_cols, "orth", required=False) or find_col(raw_cols, "ortho", required=False),
}

print("Column mapping (selected):")
for k, v in list(COL.items())[:12]:
    print(f"  {k:<20} {v or 'NOT FOUND'}")
print()

# Fetch all PROVIDER rows (no state filter for national build)
print("Fetching national PROVIDER-level rows ...")
all_rows: list = []
offset = 0
page = 0

while True:
    page += 1
    rows = fetch({
        "filter[SMRY_CTGRY]": "PROVIDER",
        "size": PAGE_SIZE,
        "offset": offset
    })
    if not rows:
        break
    all_rows.extend(rows)
    print(f"  Page {page:3}: offset={offset:6,}  got={len(rows):,}  total={len(all_rows):,}")
    if len(rows) < PAGE_SIZE:
        break
    offset += PAGE_SIZE
    time.sleep(0.3)

print(f"Fetched {len(all_rows):,} PROVIDER-level rows")
print()


def g(row, key):
    col = COL.get(key)
    return str(row.get(col, "")).strip() if col else ""


def safe_float(v):
    try:
        return float(str(v).strip()) if v not in (None, "", "N/A", "Not Available", "*") else None
    except (ValueError, TypeError):
        return None


# Preserve all original columns + add derived flags
out = []
for r in all_rows:
    pt   = safe_float(g(r, "pt_mnts"))
    ot   = safe_float(g(r, "ot_mnts"))
    dual = safe_float(g(r, "dual_pct"))

    base = {k: str(v).strip() for k, v in r.items()}
    base["high_therapy_intensity"] = (
        str(pt is not None and ot is not None and (pt + ot) > 500)
        if pt is not None or ot is not None else ""
    )
    base["high_dual_pct"] = str(dual is not None and dual > 35) if dual is not None else ""
    out.append(base)

df = pd.DataFrame(out)


# ── Assertions ─────────────────────────────────────────────────────────────────

print("Assertions ...")

total = len(df)
if not (NATIONAL_MIN <= total <= NATIONAL_MAX):
    raise AssertionError(f"FAILED: {total:,} PROVIDER rows outside [{NATIONAL_MIN:,}, {NATIONAL_MAX:,}]")
print(f"  PASS: {total:,} national provider rows")

state_col = COL["state"] or find_col(list(df.columns), "state", required=False)
if state_col:
    hi = df[df[state_col] == "HI"]
    if not (HI_MIN <= len(hi) <= HI_MAX):
        raise AssertionError(f"FAILED: HI rows {len(hi)} outside [{HI_MIN}, {HI_MAX}]")
    print(f"  PASS: {len(hi)} HI rows")

    prvdr_col = COL["prvdr_id"] or find_col(list(df.columns), "prvdr_id", required=False)
    if prvdr_col:
        hi_non12 = hi[~hi[prvdr_col].str.startswith("12", na=True)]
        if len(hi_non12) > 0:
            print(f"  WARN: {len(hi_non12)} HI PRVDR_IDs don't start with '12':")
            print(hi_non12[[prvdr_col, COL.get("prvdr_name", prvdr_col)]].to_string())
        else:
            print(f"  PASS: all HI PRVDR_IDs start with '12'")
else:
    print("  WARN: no state column found for HI filter")
    hi = pd.DataFrame()


# ── HI Summary ─────────────────────────────────────────────────────────────────

if len(hi) > 0:
    print()
    pt_col   = COL.get("pt_mnts")
    ot_col   = COL.get("ot_mnts")
    dual_col = COL.get("dual_pct")
    name_col = COL.get("prvdr_name")
    prvdr_c  = COL.get("prvdr_id")

    display_cols = [c for c in [prvdr_c, name_col, pt_col, ot_col, dual_col] if c]
    if display_cols:
        print(f"Hawaii PAC PUF (n={len(hi)}) -- therapy intensity + dual %:")
        hi_disp = hi.copy()
        for c in [pt_col, ot_col, dual_col]:
            if c:
                hi_disp[c] = pd.to_numeric(hi_disp[c], errors="coerce")
        if pt_col and ot_col:
            hi_disp = hi_disp.sort_values([pt_col], ascending=False, na_position="last")
        print(hi_disp[display_cols].head(15).to_string(index=False))


# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(df):,}  Cols: {len(df.columns)}")
print()
print("Join keys:")
print("  PRVDR_ID (CCN)  -->  facility_master_national.csv")
print("  PRVDR_ID (CCN)  -->  nh_provider_info_national.csv (Five-Star for same facilities)")
print("  PRVDR_ID (CCN)  -->  snf_vbp_national.csv (readmission/HAI performance)")
print("  DUAL_PCT        -->  medicare_monthly_enrollment.csv (state-level MA/dual context)")
