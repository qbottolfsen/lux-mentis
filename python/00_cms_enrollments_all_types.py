"""
00_cms_enrollments_all_types.py
CMS Medicare enrollment NPI+CCN crosswalk -- all provider types, national.

Combines enrollment records from 6 provider type datasets into a single
reference crosswalk. Join on NPI or CCN across any CMS dataset.

Provider types included:
  SNF      Skilled Nursing Facility        (from existing snf_enrollments_national.csv)
  HOSPITAL Hospital (all subtypes)         UUID: f6f6505c
  HOSPICE  Hospice                         UUID: 25704213
  HHA      Home Health Agency              UUID: 15f64ab4
  FQHC     Federally Qualified Health Ctr  UUID: 4bcae866
  RHC      Rural Health Clinic             UUID: 3b7e7659

Output: output_reference/cms_enrollments_all_types.csv
Join:   npi (NPI) or ccn (CCN) -- both preserved from source
Schema: enrollment_id, npi, ccn, org_name, dba_name, enrollment_state,
        address_state, zip, provider_type_code, provider_type_text,
        proprietary_nonprofit, provider_type_label

Note: Hospital dataset has additional SUBGROUP-* columns (swing bed, CAH, etc.)
not present in other datasets; those columns are dropped for the unified output.
Pull Hospital Enrollments separately to access subgroup flags.

Privacy: no individual names -- all organizational records. Publishable.
"""

import urllib.request, json, csv, time, pathlib

OUTPUT_DIR = pathlib.Path(__file__).parent / "output_reference"
SNF_EXISTING = OUTPUT_DIR / "snf_enrollments_national.csv"
OUTPUT_FILE  = OUTPUT_DIR / "cms_enrollments_all_types.csv"

PAGE_SIZE = 5_000

# UUID, label, expected national range [min, max]
DATASETS = [
    ("f6f6505c-e8b0-4d57-b258-e2b94133aaf2", "HOSPITAL", 4_000,  15_000),
    ("25704213-e833-4b8b-9dbc-58dd17149209", "HOSPICE",  3_000,  10_000),
    ("15f64ab4-3172-4a27-b589-ebd67a6d28aa", "HHA",      8_000,  20_000),
    ("4bcae866-3411-439a-b762-90a6187c194b", "FQHC",      8_000,  18_000),  # site-level
    ("3b7e7659-067e-41ea-8e36-f9ee2036e1f6", "RHC",      2_500,  18_000),  # site-level
]

TOTAL_MIN = 54_900  # 95% of 57,767 confirmed 2026-07-22
TOTAL_MAX = 61_000

# Normalized output column names
OUT_COLS = [
    "provider_type_label",
    "enrollment_id",
    "npi",
    "ccn",
    "org_name",
    "dba_name",
    "enrollment_state",
    "address_state",
    "zip",
    "provider_type_code",
    "provider_type_text",
    "proprietary_nonprofit",
    "org_type_structure",
]

# Map source column names → output column names
# Hospital uses 'PROPRIETARY NONPROFIT' (space); others use 'PROPRIETARY_NONPROFIT'
COL_MAP = {
    "ENROLLMENT ID":          "enrollment_id",
    "NPI":                    "npi",
    "CCN":                    "ccn",
    "ORGANIZATION NAME":      "org_name",
    "DOING BUSINESS AS NAME": "dba_name",
    "ENROLLMENT STATE":       "enrollment_state",
    "STATE":                  "address_state",
    "ZIP CODE":               "zip",
    "PROVIDER TYPE CODE":     "provider_type_code",
    "PROVIDER TYPE TEXT":     "provider_type_text",
    "PROPRIETARY_NONPROFIT":  "proprietary_nonprofit",
    "PROPRIETARY NONPROFIT":  "proprietary_nonprofit",  # Hospital variant
    "ORGANIZATION TYPE STRUCTURE": "org_type_structure",
}


