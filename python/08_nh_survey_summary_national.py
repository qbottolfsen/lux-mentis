"""
08_nh_survey_summary_national.py
NH Survey Summary -- deficiency category totals per survey cycle.

Source: CMS Provider Data -- NH Survey Summary
  Dataset:      tbry-pc2d
  Distribution: 23d16001-bbf2-58b9-909c-ec21dc8c8877

This dataset aggregates raw deficiency citations into per-survey totals
grouped by regulatory category. Each row = one survey cycle for one facility.
Three cycles are reported per facility (current + 2 prior years).

Category columns (deficiency counts):
  Abuse/Neglect/Exploitation  -- highest accountability signal
  Quality of Life             -- resident comfort + dignity
  Resident Assessment         -- MDS accuracy and care planning
  Nursing/Physician Services  -- clinical oversight
  Resident Rights             -- autonomy and grievance
  Nutrition/Dietary           -- food safety and hydration
  Pharmacy Service            -- medication management
  Environmental               -- physical plant conditions
  Administration              -- governance and staffing policy
  Infection Control           -- NHSN-related practices
  Emergency Preparedness      -- disaster readiness

Plus fire safety subcategories.

This dataset cross-validates the raw deficiency dataset (nh_health_deficiencies_national.csv)
-- category totals here should match citation counts there.

Output: output_reference/nh_survey_summary_national.csv

Pre-registered assertions:
  National rows:  [30,000 -- 70,000]   (3 cycles × ~14-17K facilities)
  HI rows:        [100 -- 150]          (126 confirmed = 3 × 42)
  HI facilities:  [40 -- 44]            (unique CCNs in HI subset)
"""

import json, pathlib, sys, time, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "nh_survey_summary_national.csv"

DIST_ID  = "23d16001-bbf2-58b9-909c-ec21dc8c8877"
BASE_URL = f"https://data.cms.gov/provider-data/api/1/datastore/query/{DIST_ID}"
PAGE_SIZE = 1_000

NATIONAL_MIN = 30_000
NATIONAL_MAX = 70_000
HI_ROWS_MIN = 100
HI_ROWS_MAX = 150
HI_CCN_MIN  = 40
HI_CCN_MAX  = 44


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


print("NH Survey Summary -- national deficiency category totals")
print(f"Distribution: {DIST_ID}")
print()

probe = fetch_page(json.dumps({"limit": 1, "offset": 0}).encode())
total_count = probe.get("count", "?")
raw_cols = list(probe["results"][0].keys()) if probe.get("results") else []
print(f"Reported count: {total_count:,}" if isinstance(total_count, int)
      else f"Reported count: {total_count}")
print(f"Columns ({len(raw_cols)}): {raw_cols[:6]} ...")
print()

all_raw_cols = raw_cols
print("All columns:")
for c in all_raw_cols:
    print(f"  {c}")
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
    "ccn":   find_col(raw_cols, "cms_certification_number", required=False) or find_col(raw_cols, "ccn"),
    "name":  find_col(raw_cols, "provider_name", required=False),
    "state": find_col(raw_cols, "state"),
    "cycle": find_col(raw_cols, "cycle"),
    "date":  find_col(raw_cols, "survey_date", required=False) or find_col(raw_cols, "date"),
    # Category deficiency counts
    "cat_abuse":    find_col(raw_cols, "abuse"),
    "cat_qol":      find_col(raw_cols, "quality_of_life", required=False) or find_col(raw_cols, "qol"),
    "cat_assess":   find_col(raw_cols, "resident_assessment", required=False) or find_col(raw_cols, "assessment"),
    "cat_nursing":  find_col(raw_cols, "nursing"),
    "cat_rights":   find_col(raw_cols, "resident_rights", required=False) or find_col(raw_cols, "rights"),
    "cat_nutrition":find_col(raw_cols, "nutrition"),
    "cat_pharmacy": find_col(raw_cols, "pharmacy"),
    "cat_environ":  find_col(raw_cols, "environmental", required=False) or find_col(raw_cols, "environ"),
    "cat_admin":    find_col(raw_cols, "administration"),
    "cat_infection":find_col(raw_cols, "infection_control", required=False) or find_col(raw_cols, "infection"),
    "cat_emergency":find_col(raw_cols, "emergency_preparedness", required=False) or find_col(raw_cols, "emergency"),
    "cat_fire_total":find_col(raw_cols, "fire_safety_total", required=False) or find_col(raw_cols, "fire"),
    "total_health": find_col(raw_cols, "total_health", required=False) or find_col(raw_cols, "health_total"),
    "total_fire":   find_col(raw_cols, "total_fire", required=False) or find_col(raw_cols, "fire_total"),
}

