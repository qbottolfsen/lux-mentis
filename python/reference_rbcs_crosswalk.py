"""
reference_rbcs_crosswalk.py
HCPCS → RBCS (Restructured BETOS Classification System) crosswalk.

Source: CMS data-api v1
  UUID: e3db6e56-149f-49ce-b374-40aecda2357b

17 columns. Maps every HCPCS code to its RBCS category for procedure-level
aggregation in physician SNF attendance analysis.

RBCS category structure:
  RBCS_Lvl1 / RBCS_Lvl2 / RBCS_Cat / RBCS_Subcat
  Relevant for SNF context:
    E&M Services → Office/Outpatient → 99307-99310 (SNF visits)
    Therapy Services → PT/OT/SLP codes
    Equipment → DME for post-acute residents

Required before running physician SNF attendance analysis (Phase 3).

Output: output_reference/reference_rbcs_crosswalk.csv

Pre-registered assertions:
  Total rows: [8,000 -- 15,000]  (HCPCS code universe updates annually)
  SNF visit codes present: 99307, 99308, 99309, 99310
"""

import json, pathlib, sys, time, urllib.parse, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "reference_rbcs_crosswalk.csv"

UUID     = "e3db6e56-149f-49ce-b374-40aecda2357b"
BASE_URL = f"https://data.cms.gov/data-api/v1/dataset/{UUID}/data"
PAGE_SIZE = 500

EXPECTED_MIN = 8_000
EXPECTED_MAX = 22_000
SNF_VISIT_CODES = {"99307", "99308", "99309", "99310"}


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


print("RBCS Crosswalk -- HCPCS to procedure category")
print(f"UUID: {UUID}")
print()

probe = fetch({"size": 2, "offset": 0})
if not probe:
    sys.exit("No rows returned.")
raw_cols = list(probe[0].keys())
print(f"Columns ({len(raw_cols)}): {raw_cols}")
print()

# Fetch all pages
print("Fetching all rows ...")
all_rows: list = list(probe)
offset = PAGE_SIZE
page = 1

while True:
    page += 1
    rows = fetch({"size": PAGE_SIZE, "offset": offset})
    if not rows:
        break
    all_rows.extend(rows)
    print(f"  Page {page:2}: offset={offset:6,}  total={len(all_rows):,}")
    if len(rows) < PAGE_SIZE:
        break
    offset += PAGE_SIZE
    time.sleep(0.2)

print(f"Fetched {len(all_rows):,} rows")
print()

df = pd.DataFrame(all_rows)

# ── Assertions ─────────────────────────────────────────────────────────────────

print("Assertions ...")

total = len(df)
if not (EXPECTED_MIN <= total <= EXPECTED_MAX):
    raise AssertionError(f"FAILED: {total:,} rows outside [{EXPECTED_MIN:,}, {EXPECTED_MAX:,}]")
print(f"  PASS: {total:,} HCPCS codes in RBCS")

# Find HCPCS code column
hcpcs_col = next((c for c in df.columns if "hcpcs" in c.lower()), None)
if hcpcs_col:
    present = set(df[hcpcs_col].str.strip().values) & SNF_VISIT_CODES
    missing = SNF_VISIT_CODES - present
    if missing:
        print(f"  WARN: SNF visit codes not found: {missing}")
    else:
        print(f"  PASS: all SNF visit codes present (99307-99310)")
else:
    print(f"  WARN: no HCPCS code column identified")

# ── Summary ────────────────────────────────────────────────────────────────────

# Find category column
cat_col = next((c for c in df.columns if "rbcs_cat" in c.lower() or "category" in c.lower()), None)
if cat_col:
    print()
    print(f"Top RBCS categories (by code count):")
    top = df[cat_col].value_counts().head(10)
    for k, v in top.items():
        print(f"  {k}: {v:,}")

# Show SNF visit codes
if hcpcs_col:
    snf_rows = df[df[hcpcs_col].str.strip().isin(SNF_VISIT_CODES)]
    if len(snf_rows) > 0:
        print()
        print("SNF E&M visit codes (99307-99310):")
        print(snf_rows.to_string(index=False))

# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(df):,}  Cols: {len(df.columns)}")
print()
print("Usage:")
print("  JOIN ON: HCPCS_Cd (or hcpcs_cd) in Physician_ProvSvc dataset")
print("  Filter by RBCS_Cat = 'Evaluation and Management' for SNF visits")