def fetch_all(uuid: str, label: str) -> list[dict]:
    base = f"https://data.cms.gov/data-api/v1/dataset/{uuid}/data"
    rows: list[dict] = []
    offset = 0
    page_num = 0
    while True:
        page_num += 1
        url = f"{base}?size={PAGE_SIZE}&offset={offset}&sort=ENROLLMENT+ID"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        page = json.loads(urllib.request.urlopen(req, timeout=90).read())
        if not page:
            break
        rows.extend(page)
        print(f"  {label:8}  page {page_num:2}: offset={offset:6,}  rows={len(page):,}  total={len(rows):,}")
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.3)
    return rows


def normalize(raw: list[dict], label: str) -> list[dict]:
    out = []
    for r in raw:
        row = {"provider_type_label": label}
        for src_col, out_col in COL_MAP.items():
            if src_col in r and out_col not in row:
                row[out_col] = r[src_col]
        # Fill any missing out cols with blank
        for col in OUT_COLS:
            row.setdefault(col, "")
        out.append({c: row[c] for c in OUT_COLS})
    return out


print("CMS Medicare enrollment crosswalk -- all provider types, national")
print(f"Output: {OUTPUT_FILE}")
print()

combined: list[dict] = []

# --- Load existing SNF enrollment CSV ---
print("Loading SNF from existing snf_enrollments_national.csv ...")
snf_rows_raw: list[dict] = []
with open(SNF_EXISTING, encoding="utf-8") as f:
    snf_rows_raw = list(csv.DictReader(f))
snf_rows = normalize(snf_rows_raw, "SNF")
combined.extend(snf_rows)
print(f"  SNF: {len(snf_rows):,} rows loaded from file")
if not (13_700 <= len(snf_rows) <= 16_000):  # 95% of 14,425 confirmed 2026-07-22
    raise AssertionError(f"SNF row count {len(snf_rows):,} outside [13,700, 16,000]")
print()

# --- Pull each API dataset ---
for uuid, label, exp_min, exp_max in DATASETS:
    print(f"Pulling {label} ({uuid[:8]}) ...")
    raw = fetch_all(uuid, label)
    n = len(raw)
    if not (exp_min <= n <= exp_max):
        raise AssertionError(f"ASSERTION FAILED: {label} row count {n:,} outside [{exp_min:,}, {exp_max:,}]")
    print(f"  PASS: {n:,} rows -- within expected range")
    normed = normalize(raw, label)
    combined.extend(normed)
    print()

total = len(combined)
print(f"Total rows (all types): {total:,}")
if not (TOTAL_MIN <= total <= TOTAL_MAX):
    raise AssertionError(f"ASSERTION FAILED: total {total:,} outside [{TOTAL_MIN:,}, {TOTAL_MAX:,}]")
print("PASS: Total count within expected range.")
print()

# Type summary
type_counts: dict[str, int] = {}
for r in combined:
    t = r["provider_type_label"]
    type_counts[t] = type_counts.get(t, 0) + 1
print("Rows by provider type:")
for t in ["SNF", "HOSPITAL", "HOSPICE", "HHA", "FQHC", "RHC"]:
    n = type_counts.get(t, 0)
    print(f"  {t:8}  {n:6,}")
print()

# Hawaii spot-check (address_state=HI)
hi_rows = [r for r in combined if r.get("address_state", "") == "HI"]
print(f"Hawaii rows (address_state=HI): {len(hi_rows):,}")
hi_by_type = {}
for r in hi_rows:
    t = r["provider_type_label"]
    hi_by_type[t] = hi_by_type.get(t, 0) + 1
for t, n in sorted(hi_by_type.items()):
    print(f"  {t:8}  {n:3}")
print()

# Write output
OUTPUT_DIR.mkdir(exist_ok=True)
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=OUT_COLS)
    writer.writeheader()
    writer.writerows(combined)

print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {total:,}")
print(f"Cols:   {len(OUT_COLS)}")
print()
print("Join keys:")
print("  npi  -- National Provider Identifier (join to PBJ, NPPES, etc.)")
print("  ccn  -- CMS Certification Number (join to POS, QM, VBP, cost reports)")
print("  enrollment_id -- CMS enrollment ID (join to All Owners datasets)")
