"""
00_snf_enrollments_national.py

Pulls all CMS SNF Enrollment records from the data.cms.gov API.
This is the authoritative NPI + CCN crosswalk for national SNF analysis.

Dataset: SNF Enrollments
UUID:    5f2c306f-3b1c-42cd-b037-187b2ce22126
Cols:    NPI, CCN, ENROLLMENT ID, ORGANIZATION NAME, DOING BUSINESS AS NAME,
         PROPRIETARY_NONPROFIT (P=for-profit, N=non-profit),
         ORGANIZATION TYPE STRUCTURE, AFFILIATION ENTITY NAME/ID (chain),
         INCORPORATION DATE/STATE, ADDRESS LINE 1/2, CITY, STATE, ZIP CODE

No API key required.

Expected output: ~14,000-15,000 rows (all active SNF enrollments nationally).
Script will exit if count is outside [12,000, 18,000].

Output: output_reference/snf_enrollments_national.csv
"""

import csv
import json
import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://data.cms.gov/data-api/v1/dataset/5f2c306f-3b1c-42cd-b037-187b2ce22126/data"
PAGE_SIZE = 5000

EXPECTED_MIN = 12_000
EXPECTED_MAX = 18_000

OUT_DIR = Path(__file__).parent / "output_reference"
OUT_FILE = OUT_DIR / "snf_enrollments_national.csv"


def fetch_page(offset: int) -> list[dict]:
    url = f"{BASE_URL}?size={PAGE_SIZE}&offset={offset}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    print("Pulling SNF Enrollments (NPI + CCN national crosswalk)...")
    print(f"Dataset: 5f2c306f  |  Page size: {PAGE_SIZE:,}")

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
            f"ASSERTION FAILED: Expected {EXPECTED_MIN:,}–{EXPECTED_MAX:,} rows, "
            f"got {total:,}. Do not use this output.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"PASS: Row count {total:,} within expected range.")

    # State distribution spot-check
    from collections import Counter
    state_counts = Counter(r.get("STATE", "") for r in all_rows)
    top_states = state_counts.most_common(10)
    print("\nTop 10 states by enrollment count:")
    for state, count in top_states:
        print(f"  {state or '(blank)':>4}: {count:,}")

    hi_count = state_counts.get("HI", 0)
    print(f"\nHawaii SNF enrollments: {hi_count}  (expect 42–50)")
    if not (38 <= hi_count <= 55):
        print(
            f"WARNING: Hawaii count {hi_count} is outside [38, 55]. "
            "Cross-check against known 42 CMS-certified HI SNFs.",
            file=sys.stderr,
        )

    # Write CSV
    if not all_rows:
        print("ERROR: No rows to write.", file=sys.stderr)
        sys.exit(1)

    fieldnames = list(all_rows[0].keys())
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nOutput: {OUT_FILE}")
    print(f"Rows:   {total:,}")
    print(f"Cols:   {fieldnames}")
    print("\nKey columns for downstream joins:")
    print("  NPI              -- NPPES, LEIE, SAM.gov cross-reference")
    print("  CCN              -- all CMS facility datasets (PBJ, VBP, Cost Report, Quality)")
    print("  ENROLLMENT ID    -- SNF All Owners, SNF CHOW")
    print("  AFFILIATION ENTITY NAME / ID -- chain grouping")
    print("  PROPRIETARY_NONPROFIT -- P=for-profit, N=non-profit")


if __name__ == "__main__":
    main()
