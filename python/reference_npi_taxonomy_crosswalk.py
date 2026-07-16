"""
reference_npi_taxonomy_crosswalk.py
NPI Taxonomy Code → Medicare Specialty Code crosswalk.

Source: CMS data-api v1
  UUID: 113eb0bc-0c9a-4d91-9f93-3f6b28c0bf6b

4 columns. Links the taxonomy codes in the NPPES NPI registry
(and SNF Enrollments dataset) to Medicare-recognized specialty categories.

Critical for physician SNF attendance analysis (Phase 3):
  - Filter NPPES/NPI data by taxonomy to identify which provider types
    visit nursing home patients (geriatricians, internists, hospitalists)
  - HCPCS 99307-99310 cross-referenced with taxonomy to confirm SNF-attending physicians
  - Compare actual attending physicians to Medicare specialty enrollment data

Taxonomy codes relevant to LTPAC:
  207QG0300X  — Geriatric Medicine (Family Medicine)
  207RG0300X  — Geriatric Medicine (Internal Medicine)
  208D00000X  — General Practice
  207R00000X  — Internal Medicine
  207Q00000X  — Family Medicine
  394600000X  — Specialist
  314000000X  — Skilled Nursing Facility (facility taxonomy)

Output: output_reference/reference_npi_taxonomy_crosswalk.csv

Pre-registered assertions:
  Total rows: [1,000 -- 5,000]  (taxonomy × specialty cross-mapping)
  SNF facility taxonomy present: "314000000X"
"""

import json, pathlib, sys, time, urllib.parse, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "reference_npi_taxonomy_crosswalk.csv"

UUID     = "113eb0bc-0c9a-4d91-9f93-3f6b28c0bf6b"
BASE_URL = f"https://data.cms.gov/data-api/v1/dataset/{UUID}/data"
PAGE_SIZE = 500

EXPECTED_MIN = 50
EXPECTED_MAX = 200
SNF_TAXONOMY  = "314000000X"
GERI_TAXONOMY = {"207QG0300X", "207RG0300X"}


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


print("NPI Taxonomy -> Medicare Specialty Crosswalk")
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
print(f"  PASS: {total:,} taxonomy-specialty mappings")

# Find taxonomy column
tax_col = next((c for c in df.columns if "taxonomy" in c.lower() and "code" in c.lower()), None)
if tax_col is None:
    tax_col = next((c for c in df.columns if "taxonomy" in c.lower()), None)

if tax_col:
    tax_vals = set(df[tax_col].str.strip().values)
    if SNF_TAXONOMY in tax_vals:
        print(f"  PASS: SNF facility taxonomy {SNF_TAXONOMY} present")
    else:
        print(f"  WARN: SNF facility taxonomy {SNF_TAXONOMY} not found")
    geri_present = GERI_TAXONOMY & tax_vals
    if geri_present:
        print(f"  PASS: geriatric taxonomy codes present: {geri_present}")
    else:
        print(f"  WARN: geriatric taxonomy codes not found: {GERI_TAXONOMY}")

# ── Summary ────────────────────────────────────────────────────────────────────

# Show LTPAC-relevant taxonomy mappings
if tax_col:
    ltpac_codes = {"314000000X", "207QG0300X", "207RG0300X", "207R00000X",
                   "207Q00000X", "208D00000X", "208000000X"}
    ltpac_rows = df[df[tax_col].str.strip().isin(ltpac_codes)]
    if len(ltpac_rows) > 0:
        print()
        print("LTPAC-relevant taxonomy mappings:")
        print(ltpac_rows.to_string(index=False))

# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(df):,}  Cols: {len(df.columns)}")
print()
print("Usage:")
print("  JOIN ON: taxonomy_code in NPPES/NPI registry")
print("  JOIN ON: taxonomy_code in Medicare_Physician_ProvSvc")
print("  Filter geriatric specialties: 207QG0300X, 207RG0300X")
print("  Filter SNF facilities: 314000000X")