print("Column mapping:")
for k, v in COL.items():
    print(f"  {k:<20} {v or 'NOT FOUND'}")
print()

# Fetch all pages
print("Fetching all survey summary rows ...")
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
    print(f"  Page {page:3}: offset={offset:6,}  total={len(all_rows):,}")
    if len(rows) < PAGE_SIZE:
        break
    offset += PAGE_SIZE
    time.sleep(0.5)

print(f"Fetched {len(all_rows):,} rows")
print()


def g(row, key):
    col = COL.get(key)
    return str(row.get(col, "")).strip() if col else ""


def safe_int(v):
    try:
        return int(str(v).strip()) if v not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


# Build normalized output -- keep all raw columns, add computed total
out = []
for r in all_rows:
    # Compute total health deficiencies from category sums if total column missing
    cat_vals = [safe_int(g(r, k)) for k in
                ["cat_abuse","cat_qol","cat_assess","cat_nursing","cat_rights",
                 "cat_nutrition","cat_pharmacy","cat_environ","cat_admin",
                 "cat_infection","cat_emergency"]]
    computed_total = sum(v for v in cat_vals if v is not None) if any(v is not None for v in cat_vals) else None

    row_out = {k: str(v).strip() for k, v in r.items()}
    row_out["computed_health_total"] = "" if computed_total is None else computed_total
    out.append(row_out)

df = pd.DataFrame(out)


# ── Assertions ─────────────────────────────────────────────────────────────────

print("Assertions ...")

total = len(df)
if not (NATIONAL_MIN <= total <= NATIONAL_MAX):
    raise AssertionError(f"FAILED: {total:,} rows outside [{NATIONAL_MIN:,}, {NATIONAL_MAX:,}]")
print(f"  PASS: {total:,} national rows")

state_col = COL["state"]
if state_col:
    hi = df[df[state_col] == "HI"]
    if not (HI_ROWS_MIN <= len(hi) <= HI_ROWS_MAX):
        raise AssertionError(f"FAILED: HI rows {len(hi)} outside [{HI_ROWS_MIN}, {HI_ROWS_MAX}]")
    print(f"  PASS: {len(hi)} HI survey rows")

    ccn_col = COL["ccn"]
    if ccn_col:
        hi_ccns = hi[ccn_col].nunique()
        if not (HI_CCN_MIN <= hi_ccns <= HI_CCN_MAX):
            raise AssertionError(f"FAILED: {hi_ccns} unique HI CCNs outside [{HI_CCN_MIN}, {HI_CCN_MAX}]")
        print(f"  PASS: {hi_ccns} unique HI facilities")


# ── HI Summary ─────────────────────────────────────────────────────────────────

if state_col and len(hi) > 0:
    print()
    ccn_c    = COL.get("ccn")
    name_c   = COL.get("name")
    cycle_c  = COL.get("cycle")
    abuse_c  = COL.get("cat_abuse")
    infect_c = COL.get("cat_infection")
    total_c  = COL.get("total_health") or "computed_health_total"

    # Facilities with any abuse/neglect citations
    if abuse_c:
        hi_abuse = hi[pd.to_numeric(hi[abuse_c], errors="coerce") > 0]
        print(f"HI facilities with abuse/neglect deficiencies:")
        if len(hi_abuse) > 0:
            for c in [ccn_c, name_c, cycle_c, abuse_c, total_c]:
                if c not in hi_abuse.columns:
                    hi_abuse = hi_abuse.copy()
            print(hi_abuse[[c for c in [ccn_c, name_c, cycle_c, abuse_c, total_c] if c and c in hi_abuse.columns]].to_string(index=False))
        else:
            print("  None in current cycles")

    # Facilities with highest total deficiency burden
    print()
    if total_c in hi.columns:
        hi_burden = hi.copy()
        hi_burden["_sort"] = pd.to_numeric(hi_burden[total_c], errors="coerce")
        hi_burden = hi_burden.nlargest(10, "_sort")
        display_c = [c for c in [ccn_c, name_c, cycle_c, abuse_c, infect_c, total_c] if c and c in hi_burden.columns]
        print("Top 10 HI surveys by total health deficiency count:")
        print(hi_burden[display_c].to_string(index=False))


# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(df):,}  Cols: {len(df.columns)}")
print()
print("Join keys:")
print("  ccn  -->  facility_master_national.csv")
print("  ccn  -->  nh_health_deficiencies_national.csv (cross-validates category totals)")
print("  ccn  -->  nh_provider_info_national.csv (cycle 1 count used in 5-star)")
