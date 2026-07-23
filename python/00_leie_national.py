"""
00_leie_national.py
OIG LEIE (List of Excluded Individuals/Entities) -- full national reference.

Downloads the current monthly exclusion list from OIG and adds a severity_tier
column for use across all provider type exclusion checks (not SNF-specific).

Source:  OIG public download -- no authentication required
URL:     https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv
Updated: monthly (first week of each month)

Privacy rule (non-negotiable):
  Individual records (GENERAL == 'Individual') are NEVER a public product.
  This file must remain gitignored. Use for internal matching only (role-gated).
  Entity/facility matches = publish freely as public record.

Severity tiers (from OIG exclusions background):
  CRITICAL     1128a2  Patient abuse or neglect conviction
  HIGH         1128a1/a3/a4/c3  Mandatory fraud/felony/controlled substance
  ELEVATED     1128b4/b6/b7  License revocation, substandard care, kickbacks
  INFORMATIONAL  All other permissive (1128b) codes
"""

import urllib.request, csv, io, pathlib, time

LEIE_URL = "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv"
EXPECTED_MIN = 79_500   # 95% of 83,665 confirmed 2026-07-22; LEIE grows as exclusions added
EXPECTED_MAX = 130_000

OUTPUT_DIR = pathlib.Path(__file__).parent / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "leie_national.csv"

# Severity lookup -- normalize code to uppercase before matching
SEVERITY_MAP = {
    "1128A2":    "CRITICAL",
    "1128A1":    "HIGH",
    "1128A3":    "HIGH",
    "1128A4":    "HIGH",
    "1128C3GI":  "HIGH",
    "1128C3GII": "HIGH",
    "1128A8":    "HIGH",        # CMP with exclusion
    "1128AA":    "HIGH",        # CMP statute (Sec. 1128A) with exclusion -- OIG variant spelling
    "1156":      "HIGH",        # SSA Sec. 1156 -- gross/flagrant violations
    "1128B4":    "ELEVATED",    # License revocation
    "1128B6":    "ELEVATED",    # Excessive charges / substandard care
    "1128B7":    "ELEVATED",    # Fraud, kickbacks
}
# Anything not in map → INFORMATIONAL (all other permissive 1128b codes)


def assign_severity(code: str) -> str:
    normalized = code.strip().upper().replace(" ", "")
    return SEVERITY_MAP.get(normalized, "INFORMATIONAL")


def npi_present(npi: str) -> bool:
    v = npi.strip()
    return bool(v) and v != "0000000000"


print("Downloading OIG LEIE (List of Excluded Individuals/Entities)")
print(f"Source: {LEIE_URL}")
print()

req = urllib.request.Request(
    LEIE_URL,
    headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv,text/plain"},
)
with urllib.request.urlopen(req, timeout=120) as r:
    raw = r.read()

print(f"Downloaded: {len(raw):,} bytes")

# Parse CSV -- encoding is latin-1 for OIG files (names with accented chars)
text = raw.decode("latin-1", errors="replace")
reader = csv.DictReader(io.StringIO(text))

rows = []
for row in reader:
    row["severity_tier"] = assign_severity(row.get("EXCLTYPE", ""))
    rows.append(row)

total = len(rows)
print(f"Total records: {total:,}")
print()

if total < EXPECTED_MIN or total > EXPECTED_MAX:
    raise AssertionError(
        f"ASSERTION FAILED: record count {total:,} outside expected range "
        f"[{EXPECTED_MIN:,}, {EXPECTED_MAX:,}]"
    )
print("PASS: Record count within expected range.")
print()

# Type breakdown
# Individuals have LASTNAME populated; entities have BUSNAME populated, LASTNAME blank
individuals = sum(1 for r in rows if r.get("LASTNAME", "").strip())
entities = total - individuals
print(f"Individuals (role-gated only): {individuals:,}")
print(f"Entities (publishable as public record): {entities:,}")
print()

# Severity distribution
severity_counts: dict[str, int] = {}
for r in rows:
    s = r["severity_tier"]
    severity_counts[s] = severity_counts.get(s, 0) + 1
print("Severity distribution:")
for tier in ["CRITICAL", "HIGH", "ELEVATED", "INFORMATIONAL"]:
    n = severity_counts.get(tier, 0)
    print(f"  {tier:15}  n={n:6,}")
print()

# Exclusion type frequency
type_counts: dict[str, int] = {}
for r in rows:
    t = r.get("EXCLTYPE", "").strip()
    type_counts[t] = type_counts.get(t, 0) + 1
print("Exclusion type frequency (top 15):")
for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1])[:15]:
    sev = assign_severity(t)
    print(f"  {t:15}  {sev:15}  n={cnt:6,}")
print()

# NPI coverage (useful for match rate estimates)
npi_count = sum(1 for r in rows if npi_present(r.get("NPI", "")))
print(f"Records with real NPI: {npi_count:,} of {total:,} ({npi_count/total*100:.1f}%)")
print("  (NPI=0000000000 treated as blank)")
print()

# Write output -- full file, all columns + severity_tier
OUTPUT_DIR.mkdir(exist_ok=True)
fieldnames = list(rows[0].keys()) if rows else []
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Output:  {OUTPUT_FILE}")
print(f"Rows:    {total:,}")
print(f"Cols:    {len(fieldnames)}")
print()
print("GITIGNORE: this file contains individual names -- role-gated access only.")
print("Columns (actual CSV names -- no spaces):")
print("  NPI LASTNAME FIRSTNAME MIDNAME BUSNAME GENERAL EXCLTYPE EXCLDATE")
print("  REINDATE WAIVERDATE WVRSTATE STATE ZIP + severity_tier (added)")
print("NPI=0000000000 means no real NPI -- filter with: npi.strip() not in ('', '0000000000')")
print("GENERAL field: specialty type description (not Individual/Entity flag)")
print("  Distinguish by: LASTNAME non-empty = individual; BUSNAME only = entity")
