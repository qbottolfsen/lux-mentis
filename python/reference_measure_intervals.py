"""
reference_measure_intervals.py
QM measure code --> data collection interval reference table.

Source: CMS Provider Data -- NH Data Collection Intervals
  Dataset:      qmdc-9999
  Distribution: 6dd8544e-619d-5256-9990-7321f62d55a3
  No state filter; national reference only

Decodes the timing context for every MDS QM and Claims QM measure code.
Required by nh_quality_measures_national.py to interpret measure periods.

Output: output_reference/reference_measure_intervals.csv
"""

import json, pathlib, sys, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "reference_measure_intervals.csv"

DIST_ID  = "6dd8544e-619d-5256-9990-7321f62d55a3"
BASE_URL = f"https://data.cms.gov/provider-data/api/1/datastore/query/{DIST_ID}"

EXPECTED_MIN = 10
EXPECTED_MAX = 500


def fetch_all() -> list:
    payload = json.dumps({"limit": 1_000, "offset": 0}).encode()
    req = urllib.request.Request(
        BASE_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    print(f"  Reported count: {data.get('count', '?')}")
    return data.get("results", [])


print("QM Measure Code / Data Collection Interval Reference")
print(f"Source distribution: {DIST_ID}")
print()

rows = fetch_all()
print(f"  Rows received: {len(rows)}")

if not rows:
    sys.exit("No data returned")

raw_cols = list(rows[0].keys())
print(f"  Columns ({len(raw_cols)}): {raw_cols}")
print()

# Write as-is — small reference table, preserve all columns
df = pd.DataFrame(rows)

n = len(df)
if not (EXPECTED_MIN <= n <= EXPECTED_MAX):
    raise AssertionError(f"FAILED: {n} rows outside [{EXPECTED_MIN}, {EXPECTED_MAX}]")
print(f"PASS: {n} measure interval records")
print()
print(df.to_string(index=False))

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)
print(f"\nOutput: {OUTPUT_FILE}  ({n} rows, {len(df.columns)} cols)")
print("Join key: measure_code  -->  nh_quality_measures_national.py")
