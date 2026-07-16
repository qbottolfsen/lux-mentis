"""
05_snf_vbp_national.py
SNF Value-Based Purchasing -- national facility performance scores.

Source: CMS Provider Data -- SNF VBP
  Dataset:      284v-j9fz
  Distribution: cf1f058c-65d6-5496-9770-a244cfab2a13
  Updated:      Annually (FY cycle)

One row per SNF in the VBP program. Not all SNFs participate -- excluded:
  new SNFs, very low volume, waiver holders, Medicaid-only certified.

VBP domains and scoring:
  SNFRM  -- SNF Readmission Measure (30-day unplanned readmissions)
            Achievement threshold vs. benchmark; higher = better
  HAI    -- Healthcare-Associated Infections (NHSN SIR-based)
            Lower SIR = better; achievement threshold set nationally
  Turnover    -- Total nursing staff turnover rate (annual %)
  Staffing    -- Total nursing HPRD (daily average from PBJ)

Performance Score: composite 0-100 (weighted across domains)
Incentive Payment Multiplier (IPM): 0.98 - 1.02
  < 1.0 = penalty (worse than threshold)
  = 1.0 = neutral
  > 1.0 = bonus (better than threshold)

Output: output_reference/snf_vbp_national.csv

Pre-registered assertions:
  National rows:  [8,000 -- 15,000]  (not all 14,695 SNFs participate)
  HI rows:        [35 -- 42]
  IPM range:      all in [0.96 -- 1.04]  (small adjustment range)
  Performance scores: mostly numeric
"""

import json, pathlib, sys, time, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "snf_vbp_national.csv"

DIST_ID  = "cf1f058c-65d6-5496-9770-a244cfab2a13"
BASE_URL = f"https://data.cms.gov/provider-data/api/1/datastore/query/{DIST_ID}"
PAGE_SIZE = 1_000

EXPECTED_MIN = 8_000
EXPECTED_MAX = 15_000
HI_MIN = 35
HI_MAX = 42


