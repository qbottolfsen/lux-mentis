"""
get_census_us_65plus.py

Fetches ACS 5-Year Table B01001 (Sex by Age) for ALL US ZCTAs
from the Census Bureau API and writes a CSV ready for
sql/02_census_national_load.sql.

This is the national version of the Hawaii project's
get_census_hi_65plus.py. The only functional difference:
the Hawaii filter (startswith "967"/"968") is removed.
All other logic — variable selection, suppression handling,
output format — is identical so both CSVs load into the
same schema.

REQUIRES a free Census API key.
Sign up: https://api.census.gov/data/key_signup.html
Then either:
  - Set env var:  export CENSUS_API_KEY=your_key_here
  - Or pass as arg: python3 get_census_us_65plus.py YOUR_KEY_HERE

Output: ACSDT5Y<year>.B01001_US_ZCTA_Pivoted.csv
        Written to the same directory as this script.

SCALE NOTE:
  The national pull returns ~33,000 ZCTAs vs 97 for Hawaii.
  The Census API supports this in a single keyed request.
  Without a key the API caps responses at 500 rows — which
  would load silently and produce completely wrong denominators
  everywhere downstream. A key is not optional for this script.

  This script validates the response against a hard expected
  range before writing output. If the count is outside
  [32,000, 34,500] it exits without writing the CSV and tells
  you what it got. Do not proceed to the SQL load until this
  check passes.

No third-party packages required — stdlib only.
"""

import csv
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

VARIABLES = [
    "B01001_001E",
    "B01001_020E", "B01001_021E", "B01001_022E",
    "B01001_023E", "B01001_024E", "B01001_025E",
    "B01001_044E", "B01001_045E", "B01001_046E",
    "B01001_047E", "B01001_048E", "B01001_049E",
]

# Update year to match the ACS vintage you want
ACS_YEAR = "2024"

BASE_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"

OUTPUT_FILE = Path(__file__).parent / f"ACSDT5Y{ACS_YEAR}.B01001_US_ZCTA_Pivoted.csv"

SUPPRESSED = {"-666666666", "-999999999", "-333333333", "-222222222", "N", ""}

# Hard bounds on the expected ZCTA count.
# The US has ~33,000-33,800 ZCTAs depending on ACS vintage.
# Outside this range means the pull was truncated or malformed.
EXPECTED_ZCTA_MIN = 32_000
EXPECTED_ZCTA_MAX = 34_500

# Known spot-check: Hawaii should have ~97 ZCTAs in the national pull.
# Adjust if ACS vintage changes significantly.
HAWAII_PREFIXES = ("967", "968")
HAWAII_EXPECTED_MIN = 90
HAWAII_EXPECTED_MAX = 105


def safe_int(val: str) -> int:
    return 0 if val in SUPPRESSED else int(val)


def validate_pull(rows: list) -> bool:
    """
    Validates the API response against known expectations.
    Returns True if the pull looks complete, False otherwise.
    Prints a diagnostic message in all cases.
    """
    total = len(rows)
    print(f"\n--- Validation ---")
    print(f"Total ZCTAs received: {total:,}")

    ok = True

    if not (EXPECTED_ZCTA_MIN <= total <= EXPECTED_ZCTA_MAX):
        print(
            f"FAIL: Expected {EXPECTED_ZCTA_MIN:,}-{EXPECTED_ZCTA_MAX:,} ZCTAs. "
            f"Got {total:,}. Pull is likely truncated or malformed."
        )
        if total <= 500:
            print(
                "      Got <=500 rows — this is the no-key API cap. "
                "A Census API key is required for the national pull."
            )
        ok = False
    else:
        print(f"PASS: Total count {total:,} is within expected range.")

    # Hawaii spot-check: the Hawaii subset inside the national pull
    # should match the Hawaii-only script's output of ~97 ZCTAs.
    hi_count = sum(1 for r in rows if r[-1].startswith(HAWAII_PREFIXES))
    print(f"Hawaii ZCTAs (967xx/968xx) within pull: {hi_count}")
    if not (HAWAII_EXPECTED_MIN <= hi_count <= HAWAII_EXPECTED_MAX):
        print(
            f"FAIL: Expected {HAWAII_EXPECTED_MIN}-{HAWAII_EXPECTED_MAX} Hawaii ZCTAs. "
            f"Got {hi_count}. Cross-check against Hawaii project output."
        )
        ok = False
    else:
        print(f"PASS: Hawaii count {hi_count} matches expectation.")

    # State-prefix distribution — print top 10 so you can eyeball plausibility
    from collections import Counter
    prefix_counts = Counter(r[-1][:3] for r in rows)
    print("\nTop 10 ZIP prefixes by ZCTA count (sanity check):")
    for prefix, count in prefix_counts.most_common(10):
        print(f"  {prefix}xx: {count} ZCTAs")

    return ok


