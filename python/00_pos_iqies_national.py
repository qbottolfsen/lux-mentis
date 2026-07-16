"""
00_pos_iqies_national.py
Provider of Services (iQIES) -- all Medicare/Medicaid certified providers, national.

This is a general reference layer, not SNF-specific.
Coverage: ALL provider types -- SNF, hospital, HHA, hospice, dialysis, FQHC, RHC, etc.

Join key:  prvdr_num (CCN)
State:     state_cd
Type:      gnrl_fac_type_cd (distribution printed at run time -- codes in CMS POS data dictionary)
Active:    pgm_trmntn_cd == "00"

Source: CMS data.cms.gov data-api v1
UUID:   086e48c4-87a6-4be1-8823-29e8da8f225b
Cols:   182 (confirmed 2026-07-15)
Docs:   https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/provider-of-services-file-hospital-non-hospital-facilities

NOTE: A 473-col historical version also exists (UUID 8ba0f9b4, field name PRVDR_CTGRY_CD).
That version includes CHOW_DT and CHOW_CNT per facility. Use it for ownership history analysis.
This 182-col version is preferred for the current-state reference layer.
"""

import urllib.request, json, csv, time, pathlib

BASE_URL = (
    "https://data.cms.gov/data-api/v1/dataset"
    "/086e48c4-87a6-4be1-8823-29e8da8f225b/data"
)
PAGE_SIZE = 5_000
EXPECTED_MIN = 40_000
EXPECTED_MAX = 150_000
HI_MIN = 100
HI_MAX = 500

OUTPUT_DIR = pathlib.Path(__file__).parent / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "pos_iqies_national.csv"


def fetch_page(offset: int) -> list[dict]:
    url = f"{BASE_URL}?size={PAGE_SIZE}&offset={offset}&sort=prvdr_num"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


print("Pulling Provider of Services (iQIES) -- all provider types, national")
print(f"UUID: 086e48c4  |  Page size: {PAGE_SIZE:,}")
print()

rows: list[dict] = []
offset = 0
page_num = 0

while True:
    page_num += 1
    page = fetch_page(offset)
    if not page:
        break
    rows.extend(page)
    print(f"  Page {page_num}: offset={offset:,}  rows={len(page):,}  running total={len(rows):,}")
    if len(page) < PAGE_SIZE:
        break
    offset += PAGE_SIZE
    time.sleep(0.3)

print()
total = len(rows)
print(f"Total rows fetched: {total:,}")

if total < EXPECTED_MIN or total > EXPECTED_MAX:
    raise AssertionError(
        f"ASSERTION FAILED: row count {total:,} outside expected range "
        f"[{EXPECTED_MIN:,}, {EXPECTED_MAX:,}] -- check UUID or update bounds"
    )
print("PASS: Row count within expected range.")
print()

# Hawaii spot-check
hi_rows = [r for r in rows if r.get("state_cd") == "HI"]
hi_n = len(hi_rows)
print(f"Hawaii rows (state_cd=HI): {hi_n:,}  (expect {HI_MIN}-{HI_MAX})")
if hi_n < HI_MIN or hi_n > HI_MAX:
    raise AssertionError(
        f"ASSERTION FAILED: HI row count {hi_n} outside expected range "
        f"[{HI_MIN}, {HI_MAX}]"
    )
print()

# Provider type distribution -- use to understand gnrl_fac_type_cd codes
print("Provider type distribution (gnrl_fac_type_cd) -- top 25:")
type_counts: dict[str, int] = {}
for r in rows:
    t = str(r.get("gnrl_fac_type_cd", ""))
    type_counts[t] = type_counts.get(t, 0) + 1
for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1])[:25]:
    print(f"  gnrl_fac_type_cd={t:6}  n={cnt:6,}")
print()

# Active vs terminated breakdown
print("Termination status (pgm_trmntn_cd):")
term_counts: dict[str, int] = {}
for r in rows:
    t = str(r.get("pgm_trmntn_cd", ""))
    term_counts[t] = term_counts.get(t, 0) + 1
for t, cnt in sorted(term_counts.items(), key=lambda x: -x[1]):
    label = "ACTIVE" if t == "00" else "terminated"
    print(f"  pgm_trmntn_cd={t!r:6}  {label:12}  n={cnt:6,}")
print()

# Hawaii breakdown by provider type
if hi_rows:
    print(f"Hawaii provider types (n={hi_n}):")
    hi_types: dict[str, int] = {}
    for r in hi_rows:
        t = str(r.get("gnrl_fac_type_cd", ""))
        hi_types[t] = hi_types.get(t, 0) + 1
    for t, cnt in sorted(hi_types.items(), key=lambda x: -x[1]):
        print(f"  gnrl_fac_type_cd={t:6}  n={cnt:3}")
    print()

# Write output -- all 182 columns, all provider types
OUTPUT_DIR.mkdir(exist_ok=True)
fieldnames = list(rows[0].keys()) if rows else []
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {total:,}")
print(f"Cols:   {len(fieldnames)}")
print()
print("Usage:")
print("  Join key:      prvdr_num (CCN)")
print("  Active filter: pgm_trmntn_cd == '00'")
print("  SNF filter:    gnrl_fac_type_cd == '7' (verify from distribution above)")
print("  State filter:  state_cd == 'HI'")
print()
print("To join to SNF Enrollments (for NPI):")
print("  pos.prvdr_num == snf_enrollments.CCN")
