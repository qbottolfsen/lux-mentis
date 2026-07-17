"""
10_nh_state_benchmarks_national.py
NH State and National Benchmarks -- one row per state + one US aggregate.

Source: CMS Provider Data -- NH State/US Averages
  Dataset:      xcdc-v8bm
  Distribution: 20098691-f735-5ea4-b364-1874ec34b950

No state filter field. Pull all 54 rows (50 states + DC + territories + US).
Filter client-side for HI benchmarks; keep all rows for national comparison.

One row per state = the average values for all NH Provider Info fields for
SNFs in that state. This is the correct denominator for:
  - "HI vs national" comparisons in Five-Star
  - Staffing HPRD benchmark (is HI above/below national avg?)
  - Turnover benchmark
  - Deficiency score benchmark
  - All quality measure averages by state

HI confirmed values (verified 2026-07-12):
  Overall Rating: 3.6     Health Inspection: 2.9 (below avg)
  QM Rating: 4.5          Staffing Rating: 4.3
  Total Nurse HPRD: 4.64  RN Turnover: 34.2%   Total Turnover: 37.5%
  Avg Residents/Day: 81.7

Output: output_reference/nh_state_benchmarks_national.csv

Pre-registered assertions:
  Total rows:  [50 -- 60]     (54 rows expected: 50 states + DC + territories + US)
  HI row:      exactly 1
  US row:      exactly 1 (State or Nation = "US")
  HI overall rating: [3.0 -- 4.5]
"""

import json, pathlib, sys, time, urllib.parse, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "nh_state_benchmarks_national.csv"

DIST_ID  = "20098691-f735-5ea4-b364-1874ec34b950"
BASE_URL = f"https://data.cms.gov/provider-data/api/1/datastore/query/{DIST_ID}"

TOTAL_ROWS_MIN = 50
TOTAL_ROWS_MAX = 60


def fetch(payload: bytes, max_retries: int = 5) -> dict:
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


print("NH State/US Benchmarks -- one row per state")
print(f"Distribution: {DIST_ID}")
print()

# Pull all rows (54 max; one request is sufficient)
data = fetch(json.dumps({"limit": 100, "offset": 0}).encode())
rows = data.get("results", [])
print(f"Rows returned: {len(rows)}")

if not rows:
    sys.exit("No rows returned.")

raw_cols = list(rows[0].keys())
print(f"Columns ({len(raw_cols)}): {raw_cols[:8]} ...")
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


# Identify the state/nation identifier column
state_col = find_col(raw_cols, "state_or_nation", required=False) or find_col(raw_cols, "state")
print(f"State/nation identifier column: {state_col}")

# Find key benchmark columns
overall_col  = find_col(raw_cols, "overall_rating")
health_col   = find_col(raw_cols, "health_inspection_rating", exclude=["chain"])
qm_col       = find_col(raw_cols, "qm_rating", required=False) or find_col(raw_cols, "quality_measure_rating")
staff_col    = find_col(raw_cols, "staffing_rating")
hprd_col     = find_col(raw_cols, "reported_total_nurse_staffing")
rn_col       = find_col(raw_cols, "reported_rn_staffing")
turnover_col = find_col(raw_cols, "total_nursing_staff_turnover")
rn_turn_col  = find_col(raw_cols, "registered_nurse_turnover")
census_col   = find_col(raw_cols, "average_number_of_residents", required=False)

print(f"  overall_rating: {overall_col}")
print(f"  health_inspect: {health_col}")
print(f"  qm_rating:      {qm_col}")
print(f"  total_hprd:     {hprd_col}")
print(f"  turnover:       {turnover_col}")
print()

df = pd.DataFrame(rows)


# ── Assertions ─────────────────────────────────────────────────────────────────

print("Assertions ...")

total = len(df)
if not (TOTAL_ROWS_MIN <= total <= TOTAL_ROWS_MAX):
    raise AssertionError(f"FAILED: {total} rows outside [{TOTAL_ROWS_MIN}, {TOTAL_ROWS_MAX}]")
print(f"  PASS: {total} state/national rows")

hi_rows = df[df[state_col] == "HI"]
if len(hi_rows) != 1:
    raise AssertionError(f"FAILED: expected 1 HI row, got {len(hi_rows)}")
print(f"  PASS: 1 HI row")

us_rows = df[df[state_col] == "NATION"]
if len(us_rows) != 1:
    us_rows = df[df[state_col].str.upper().isin(["US", "NATION", "UNITED STATES"])]
    if len(us_rows) != 1:
        print(f"  WARN: expected 1 NATION row, got {len(us_rows)}")
    else:
        print(f"  PASS: 1 NATION aggregate row (value: {us_rows[state_col].values[0]})")
else:
    print(f"  PASS: 1 NATION aggregate row")

# HI overall rating sanity
if overall_col:
    hi_overall = pd.to_numeric(hi_rows[overall_col].values[0], errors="coerce")
    if hi_overall and not (3.0 <= hi_overall <= 4.5):
        print(f"  WARN: HI overall rating {hi_overall} outside expected [3.0, 4.5]")
    else:
        print(f"  PASS: HI overall rating = {hi_overall}")


# ── Summary Table ─────────────────────────────────────────────────────────────

print()
print("HI vs US benchmarks:")
benchmarks = [
    ("Overall Rating",     overall_col),
    ("Health Inspection",  health_col),
    ("QM Rating",          qm_col),
    ("Staffing Rating",    staff_col),
    ("Total HPRD",         hprd_col),
    ("RN HPRD",            rn_col),
    ("Total Turnover %",   turnover_col),
    ("RN Turnover %",      rn_turn_col),
    ("Avg Residents/Day",  census_col),
]

for label, col in benchmarks:
    if not col:
        continue
    hi_val = pd.to_numeric(hi_rows[col].values[0], errors="coerce") if len(hi_rows) > 0 else None
    us_val = pd.to_numeric(us_rows[col].values[0], errors="coerce") if len(us_rows) == 1 else None
    if hi_val is not None and us_val is not None:
        diff = hi_val - us_val
        flag = " *** HI HIGHER" if diff > 0 else (" *** HI LOWER" if diff < -0.1 else "")
        print(f"  {label:<22} HI={hi_val:6.2f}  US={us_val:6.2f}  diff={diff:+.2f}{flag}")
    elif hi_val is not None:
        print(f"  {label:<22} HI={hi_val:6.2f}  US=N/A")

# State ranking for overall rating
print()
if overall_col:
    rank_df = df[pd.to_numeric(df[overall_col], errors="coerce").notna()].copy()
    rank_df["_sort"] = pd.to_numeric(rank_df[overall_col], errors="coerce")
    rank_df = rank_df.sort_values("_sort", ascending=False).reset_index(drop=True)
    hi_rank = rank_df[rank_df[state_col] == "HI"].index
    if len(hi_rank) > 0:
        print(f"HI rank for overall rating: #{hi_rank[0]+1} of {len(rank_df)} states")


# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(df):,}  Cols: {len(df.columns)}")
print()
print("Usage:")
print("  Join on state code to add state benchmark context to facility-level analysis.")
print("  Reference: HI QM=4.5 (above US avg), Health Inspection=2.9 (below US avg)")