def main() -> None:
    api_key = (
        sys.argv[1] if len(sys.argv) > 1
        else os.environ.get("CENSUS_API_KEY", "")
    )
    if not api_key:
        print(
            "ERROR: Census API key required.\n"
            "Without a key the Census API caps responses at 500 rows,\n"
            "which would silently produce a completely wrong dataset.\n"
            "Get a free key at: https://api.census.gov/data/key_signup.html\n"
            "Then run:  python3 get_census_us_65plus.py YOUR_KEY_HERE\n"
            "   or set: export CENSUS_API_KEY=YOUR_KEY_HERE",
            file=sys.stderr,
        )
        sys.exit(1)

    url = (
        BASE_URL
        + "?get=" + ",".join(VARIABLES)
        + "&for=zip%20code%20tabulation%20area:*"
        + "&key=" + api_key
    )

    print(f"Fetching Census ACS 5-Year {ACS_YEAR}, Table B01001 — ALL US ZCTAs...")
    print(f"URL: {url.replace(api_key, '***KEY***')}")
    print("Expect 30-90 seconds. The Census API returns all ~33K ZCTAs in one response.\n")

    # Try verified SSL first; fall back unverified with a warning if certs
    # are missing. Install 'certifi' and pass cafile=certifi.where() to
    # ssl.create_default_context() to avoid the fallback permanently.
    def _fetch(verified: bool) -> bytes:
        ctx = ssl.create_default_context()
        if not verified:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(url, timeout=180, context=ctx) as resp:
            return resp.read()

    try:
        raw = _fetch(verified=True)
    except ssl.SSLError as exc:
        print(
            f"WARNING: SSL verification failed ({exc}). "
            "Retrying without certificate check. "
            "Install 'certifi' to fix this permanently.",
            file=sys.stderr,
        )
        try:
            raw = _fetch(verified=False)
        except Exception as exc2:
            print(f"ERROR fetching data: {exc2}", file=sys.stderr)
            print(
                "If this is a timeout, the Census API may be under load. "
                "Wait a few minutes and retry.",
                file=sys.stderr,
            )
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR fetching data: {exc}", file=sys.stderr)
        print(
            "If this is a timeout, the Census API may be under load. "
            "Wait a few minutes and retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR parsing response as JSON: {exc}", file=sys.stderr)
        print(f"Response size: {len(raw):,} bytes", file=sys.stderr)
        sys.exit(1)

    rows = data[1:]  # row 0 is the API header

    # Validate before writing anything
    if not validate_pull(rows):
        print(
            "\nValidation failed. CSV not written. "
            "Fix the issue above before proceeding to the SQL load.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\nValidation passed. Writing output...")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ZIP", "Population_Total", "Population_65Plus", "ACS_Year"])

        for row in rows:
            zcta       = row[-1]
            pop_total  = safe_int(row[0])
            pop_65plus = sum(safe_int(v) for v in row[1:13])
            writer.writerow([zcta, pop_total, pop_65plus, f"{ACS_YEAR}-5yr"])

    print(f"\nOutput written to:\n  {OUTPUT_FILE}")
    print("\nPreview (first 10 data rows):")
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 11:
                break
            print(f"  {line.rstrip()}")

    print(
        "\nNext step: copy the CSV to wherever your SQL Server instance"
        "\ncan reach it, then run sql/02_census_national_load.sql."
        "\nVerify row count there too — expect same count as shown above."
    )


if __name__ == "__main__":
    main()
