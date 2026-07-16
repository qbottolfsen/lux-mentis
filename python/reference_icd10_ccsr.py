"""
reference_icd10_ccsr.py
ICD-10-CM clinical grouper reference table -- national LTPAC platform.

Source: AHRQ Clinical Classifications Software Refined (DXCCSR) v2026.1
  Released: November 2025 | Valid through: September 2026
  URL: https://hcup-us.ahrq.gov/toolssoftware/ccsr/DXCCSR-v2026-1.zip
  Citation: HCUP CCSR. 2025. Agency for Healthcare Research and Quality, Rockville, MD.
            https://hcup-us.ahrq.gov/toolssoftware/ccsr/ccs_refined.jsp

What this provides:
  - Every ICD-10-CM diagnosis code mapped to up to 6 CCSR clinical categories
  - CCSR categories enable "all diabetes", "all cancer" queries without hardcoding
    code ranges. Drill down to specific codes or roll up to body system.
  - Chapter assignment for all codes (A00-Z99, U00-U85)
  - Incident classification flags for LTPAC abuse/safety analysis:
      is_abuse_maltreatment  T74/T76  confirmed/suspected maltreatment
      is_perpetrator_code    Y07      who caused harm (staff vs resident vs family)
      is_place_of_occurrence Y92      where incident occurred
      is_fall                W00-W19  fall incidents

Output columns:
  icd10_code             7-char code without period (join key, e.g. E1165)
  icd10_code_formatted   with period (e.g. E11.65) for display
  icd10_desc             long description
  chapter / chapter_desc ICD-10-CM chapter from code prefix
  default_ccsr_ip/op     default CCSR category (inpatient / outpatient)
  ccsr_cat_1..6          up to 6 CCSR category codes (e.g. DIA002)
  ccsr_cat_1_desc..6     CCSR category descriptions
  body_system            CCSR body system label
  is_external_cause      True for V00-Y99 (Chapter 20)
  is_injury_poisoning    True for S00-T88 (Chapter 19)
  is_abuse_maltreatment  True for T74, T76
  is_perpetrator_code    True for Y07
  is_place_of_occurrence True for Y92
  is_fall                True for W00-W19
  is_assault             True for X85-Y09
  ccsr_version           source version label

Output: output_reference/icd10_ccsr_reference.csv

Usage:
  JOIN on icd10_code (no periods) to any dataset with ICD-10-CM codes.
  To query "all Type 2 diabetes": WHERE ccsr_cat_1 = 'DIA002' OR ccsr_cat_2 = 'DIA002' ...
  To query "all cancer": WHERE body_system LIKE '%Neoplasm%' OR chapter = 'Chapter 2'
  To query "all falls": WHERE is_fall = 'True'
  To query "staff-on-resident abuse": WHERE is_abuse_maltreatment='True' (T74/T76)
    paired with is_perpetrator_code='True' (Y07) in same encounter
"""

import csv, io, pathlib, sys, time, urllib.request, zipfile

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required: pip install pandas")

SCRIPT_DIR  = pathlib.Path(__file__).parent
OUTPUT_DIR  = SCRIPT_DIR / "output_reference"
CACHE_DIR   = OUTPUT_DIR / "icd10_cache"
OUTPUT_FILE = OUTPUT_DIR / "icd10_ccsr_reference.csv"

CCSR_URL      = "https://hcup-us.ahrq.gov/toolssoftware/ccsr/DXCCSR-v2026-1.zip"
CCSR_VERSION  = "AHRQ DXCCSR v2026.1"
CACHE_FILE    = CACHE_DIR / "DXCCSR-v2026-1.zip"

EXPECTED_MIN = 75_000
EXPECTED_MAX = 130_000