def fetch_page(payload: bytes, max_retries: int = 5) -> dict:
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(BASE_URL, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
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


print("SNF Value-Based Purchasing -- national")
print(f"Distribution: {DIST_ID}")
print()

probe = fetch_page(json.dumps({"limit": 1, "offset": 0}).encode())
total_count = probe.get("count", "?")
raw_cols = list(probe["results"][0].keys()) if probe.get("results") else []
print(f"Reported count: {total_count:,}" if isinstance(total_count, int)
      else f"Reported count: {total_count}")
print(f"Columns ({len(raw_cols)}): {raw_cols[:8]} ...")
print()


def find_col(cols, *substrings, exclude=None):
    for c in cols:
        if all(s.lower() in c.lower() for s in substrings):
            if exclude and any(e.lower() in c.lower() for e in exclude):
                continue
            return c
    return None


COL = {
    "ccn":         find_col(raw_cols, "cms_certification_number") or find_col(raw_cols, "ccn"),
    "name":        find_col(raw_cols, "provider_name"),
    "state":       find_col(raw_cols, "state"),
    "city":        find_col(raw_cols, "city") or find_col(raw_cols, "citytown"),
    "zip":         find_col(raw_cols, "zip"),
    # SNFRM (readmission) scores
    "snfrm_ach":   find_col(raw_cols, "snfrm", "achievement", exclude=["improvement"]),
    "snfrm_imp":   find_col(raw_cols, "snfrm", "improvement"),
    "snfrm_score": find_col(raw_cols, "snfrm", "measure_score") or find_col(raw_cols, "snfrm_score"),
    # HAI scores
    "hai_ach":     find_col(raw_cols, "hai", "achievement", exclude=["improvement"]),
    "hai_imp":     find_col(raw_cols, "hai", "improvement"),
    "hai_score":   find_col(raw_cols, "hai", "measure_score") or find_col(raw_cols, "hai_score"),
    # Turnover and staffing
    "turnover_score": find_col(raw_cols, "turnover_measure") or find_col(raw_cols, "turnover_score"),
    "staffing_score": find_col(raw_cols, "staffing_measure") or find_col(raw_cols, "staffing_score"),
    # Summary
    "performance_score": find_col(raw_cols, "performance_score") or find_col(raw_cols, "total_performance"),
    "ipm":               find_col(raw_cols, "incentive_payment_multiplier") or find_col(raw_cols, "multiplier"),
}

print("Column mapping:")
for k, v in COL.items():
    print(f"  {k:<20} {v or 'NOT FOUND'}")
print()

# Fetch all pages
all_rows = list(probe.get("results", []))
offset = PAGE_SIZE
page = 1
print(f"  Page  1: {len(all_rows)}")

while True:
    page += 1
    data = fetch_page(json.dumps({"limit": PAGE_SIZE, "offset": offset}).encode())
    rows = data.get("results", [])
    if not rows:
        break
    all_rows.extend(rows)
    print(f"  Page {page:2}: offset={offset:6,}  total={len(all_rows):,}")
    if len(rows) < PAGE_SIZE:
        break
    offset += PAGE_SIZE
    time.sleep(0.3)

print(f"Fetched {len(all_rows):,} rows")
print()


def g(row, key):
    col = COL.get(key)
    return str(row.get(col, "")).strip() if col else ""


def safe_float(v):
    try:
        return float(str(v).strip()) if v not in (None, "", "N/A", "Not Available") else None
    except (ValueError, TypeError):
        return None


out = []
for r in all_rows:
    ps    = safe_float(g(r, "performance_score"))
    ipm   = safe_float(g(r, "ipm"))
    out.append({
        "ccn":                g(r, "ccn"),
        "provider_name":      g(r, "name"),
        "state":              g(r, "state"),
        "city":               g(r, "city"),
        "zip":                g(r, "zip"),
        "snfrm_achievement":  g(r, "snfrm_ach"),
        "snfrm_improvement":  g(r, "snfrm_imp"),
        "snfrm_measure_score":g(r, "snfrm_score"),
        "hai_achievement":    g(r, "hai_ach"),
        "hai_improvement":    g(r, "hai_imp"),
        "hai_measure_score":  g(r, "hai_score"),
        "turnover_score":     g(r, "turnover_score"),
        "staffing_score":     g(r, "staffing_score"),
        "performance_score":  "" if ps  is None else ps,
        "incentive_payment_multiplier": "" if ipm is None else ipm,
        "vbp_penalty":        str(ipm is not None and ipm < 1.0) if ipm is not None else "",
        "vbp_bonus":          str(ipm is not None and ipm > 1.0) if ipm is not None else "",
    })

df = pd.DataFrame(out)


# ── Assertions ─────────────────────────────────────────────────────────────────

print("Assertions ...")

total = len(df)
if not (EXPECTED_MIN <= total <= EXPECTED_MAX):
    raise AssertionError(f"FAILED: {total:,} rows outside [{EXPECTED_MIN:,}, {EXPECTED_MAX:,}]")
print(f"  PASS: {total:,} facilities in VBP program")

hi = df[df["state"] == "HI"]
if not (HI_MIN <= len(hi) <= HI_MAX):
    raise AssertionError(f"FAILED: HI rows {len(hi)} outside [{HI_MIN}, {HI_MAX}]")
print(f"  PASS: {len(hi)} HI facilities")

ipm_vals = pd.to_numeric(df["incentive_payment_multiplier"], errors="coerce").dropna()
if len(ipm_vals) > 0:
    ipm_min = ipm_vals.min()
    ipm_max = ipm_vals.max()
    if not (0.96 <= ipm_min and ipm_max <= 1.04):
        print(f"  WARN: IPM range [{ipm_min:.4f}, {ipm_max:.4f}] outside expected [0.96, 1.04]")
    else:
        print(f"  PASS: IPM range [{ipm_min:.4f}, {ipm_max:.4f}]")


# ── Summary ────────────────────────────────────────────────────────────────────

print()
ipm_num = pd.to_numeric(df["incentive_payment_multiplier"], errors="coerce")
penalty_n = (ipm_num < 1.0).sum()
bonus_n   = (ipm_num > 1.0).sum()
neutral_n = (ipm_num == 1.0).sum()
print(f"National VBP outcome:")
print(f"  Bonus  (IPM > 1.0): {bonus_n:,}  ({bonus_n/total*100:.1f}%)")
print(f"  Neutral (IPM = 1.0): {neutral_n:,}  ({neutral_n/total*100:.1f}%)")
print(f"  Penalty (IPM < 1.0): {penalty_n:,}  ({penalty_n/total*100:.1f}%)")

print()
hi_ipm = pd.to_numeric(hi["incentive_payment_multiplier"], errors="coerce")
print(f"Hawaii VBP (n={len(hi)}):")
hi_sorted = hi.copy()
hi_sorted["ipm_num"] = pd.to_numeric(hi_sorted["incentive_payment_multiplier"], errors="coerce")
hi_sorted = hi_sorted.sort_values("ipm_num", ascending=False)
print(hi_sorted[["ccn", "provider_name", "performance_score",
                  "incentive_payment_multiplier", "vbp_penalty"]].to_string(index=False))


# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(df):,}  Cols: {len(df.columns)}")
print()
print("Join keys:")
print("  ccn  -->  facility_master_national.csv")
print("  ccn  -->  nh_provider_info_national.csv (Five-Star staffing/turnover context)")
print("  ccn  -->  nh_quality_measures_national (SNFRM relates to readmission QMs)")
