"""
00_census_demographics_national.py

Pulls ACS 5-Year demographic variables for ALL US ZCTAs from the Census API.
Companion to get_census_us_65plus.py (which covers B01001 age/65+ only).
This script covers the remaining variables needed for the Phase 2 accountability layer.

Variables pulled (ACS 5-Year):
  B02001 -- Race (White alone, Black alone, Asian alone, NHPI alone, multiracial)
  B03002 -- Hispanic or Latino origin
  B19013 -- Median household income
  S1811  -- Disability characteristics (civilian noninstitutionalized population)

The existing get_census_us_65plus.py is NOT replaced -- it feeds the SQL Server
pipeline and its output format matches sql/02_census_national_load.sql.
This script produces a separate wider CSV for the Python analytics layer.

No API key needed from environment -- reads CENSUS_API_KEY env var or first arg.
Key on file: 30377fb3d687e35d95ac7a5a29ad94eb5baa69d0

Expected output: 33,000-34,500 ZCTAs.
Script will exit if count outside this range.

Output: output_reference/census_demographics_national.csv
"""

import csv
import json
import os
import ssl
import sys
import time
import urllib.request
from pathlib import Path

ACS_YEAR = "2024"
BASE_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
BASE_URL_S = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5/subject"  # S-table endpoint

EXPECTED_MIN = 32_100   # 95% of 33,772 confirmed 2026-07-22
EXPECTED_MAX = 35_500

OUT_DIR = Path(__file__).parent / "output_reference"
OUT_FILE = OUT_DIR / "census_demographics_national.csv"

# Suppressed/null sentinel values from Census API
SUPPRESSED = {"-666666666", "-999999999", "-333333333", "-222222222", "N", "null", "None", ""}


def safe_int(val) -> int:
    return 0 if str(val) in SUPPRESSED else int(float(str(val)))


def safe_float(val) -> float:
    return None if str(val) in SUPPRESSED else round(float(str(val)), 1)


def _fetch(url: str) -> list:
    """Fetch a Census API URL, returns parsed JSON rows (header included)."""
    def _get(verified: bool) -> bytes:
        ctx = ssl.create_default_context()
        if not verified:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(url, timeout=180, context=ctx) as r:
            return r.read()
    try:
        raw = _get(verified=True)
    except ssl.SSLError:
        raw = _get(verified=False)
    return json.loads(raw)


def fetch_b02001(key: str) -> dict[str, dict]:
    """Race — B02001."""
    vars_ = [
        "B02001_001E",  # Total
        "B02001_002E",  # White alone
        "B02001_003E",  # Black or African American alone
        "B02001_004E",  # American Indian and Alaska Native alone
        "B02001_005E",  # Asian alone
        "B02001_006E",  # Native Hawaiian and Other Pacific Islander alone
        "B02001_007E",  # Some other race alone
        "B02001_008E",  # Two or more races
    ]
    url = (
        BASE_URL
        + "?get=" + ",".join(vars_)
        + "&for=zip%20code%20tabulation%20area:*"
        + "&key=" + key
    )
    print("  Fetching B02001 (race)...")
    data = _fetch(url)
    header = data[0]
    out = {}
    for row in data[1:]:
        zcta = row[-1]
        total = safe_int(row[0])
        out[zcta] = {
            "race_total":    total,
            "race_white":    safe_int(row[1]),
            "race_black":    safe_int(row[2]),
            "race_aian":     safe_int(row[3]),
            "race_asian":    safe_int(row[4]),
            "race_nhpi":     safe_int(row[5]),
            "race_other":    safe_int(row[6]),
            "race_multi":    safe_int(row[7]),
            "pct_white":     round(safe_int(row[1]) / total * 100, 1) if total else None,
            "pct_black":     round(safe_int(row[2]) / total * 100, 1) if total else None,
            "pct_asian":     round(safe_int(row[4]) / total * 100, 1) if total else None,
            "pct_nhpi":      round(safe_int(row[5]) / total * 100, 1) if total else None,
        }
    return out


def fetch_b03002(key: str) -> dict[str, dict]:
    """Hispanic or Latino origin — B03002."""
    vars_ = [
        "B03002_001E",  # Total
        "B03002_003E",  # White alone, Not Hispanic or Latino
        "B03002_012E",  # Hispanic or Latino (any race)
    ]
    url = (
        BASE_URL
        + "?get=" + ",".join(vars_)
        + "&for=zip%20code%20tabulation%20area:*"
        + "&key=" + key
    )
    print("  Fetching B03002 (Hispanic/Latino origin)...")
    data = _fetch(url)
    out = {}
    for row in data[1:]:
        zcta = row[-1]
        total = safe_int(row[0])
        hispanic = safe_int(row[2])
        out[zcta] = {
            "hispanic_total":   total,
            "hispanic_count":   hispanic,
            "pct_hispanic":     round(hispanic / total * 100, 1) if total else None,
            "non_hisp_white":   safe_int(row[1]),
        }
    return out