# ── ICD-10-CM chapter map (stable -- official ICD-10-CM structure) ─────────────
CHAPTERS = [
    ("Chapter 1",  "A00", "B99", "Certain infectious and parasitic diseases"),
    ("Chapter 2",  "C00", "D49", "Neoplasms"),
    ("Chapter 3",  "D50", "D89", "Diseases of the blood and blood-forming organs and certain disorders involving the immune mechanism"),
    ("Chapter 4",  "E00", "E89", "Endocrine, nutritional and metabolic diseases"),
    ("Chapter 5",  "F01", "F99", "Mental, behavioral and neurodevelopmental disorders"),
    ("Chapter 6",  "G00", "G99", "Diseases of the nervous system"),
    ("Chapter 7",  "H00", "H59", "Diseases of the eye and adnexa"),
    ("Chapter 8",  "H60", "H95", "Diseases of the ear and mastoid process"),
    ("Chapter 9",  "I00", "I99", "Diseases of the circulatory system"),
    ("Chapter 10", "J00", "J99", "Diseases of the respiratory system"),
    ("Chapter 11", "K00", "K95", "Diseases of the digestive system"),
    ("Chapter 12", "L00", "L99", "Diseases of the skin and subcutaneous tissue"),
    ("Chapter 13", "M00", "M99", "Diseases of the musculoskeletal system and connective tissue"),
    ("Chapter 14", "N00", "N99", "Diseases of the genitourinary system"),
    ("Chapter 15", "O00", "O9A", "Pregnancy, childbirth and the puerperium"),
    ("Chapter 16", "P00", "P96", "Certain conditions originating in the perinatal period"),
    ("Chapter 17", "Q00", "Q99", "Congenital malformations, deformations and chromosomal abnormalities"),
    ("Chapter 18", "R00", "R99", "Symptoms, signs and abnormal clinical and laboratory findings, not elsewhere classified"),
    ("Chapter 19", "S00", "T88", "Injury, poisoning and certain other consequences of external causes"),
    ("Chapter 20", "V00", "Y99", "External causes of morbidity"),
    ("Chapter 21", "Z00", "Z99", "Factors influencing health status and contact with health services"),
    ("Chapter 22", "U00", "U85", "Codes for special purposes"),
]


def get_chapter(code: str) -> tuple[str, str]:
    if not code or len(code) < 3:
        return "", ""
    prefix = code[:3].upper()
    for label, start, end, desc in CHAPTERS:
        if start <= prefix <= end:
            return label, desc
    return "Unknown", ""


def format_code(code: str) -> str:
    """Add decimal point after 3rd character: E1165 → E11.65"""
    code = code.strip()
    if len(code) <= 3:
        return code
    return code[:3] + "." + code[3:]


def incident_flags(code: str) -> dict:
    """Return boolean flags relevant to LTPAC incident classification."""
    if not code or len(code) < 3:
        return {}
    c = code.upper().replace(".", "")
    p3 = c[:3]   # 3-char category prefix
    return {
        "is_external_cause":       "V00" <= p3 <= "Y99",
        "is_injury_poisoning":     "S00" <= p3 <= "T88",
        "is_abuse_maltreatment":   p3 in ("T74", "T76"),
        "is_perpetrator_code":     p3 == "Y07",
        "is_place_of_occurrence":  p3 == "Y92",
        "is_fall":                 "W00" <= p3 <= "W19",
        "is_assault":              "X85" <= p3 <= "Y09",
    }


# ── Download / cache ───────────────────────────────────────────────────────────

print("ICD-10-CM / AHRQ CCSR Reference Table")
print(f"Source: {CCSR_VERSION}")
print(f"Output: {OUTPUT_FILE}")
print()

CACHE_DIR.mkdir(parents=True, exist_ok=True)

if CACHE_FILE.exists():
    age_days = (pathlib.Path(CACHE_FILE).stat().st_mtime - 0)
    print(f"Using cached ZIP: {CACHE_FILE}")
