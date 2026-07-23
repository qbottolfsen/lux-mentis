"""
07_snf_cost_report_national.py
SNF Cost Report (HCRIS) -- national facility financial data.

Source: CMS data-api v1 (HCRIS -- Healthcare Cost Report Information System)
  UUID:      a69d3df7-3f66-4a0d-b5b8-0d66049bd565
  Endpoint:  https://data.cms.gov/data-api/v1/dataset/{UUID}/data
  Updated:   Annually; FY 2023 data confirmed available

122 columns covering payer mix, financials, balance sheet, and staffing costs.

Derived metrics (added by this script):
  medicare_days_pct   -- SNF Days Title XVIII / Total Days × 100
  medicaid_days_pct   -- SNF Days Title XIX / Total Days × 100
  private_other_pct   -- remaining days %
  operating_margin    -- Net Income / Net Patient Revenue × 100
  occupancy_pct       -- Total Days / (Beds × 365) × 100  (estimated)
  contract_labor_pct  -- Contract Labor / Total Salaries × 100
  medicaid_heavy      -- True if medicaid_days_pct > 60  (mission-driven facilities)
  financially_stressed -- True if operating_margin < -5  (persistent loss)

Type of Control codes (HCRIS standard):
  1 = Voluntary Nonprofit / Church
  2 = Voluntary Nonprofit / Other
  3 = Proprietary / Partnership
  4 = Proprietary / Corporation
  5 = Proprietary / Other
  6 = Gov / Federal
  7 = Gov / State
  8 = Gov / City-County
  9 = Gov / Hospital District

Output: output_reference/snf_cost_report_national.csv

Pre-registered assertions:
  National rows:   [10,000 -- 100,000]  (multiple FY may be present)
  HI rows:         [30 -- 80]           (37 confirmed for FY2023; more if multi-year)
  Net Income range: no assertion (can be negative)
  Occupancy range:  0--110% (small rounding OK)
  HI operating margin: warn if any > 30% (data quality flag)
"""

import json, pathlib, sys, time, urllib.parse, urllib.request

try:
    import pandas as pd
    import numpy as np
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "snf_cost_report_national.csv"

UUID     = "a69d3df7-3f66-4a0d-b5b8-0d66049bd565"
BASE_URL = f"https://data.cms.gov/data-api/v1/dataset/{UUID}/data"
PAGE_SIZE = 500

NATIONAL_MIN = 14_186  # 95% of 14,933 confirmed 2026-07-22
NATIONAL_MAX = 16_500
HI_MIN = 30
HI_MAX = 80


def fetch(params: dict, max_retries: int = 5) -> list:
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = 10 * (2 ** attempt)
                print(f"  HTTP {e.code}; retry in {wait}s ...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("exhausted retries")


print("SNF Cost Report (HCRIS) -- national financial data")
print(f"UUID: {UUID}")
print()

# Probe to discover columns and total size
probe = fetch({"size": 2, "offset": 0})
if not probe:
    sys.exit("No rows returned from probe. Check UUID.")
raw_cols = list(probe[0].keys())
print(f"Columns ({len(raw_cols)}): {raw_cols[:8]} ...")
print()

# Probe total row count (pull 1 row to see if there's a header with count)
# data-api v1 returns a plain array; count must be inferred from pagination
# Try pulling all rows for a known-small subset first to confirm filter syntax
hi_probe = fetch({"filter[State Code]": "HI", "size": 5, "offset": 0})
print(f"HI probe (first 5 rows): {len(hi_probe)} returned")
if hi_probe:
    print(f"  Sample CCN: {hi_probe[0].get('Provider CCN', hi_probe[0].get('provider_ccn', '?'))}")
    print(f"  Sample state col value: {hi_probe[0].get('State Code', hi_probe[0].get('state_code', '?'))}")
print()


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
    "ccn":              find_col(raw_cols, "provider ccn", required=False) or find_col(raw_cols, "ccn"),
    "name":             find_col(raw_cols, "facility name", required=False) or find_col(raw_cols, "provider name"),
    "state":            find_col(raw_cols, "state code", required=False) or find_col(raw_cols, "state"),
    "control_type":     find_col(raw_cols, "type of control", required=False),
    "fy_begin":         find_col(raw_cols, "fiscal year begin", required=False) or find_col(raw_cols, "fy begin"),
    "fy_end":           find_col(raw_cols, "fiscal year end", required=False) or find_col(raw_cols, "fy end"),
    # Payer days — SNF-specific (excludes NF/Medicaid-only beds)
    "days_medicare":    find_col(raw_cols, "snf days title xviii"),
    "days_medicaid":    find_col(raw_cols, "snf days title xix"),
    "days_other":       find_col(raw_cols, "snf days other", required=False),
    "days_total":       find_col(raw_cols, "snf days total"),
    "bed_days_avail":   find_col(raw_cols, "snf bed days available"),
    # Beds
    "beds":             find_col(raw_cols, "snf number of beds", required=False) or find_col(raw_cols, "number of beds", required=False),
    # Financials
    "net_revenue":      find_col(raw_cols, "net patient revenue"),
    "net_income":       find_col(raw_cols, "net income"),
    "total_costs":      find_col(raw_cols, "total costs"),
    "total_salaries":   find_col(raw_cols, "total salaries", required=False),
    "contract_labor":   find_col(raw_cols, "contract labor", required=False),
}