def fetch_b19013(key: str) -> dict[str, dict]:
    """Median household income — B19013."""
    vars_ = ["B19013_001E"]
    url = (
        BASE_URL
        + "?get=" + ",".join(vars_)
        + "&for=zip%20code%20tabulation%20area:*"
        + "&key=" + key
    )
    print("  Fetching B19013 (median household income)...")
    data = _fetch(url)
    out = {}
    for row in data[1:]:
        zcta = row[-1]
        val = row[0]
        out[zcta] = {
            "median_hh_income": None if str(val) in SUPPRESSED else int(float(str(val)))
        }
    return out


def fetch_s1811(key: str) -> dict[str, dict]:
    """Disability status — S1811 (Subject table, separate endpoint)."""
    # S1811_C01_001E = civilian noninst. pop total
    # S1811_C02_001E = with any disability (count)
    # S1811_C03_001E = percent with disability
    vars_ = [
        "S1811_C01_001E",  # total civilian noninstitutionalized pop
        "S1811_C02_001E",  # with a disability
        "S1811_C03_001E",  # percent with a disability
    ]
    url = (
        BASE_URL_S
        + "?get=" + ",".join(vars_)
        + "&for=zip%20code%20tabulation%20area:*"
        + "&key=" + key
    )
    print("  Fetching S1811 (disability)...")
    data = _fetch(url)
    out = {}
    for row in data[1:]:
        zcta = row[-1]
        out[zcta] = {
            "disability_pop_total":   safe_int(row[0]),
            "disability_count":       safe_int(row[1]),
            "pct_disability":         safe_float(row[2]),
        }
    return out


def main() -> None:
    key = (
        sys.argv[1] if len(sys.argv) > 1
        else os.environ.get("CENSUS_API_KEY", "30377fb3d687e35d95ac7a5a29ad94eb5baa69d0")
    )

    OUT_DIR.mkdir(exist_ok=True)

    print(f"Pulling Census ACS 5-Year {ACS_YEAR} demographic variables -- all US ZCTAs")
    print(f"Tables: B02001 (race), B03002 (Hispanic), B19013 (income), S1811 (disability)")
    print("Each table is a separate API call. Expect 2-5 minutes total.\n")

    b02001 = fetch_b02001(key)
    time.sleep(1)
    b03002 = fetch_b03002(key)
    time.sleep(1)
    b19013 = fetch_b19013(key)
    time.sleep(1)
    s1811  = fetch_s1811(key)

    # Merge on ZCTA
    all_zctas = sorted(set(b02001) | set(b03002) | set(b19013) | set(s1811))
    total = len(all_zctas)
    print(f"\nUnique ZCTAs across all tables: {total:,}")

    if not (EXPECTED_MIN <= total <= EXPECTED_MAX):
        print(
            f"ASSERTION FAILED: Expected {EXPECTED_MIN:,}-{EXPECTED_MAX:,} ZCTAs, "
            f"got {total:,}. Do not use this output.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"PASS: ZCTA count {total:,} within expected range.")

    # Spot-check: Hawaii ZCTAs
    hi_zctas = [z for z in all_zctas if z.startswith(("967", "968"))]
    print(f"Hawaii ZCTAs (967xx/968xx): {len(hi_zctas)}  (expect 90-105)")

    fieldnames = [
        "zcta",
        # Race
        "race_total", "race_white", "race_black", "race_aian",
        "race_asian", "race_nhpi", "race_other", "race_multi",
        "pct_white", "pct_black", "pct_asian", "pct_nhpi",
        # Hispanic
        "hispanic_total", "hispanic_count", "pct_hispanic", "non_hisp_white",
        # Income
        "median_hh_income",
        # Disability
        "disability_pop_total", "disability_count", "pct_disability",
        # Metadata
        "acs_year",
    ]

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for zcta in all_zctas:
            row = {"zcta": zcta, "acs_year": f"{ACS_YEAR}-5yr"}
            row.update(b02001.get(zcta, {}))
            row.update(b03002.get(zcta, {}))
            row.update(b19013.get(zcta, {}))
            row.update(s1811.get(zcta, {}))
            writer.writerow(row)

    print(f"\nOutput: {OUT_FILE}")
    print(f"Rows:   {total:,}")
    print(f"Cols:   {fieldnames}")
    print()
    print("This file covers race/ethnicity, income, and disability.")
    print("For 65+ population totals, use get_census_us_65plus.py output.")
    print("Join both files on 'zcta' (= 'ZIP' in the 65+ file).")


if __name__ == "__main__":
    main()