else:
    print(f"Downloading {CCSR_URL} ...")
    t0 = time.time()
    req = urllib.request.Request(
        CCSR_URL,
        headers={"User-Agent": "Mozilla/5.0 (research data pipeline)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except Exception as e:
        sys.exit(
            f"Download failed: {e}\n"
            f"Check URL: {CCSR_URL}\n"
            f"Or download manually and save to: {CACHE_FILE}"
        )
    CACHE_FILE.write_bytes(data)
    print(f"  Downloaded {len(data):,} bytes in {time.time()-t0:.1f}s")

# ── Extract CSV from ZIP ───────────────────────────────────────────────────────

print("Extracting CCSR CSV ...")
with zipfile.ZipFile(CACHE_FILE) as zf:
    names = zf.namelist()
    print(f"  ZIP contains: {names}")
    # Find the diagnosis CCSR CSV (not procedure)
    csv_names = [n for n in names if n.upper().endswith(".CSV") and "DX" in n.upper()]
    if not csv_names:
        csv_names = [n for n in names if n.upper().endswith(".CSV")]
    if not csv_names:
        sys.exit(f"No CSV found in ZIP. Contents: {names}")
    csv_name = csv_names[0]
    print(f"  Extracting: {csv_name}")
    raw_bytes = zf.read(csv_name)

# ── Parse CCSR CSV ─────────────────────────────────────────────────────────────

print("Parsing CCSR CSV ...")

# DXCCSR CSVs sometimes have a note/disclaimer as the first line before the header.
# Find the actual header row (contains 'ICD-10-CM CODE').
text = raw_bytes.decode("latin-1")
lines = text.splitlines()

header_idx = None
for i, line in enumerate(lines):
    if "ICD-10-CM CODE" in line.upper():
        header_idx = i
        break

if header_idx is None:
    sys.exit("Could not locate header row containing 'ICD-10-CM CODE' in CCSR CSV.")

print(f"  Header at line {header_idx + 1}: {lines[header_idx][:120]}")
body = "\n".join(lines[header_idx:])

reader = csv.DictReader(io.StringIO(body))
raw_cols = reader.fieldnames
print(f"  Columns ({len(raw_cols)}): {raw_cols}")

# Normalize column names: strip whitespace and quotes
def norm(s):
    return s.strip().strip('"').strip("'").strip()

raw_rows = list(reader)
print(f"  Raw rows: {len(raw_rows):,}")

# ── Column mapping ─────────────────────────────────────────────────────────────
# CCSR column names are consistent across versions but may have minor spacing differences.
# We match by substring to be resilient.

def find_col(cols, *substrings):
    """Find column name containing all substrings (case-insensitive)."""
    for c in cols:
        cn = c.upper().strip().strip('"').strip("'").strip()
        if all(s.upper() in cn for s in substrings):
            return c
    return None

col_code      = find_col(raw_cols, "ICD-10-CM CODE") or find_col(raw_cols, "CODE")
col_desc      = find_col(raw_cols, "DESCRIPTION") or find_col(raw_cols, "DESC")
col_dflt_ip   = find_col(raw_cols, "DEFAULT", "IP")
col_dflt_op   = find_col(raw_cols, "DEFAULT", "OP")
col_body      = find_col(raw_cols, "BODY")

# CCSR category pairs (1-6)
cat_pairs = []
for n in range(1, 7):
    c_cat  = find_col(raw_cols, f"CCSR CATEGORY {n}") or find_col(raw_cols, f"CATEGORY {n}")
    c_desc = find_col(raw_cols, f"CCSR CATEGORY {n} DESCRIPTION") or find_col(raw_cols, f"CATEGORY {n} DESCRIPTION")
    if c_cat:
        cat_pairs.append((n, c_cat, c_desc))

if not col_code:
    sys.exit(f"Could not find ICD-10-CM CODE column. Available: {raw_cols}")

print(f"  Code column:  {col_code!r}")
print(f"  Desc column:  {col_desc!r}")
print(f"  CCSR cats:    {len(cat_pairs)} category pairs found")
print(f"  Body system:  {col_body!r}")

# ── Build output rows ──────────────────────────────────────────────────────────

print()
print("Building reference table ...")

out_rows = []
for r in raw_rows:
    raw_code = norm(r.get(col_code, ""))
    if not raw_code:
        continue
    # Remove periods if source has them
    code = raw_code.replace(".", "").upper()
    desc = norm(r.get(col_desc, "")) if col_desc else ""

    chapter, chapter_desc = get_chapter(code)
    flags = incident_flags(code)

    row = {
        "icd10_code":           code,
        "icd10_code_formatted": format_code(code),
        "icd10_desc":           desc,
        "chapter":              chapter,
        "chapter_desc":         chapter_desc,
        "default_ccsr_ip":      norm(r.get(col_dflt_ip, "")) if col_dflt_ip else "",
        "default_ccsr_op":      norm(r.get(col_dflt_op, "")) if col_dflt_op else "",
        "body_system":          norm(r.get(col_body, "")) if col_body else "",
    }

    # CCSR categories 1-6
    for n, c_cat, c_desc_col in cat_pairs:
        row[f"ccsr_cat_{n}"]      = norm(r.get(c_cat, "")) if c_cat else ""
        row[f"ccsr_cat_{n}_desc"] = norm(r.get(c_desc_col, "")) if c_desc_col else ""

    # Pad missing cat columns
    for n in range(1, 7):
        row.setdefault(f"ccsr_cat_{n}", "")
        row.setdefault(f"ccsr_cat_{n}_desc", "")

    row.update({k: str(v) for k, v in flags.items()})
    row["ccsr_version"] = CCSR_VERSION

    out_rows.append(row)

# ── Assertions ─────────────────────────────────────────────────────────────────

print()
print("Assertions ...")

total = len(out_rows)
if not (EXPECTED_MIN <= total <= EXPECTED_MAX):
    raise AssertionError(f"FAILED: total {total:,} outside [{EXPECTED_MIN:,}, {EXPECTED_MAX:,}]")
print(f"  PASS: {total:,} codes")

df = pd.DataFrame(out_rows)

# Diabetes codes (E10=Type1, E11=Type2)
t1 = df["icd10_code"].str.startswith("E10").sum()
t2 = df["icd10_code"].str.startswith("E11").sum()
assert t1 > 0 and t2 > 0, f"Missing diabetes codes: E10={t1}, E11={t2}"
print(f"  PASS: Type 1 diabetes codes (E10.x): {t1}")
print(f"  PASS: Type 2 diabetes codes (E11.x): {t2}")

# Cancer (C codes)
cancer = df["icd10_code"].str.startswith("C").sum()
assert cancer > 0, "No cancer codes (C..) found"
print(f"  PASS: Cancer codes (C.x): {cancer:,}")

# Incident codes
for flag, expected_prefix, label in [
    ("is_abuse_maltreatment",  "T74", "T74/T76 maltreatment"),
    ("is_perpetrator_code",    "Y07", "Y07 perpetrator"),
    ("is_place_of_occurrence", "Y92", "Y92 place of occurrence"),
    ("is_fall",                "W00", "W00-W19 falls"),
]:
    n = (df[flag] == "True").sum()
    assert n > 0, f"No {label} codes found (flag={flag})"
    print(f"  PASS: {label}: {n} codes")

# ── Summary ────────────────────────────────────────────────────────────────────

print()
print("Chapter distribution:")
for ch, desc in [(c[0], c[3]) for c in CHAPTERS]:
    n = (df["chapter"] == ch).sum()
    if n:
        print(f"  {ch:<10}  {n:6,}  {desc[:55]}")

print()
print("Sample CCSR categories — diabetes:")
diab = df[df["icd10_code"].str.startswith(("E10", "E11", "E13"))][
    ["icd10_code_formatted", "icd10_desc", "default_ccsr_ip", "ccsr_cat_1", "ccsr_cat_1_desc"]
].drop_duplicates(subset=["default_ccsr_ip"]).head(8)
for _, r in diab.iterrows():
    print(f"  {r['icd10_code_formatted']:<10}  {r['default_ccsr_ip']:<8}  {r['ccsr_cat_1_desc']}")

print()
print("Sample CCSR categories — cancer:")
ca = df[df["icd10_code"].str.startswith("C")][
    ["icd10_code_formatted", "default_ccsr_ip", "ccsr_cat_1_desc"]
].drop_duplicates(subset=["default_ccsr_ip"]).head(6)
for _, r in ca.iterrows():
    print(f"  {r['icd10_code_formatted']:<10}  {r['default_ccsr_ip']:<8}  {r['ccsr_cat_1_desc']}")

print()
print("Incident flags (LTPAC relevance):")
for flag in ["is_abuse_maltreatment", "is_perpetrator_code", "is_place_of_occurrence",
             "is_fall", "is_assault", "is_external_cause", "is_injury_poisoning"]:
    n = (df[flag] == "True").sum()
    print(f"  {flag:<28}  {n:5,} codes")

print()
print("Y07 perpetrator codes (staff vs. resident vs. family):")
y07 = df[df["icd10_code"].str.startswith("Y07")][
    ["icd10_code_formatted", "icd10_desc"]
].sort_values("icd10_code_formatted")
for _, r in y07.iterrows():
    print(f"  {r['icd10_code_formatted']:<12}  {r['icd10_desc']}")

# ── Write output ───────────────────────────────────────────────────────────────

OUT_COLS = [
    "icd10_code", "icd10_code_formatted", "icd10_desc",
    "chapter", "chapter_desc",
    "default_ccsr_ip", "default_ccsr_op",
    "ccsr_cat_1", "ccsr_cat_1_desc",
    "ccsr_cat_2", "ccsr_cat_2_desc",
    "ccsr_cat_3", "ccsr_cat_3_desc",
    "ccsr_cat_4", "ccsr_cat_4_desc",
    "ccsr_cat_5", "ccsr_cat_5_desc",
    "ccsr_cat_6", "ccsr_cat_6_desc",
    "body_system",
    "is_external_cause", "is_injury_poisoning",
    "is_abuse_maltreatment", "is_perpetrator_code",
    "is_place_of_occurrence", "is_fall", "is_assault",
    "ccsr_version",
]
df = df[[c for c in OUT_COLS if c in df.columns]]

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(df):,}")
print(f"Cols:   {len(df.columns)}")
print()
print("Join pattern for downstream scripts:")
print("  icd10_ccsr[icd10_code]  <-->  any CMS dataset's diagnosis code column")
print("  Strip periods before joining: code.replace('.', '').upper()")
print()
print("Query patterns:")
print("  All Type 2 diabetes:  ccsr_cat_1=='DIA002' | ccsr_cat_2=='DIA002' | ...")
print("  All cancer:           chapter=='Chapter 2'")
print("  All falls:            is_fall=='True'")
print("  Abuse/maltreatment:   is_abuse_maltreatment=='True'  (T74/T76)")
print("  Perpetrator type:     is_perpetrator_code=='True'    (Y07.xx)")
print("  Place of occurrence:  is_place_of_occurrence=='True' (Y92.xx)")