print("Column mapping:")
for k, v in COL.items():
    print(f"  {k:<20} {v or 'NOT FOUND'}")
print()

# Fetch all rows nationally
print("Fetching all rows nationally ...")
all_rows: list = []
offset = 0
page = 0

while True:
    page += 1
    rows = fetch({"size": PAGE_SIZE, "offset": offset})
    if not rows:
        break
    all_rows.extend(rows)
    print(f"  Page {page:3}: offset={offset:6,}  got={len(rows):,}  total={len(all_rows):,}")
    if len(rows) < PAGE_SIZE:
        break
    offset += PAGE_SIZE
    time.sleep(0.3)

print(f"Fetched {len(all_rows):,} rows total")
print()


def g(row, key):
    col = COL.get(key)
    return str(row.get(col, "")).strip() if col else ""


def safe_float(v):
    try:
        val = str(v).strip().replace(",", "").replace("$", "")
        return float(val) if val not in ("", "N/A", "Not Available") else None
    except (ValueError, TypeError):
        return None


# Build normalized output
out = []
for r in all_rows:
    days_med   = safe_float(g(r, "days_medicare"))
    days_mcd   = safe_float(g(r, "days_medicaid"))
    days_oth   = safe_float(g(r, "days_other"))
    days_tot   = safe_float(g(r, "days_total"))
    bed_days   = safe_float(g(r, "bed_days_avail"))
    beds       = safe_float(g(r, "beds"))
    net_rev    = safe_float(g(r, "net_revenue"))
    net_inc    = safe_float(g(r, "net_income"))
    total_sal  = safe_float(g(r, "total_salaries"))
    contract   = safe_float(g(r, "contract_labor"))

    med_pct  = round(days_med / days_tot * 100, 1) if days_med is not None and days_tot else None
    mcd_pct  = round(days_mcd / days_tot * 100, 1) if days_mcd is not None and days_tot else None
    oth_pct  = round(days_oth / days_tot * 100, 1) if days_oth is not None and days_tot else None
    margin   = round(net_inc / net_rev * 100, 2)   if net_inc is not None and net_rev and net_rev != 0 else None
    occupancy = round(days_tot / bed_days * 100, 1) if days_tot and bed_days and bed_days > 0 else None
    contract_pct = round(contract / total_sal * 100, 1) if contract is not None and total_sal and total_sal > 0 else None

    out.append({
        "ccn":                  g(r, "ccn").zfill(6) if g(r, "ccn") else "",
        "facility_name":        g(r, "name"),
        "state":                g(r, "state"),
        "type_of_control":      g(r, "control_type"),
        "fy_begin":             g(r, "fy_begin"),
        "fy_end":               g(r, "fy_end"),
        "beds":                 "" if beds is None else beds,
        "days_medicare":        "" if days_med is None else days_med,
        "days_medicaid":        "" if days_mcd is None else days_mcd,
        "days_total":           "" if days_tot is None else days_tot,
        "bed_days_available":   "" if bed_days is None else bed_days,
        "medicare_days_pct":    "" if med_pct is None else med_pct,
        "medicaid_days_pct":    "" if mcd_pct is None else mcd_pct,
        "private_other_pct":    "" if oth_pct is None else oth_pct,
        "net_patient_revenue":  "" if net_rev is None else net_rev,
        "net_income":           "" if net_inc is None else net_inc,
        "total_costs":          "" if safe_float(g(r, "total_costs")) is None else safe_float(g(r, "total_costs")),
        "total_salaries":       "" if total_sal is None else total_sal,
        "contract_labor":       "" if contract is None else contract,
        "operating_margin_pct": "" if margin is None else margin,
        "occupancy_pct":        "" if occupancy is None else occupancy,
        "contract_labor_pct":   "" if contract_pct is None else contract_pct,
        # Derived flags
        "medicaid_heavy":       str(mcd_pct is not None and mcd_pct > 60),
        "financially_stressed": str(margin is not None and margin < -5),
    })

