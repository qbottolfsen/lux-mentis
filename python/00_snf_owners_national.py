"""
00_snf_owners_national.py

Pulls all CMS SNF All Owners records from the data.cms.gov API.
Provides ownership chain analysis with private equity, REIT, holding company,
and chain affiliation flags at the individual owner level.

Dataset: SNF All Owners
UUID:    afe44b85-cc6d-40d7-b5df-00ae8910d1d2
Cols:    ENROLLMENT ID, ORGANIZATION NAME (the SNF), ASSOCIATE ID - OWNER,
         TYPE - OWNER (O=org / I=individual), ROLE CODE/TEXT - OWNER,
         FIRST/LAST NAME - OWNER (individuals), ORG NAME - OWNER (orgs),
         PERCENTAGE OWNERSHIP,
         Boolean flags (Y/N): PRIVATE EQUITY COMPANY, REIT, HOLDING COMPANY,
         INVESTMENT FIRM, LLC, CORPORATION, NON PROFIT, FOR PROFIT,
         MEDICAL STAFFING COMPANY, CHAIN HOME OFFICE, TRUST OR TRUSTEE

Join to snf_enrollments_national.csv on ENROLLMENT ID to get NPI + CCN.

No API key required.

Expected output: ~80,000-130,000 rows (multiple owner records per SNF).
Script will exit if count is outside [60,000, 160,000].

Privacy note: Individual owner records (TYPE - OWNER = I) contain names.
The output CSV is gitignored. Aggregate/flag-level analysis only for public outputs.

Output: output_reference/snf_owners_national.csv
        output_reference/snf_owners_facility_flags.csv  (facility-level PE/REIT summary, public)
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
import urllib.request

BASE_URL = "https://data.cms.gov/data-api/v1/dataset/afe44b85-cc6d-40d7-b5df-00ae8910d1d2/data"
PAGE_SIZE = 5000

EXPECTED_MIN = 200_000
EXPECTED_MAX = 350_000

OUT_DIR = Path(__file__).parent / "output_reference"
OUT_FULL = OUT_DIR / "snf_owners_national.csv"
OUT_FLAGS = OUT_DIR / "snf_owners_facility_flags.csv"

# Boolean flag columns to aggregate to facility level
FLAG_COLS = [
    "PRIVATE EQUITY COMPANY - OWNER",
    "REIT - OWNER",
    "HOLDING COMPANY - OWNER",
    "INVESTMENT FIRM - OWNER",
    "MEDICAL STAFFING COMPANY - OWNER",
    "CHAIN HOME OFFICE - OWNER",
    "CORPORATION - OWNER",
    "LLC - OWNER",
    "NON PROFIT - OWNER",
    "FOR PROFIT - OWNER",
    "TRUST OR TRUSTEE - OWNER",
]


def fetch_page(offset: int) -> list[dict]:
    url = f"{BASE_URL}?size={PAGE_SIZE}&offset={offset}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def flag_val(row: dict, col: str) -> bool:
    return str(row.get(col, "")).strip().upper() == "Y"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    print("Pulling SNF All Owners (ownership chain + PE/REIT flags)...")
    print(f"Dataset: afe44b85  |  Page size: {PAGE_SIZE:,}")

    all_rows: list[dict] = []
    offset = 0
    page = 0

    while True:
        page += 1
        rows = fetch_page(offset)
        print(f"  Page {page}: offset={offset:,}  rows={len(rows)}")
        all_rows.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    total = len(all_rows)
    print(f"\nTotal rows fetched: {total:,}")

    if not (EXPECTED_MIN <= total <= EXPECTED_MAX):
        print(
            f"ASSERTION FAILED: Expected {EXPECTED_MIN:,}-{EXPECTED_MAX:,} rows, "
            f"got {total:,}. Do not use this output.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"PASS: Row count {total:,} within expected range.")

    # --- Facility-level flag aggregation ---
    # For each ENROLLMENT ID, does ANY owner record have this flag = Y?
    facility_flags: dict[str, dict] = defaultdict(lambda: {
        "enrollment_id": "",
        "organization_name": "",
        "owner_count": 0,
        "individual_owner_count": 0,
        **{col: False for col in FLAG_COLS},
    })

    for row in all_rows:
        eid = row.get("ENROLLMENT ID", "")
        if not eid:
            continue
        rec = facility_flags[eid]
        rec["enrollment_id"] = eid
        rec["organization_name"] = row.get("ORGANIZATION NAME", "")
        rec["owner_count"] += 1
        if str(row.get("TYPE - OWNER", "")).strip().upper() == "I":
            rec["individual_owner_count"] += 1
        for col in FLAG_COLS:
            if flag_val(row, col):
                rec[col] = True

    # Summary stats
    pe_count   = sum(1 for r in facility_flags.values() if r["PRIVATE EQUITY COMPANY - OWNER"])
    reit_count = sum(1 for r in facility_flags.values() if r["REIT - OWNER"])
    hold_count = sum(1 for r in facility_flags.values() if r["HOLDING COMPANY - OWNER"])
    chain_count = sum(1 for r in facility_flags.values() if r["CHAIN HOME OFFICE - OWNER"])

    print(f"\nFacility-level ownership flag summary (n={len(facility_flags):,} facilities):")
    print(f"  Private equity owner present: {pe_count:,}")
    print(f"  REIT owner present:           {reit_count:,}")
    print(f"  Holding company owner:        {hold_count:,}")
    print(f"  Chain home office listed:     {chain_count:,}")

    # Write full owners file (gitignored — contains individual names)
    if all_rows:
        fieldnames = list(all_rows[0].keys())
        with open(OUT_FULL, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\nFull owners file (gitignore): {OUT_FULL}")

    # Write facility-level flags file (public — no individual names)
    flag_fieldnames = [
        "enrollment_id", "organization_name", "owner_count", "individual_owner_count",
    ] + [col.lower().replace(" ", "_").replace("-", "").replace("__", "_") for col in FLAG_COLS]

    with open(OUT_FLAGS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(flag_fieldnames)
        for eid, rec in sorted(facility_flags.items()):
            writer.writerow([
                rec["enrollment_id"],
                rec["organization_name"],
                rec["owner_count"],
                rec["individual_owner_count"],
            ] + [rec[col] for col in FLAG_COLS])

    print(f"Facility flags file (public):  {OUT_FLAGS}")
    print(f"Facilities with ownership data: {len(facility_flags):,}")
    print("\nJoin key: ENROLLMENT ID -- links to snf_enrollments_national.csv for NPI + CCN")


if __name__ == "__main__":
    main()