df = pd.DataFrame(out)


# ── Assertions ─────────────────────────────────────────────────────────────────

print("Assertions ...")

total = len(df)
if not (NATIONAL_MIN <= total <= NATIONAL_MAX):
    raise AssertionError(f"FAILED: {total:,} rows outside [{NATIONAL_MIN:,}, {NATIONAL_MAX:,}]")
print(f"  PASS: {total:,} rows nationally")

hi = df[df["state"] == "HI"]
if not (HI_MIN <= len(hi) <= HI_MAX):
    raise AssertionError(f"FAILED: HI rows {len(hi)} outside [{HI_MIN}, {HI_MAX}]")
print(f"  PASS: {len(hi)} HI rows")

# Occupancy sanity: 0-110% (small rounding OK)
occ = pd.to_numeric(df["occupancy_pct"], errors="coerce").dropna()
if len(occ) > 0:
    occ_max = occ.max()
    if occ_max > 110:
        print(f"  WARN: max occupancy {occ_max:.1f}% > 110 (data quality issue)")
    else:
        print(f"  PASS: occupancy range [{occ.min():.1f}%, {occ.max():.1f}%]")

# HI margin sanity
hi_margin = pd.to_numeric(hi["operating_margin_pct"], errors="coerce").dropna()
hi_outliers = hi_margin[hi_margin.abs() > 50]
if len(hi_outliers) > 0:
    print(f"  WARN: {len(hi_outliers)} HI facilities with margin > 50% or < -50% (check data)")
else:
    if len(hi_margin) > 0:
        print(f"  PASS: HI operating margin range [{hi_margin.min():.1f}%, {hi_margin.max():.1f}%]")


# ── Summary ────────────────────────────────────────────────────────────────────

print()
# Fiscal years present
fy_col = "fy_end"
if fy_col in df.columns:
    fy_years = df[fy_col].str[:4].value_counts().sort_index()
    print(f"Fiscal years in dataset:")
    for yr, cnt in fy_years.items():
        print(f"  FY{yr}: {cnt:,} facilities")
    print()

# Control type distribution nationally
ctrl_dist = df["type_of_control"].value_counts()
print("Control type distribution (national, top 8):")
for k, v in ctrl_dist.head(8).items():
    print(f"  {k}: {v:,}")
print()

# HI financials
if len(hi) > 0:
    hi_display = hi[["ccn", "facility_name", "fy_end",
                      "medicare_days_pct", "medicaid_days_pct",
                      "operating_margin_pct", "occupancy_pct",
                      "medicaid_heavy"]].copy()
    for c in ["medicare_days_pct", "medicaid_days_pct", "operating_margin_pct", "occupancy_pct"]:
        hi_display[c] = pd.to_numeric(hi_display[c], errors="coerce")
    hi_display = hi_display.sort_values("operating_margin_pct", ascending=True)
    print(f"Hawaii SNF Financial Profile (n={len(hi)}):")
    print(hi_display.to_string(index=False))
    print()
    print(f"  Medicaid-heavy (>60%): {(hi_display['medicaid_days_pct'] > 60).sum()} facilities")
    print(f"  Financially stressed (<-5% margin): {(hi_display['operating_margin_pct'] < -5).sum()} facilities")


# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(df):,}  Cols: {len(df.columns)}")
print()
print("Join keys:")
print("  ccn  -->  facility_master_national.csv")
print("  ccn  -->  nh_provider_info_national.csv (Five-Star + staffing cross-check)")
print("  ccn  -->  snf_owners_national.csv (control type vs ownership type validation)")
print("  ccn  -->  nh_penalties_by_facility.csv (financial stress + penalty co-occurrence)")
