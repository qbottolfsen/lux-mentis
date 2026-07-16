"""
reference_ftag_citations.py
F-tag / K-tag deficiency citation reference table.

Source: CMS Provider Data -- NH Citation Code Lookup
  Dataset:      tagd-9999
  Distribution: 0be2d742-2119-55cd-b8a9-59e8e25fd6b0
  Updated:      Annually with CMS survey guidance revisions
  ~700+ rows; no state filter

Maps deficiency tag numbers to regulatory category and description.
Used by nh_deficiencies_national.py for human-readable category labeling.

Prefix conventions:
  F  = Health deficiency (42 CFR §483 subparts B, C, D, E, F, G)
  K  = Fire safety deficiency (NFPA 101 Life Safety Code)

Output: output_reference/reference_ftag_citations.csv
"""

import json, pathlib, sys, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "reference_ftag_citations.csv"

DIST_ID  = "0be2d742-2119-55cd-b8a9-59e8e25fd6b0"
# This dataset requires the SQL GET endpoint (JSON POST returns 400)
SQL_BASE = "https://data.cms.gov/provider-data/api/1/datastore/sql"

EXPECTED_MIN = 500
EXPECTED_MAX = 1_200


def fetch_all() -> list:
    import urllib.parse
    query = f"[SELECT * FROM {DIST_ID}][LIMIT 2000]"
    url = SQL_BASE + "?query=" + urllib.parse.quote(query)
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = json.loads(resp.read())
    # SQL endpoint returns a list (not dict with count/results)
    if isinstance(data, list):
        print(f"  Rows received: {len(data)}")
        return data
    # Some endpoints wrap in dict
    return data.get("results", data)


print("F-tag / K-tag Citation Reference Table")
print(f"Source distribution: {DIST_ID}")
print()

rows = fetch_all()
print(f"  Rows received: {len(rows)}")

if not rows:
    sys.exit("No data returned")

raw_cols = list(rows[0].keys())
print(f"  Columns ({len(raw_cols)}): {raw_cols}")
print()


def find_col(cols, *substrings):
    for c in cols:
        if all(s.lower() in c.lower() for s in substrings):
            return c
    return None


# SQL endpoint returns display-name keys (not snake_case)
COL = {
    "prefix":      find_col(raw_cols, "Prefix") and find_col(raw_cols, "Prefix", "Number") is None and find_col(raw_cols, "Prefix") or
                   find_col(raw_cols, "Deficiency Prefix"),
    "tag_number":  find_col(raw_cols, "Tag Number"),
    "prefix_tag":  find_col(raw_cols, "Prefix and Number") or find_col(raw_cols, "Prefix and"),
    "description": find_col(raw_cols, "Description"),
    "category":    find_col(raw_cols, "Category"),
}
# Simpler fallback: direct known column names from probe
if not COL["prefix"]:
    COL["prefix"] = "Deficiency Prefix"
if not COL["tag_number"]:
    COL["tag_number"] = "Deficiency Tag Number"
if not COL["prefix_tag"]:
    COL["prefix_tag"] = "Deficiency Prefix and Number"
if not COL["description"]:
    COL["description"] = "Deficiency Description"
if not COL["category"]:
    COL["category"] = "Deficiency Category"

print("Column mapping:")
for k, v in COL.items():
    print(f"  {k:<14} {v or 'NOT FOUND'}")
print()

out = []
for r in rows:
    out.append({
        "tag_prefix":    r.get(COL["prefix"], ""),
        "tag_number":    r.get(COL["tag_number"], ""),
        "prefix_tag":    r.get(COL["prefix_tag"], ""),
        "description":   r.get(COL["description"], ""),
        "category":      r.get(COL["category"], ""),
    })

df = pd.DataFrame(out)

n = len(df)
if not (EXPECTED_MIN <= n <= EXPECTED_MAX):
    raise AssertionError(f"FAILED: {n} rows outside [{EXPECTED_MIN}, {EXPECTED_MAX}]")
print(f"PASS: {n} citation codes loaded")
print()

print("Category distribution:")
for cat, grp in df.groupby("category"):
    print(f"  {str(cat):<55} {len(grp):3} tags")

print()
print("Prefix distribution:")
for pfx, grp in df.groupby("tag_prefix"):
    print(f"  {str(pfx):<6} {len(grp):3} tags")

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)
print(f"\nOutput: {OUTPUT_FILE}  ({n} rows, {len(df.columns)} cols)")
print("Join key: tag_prefix + tag_number  -->  nh_deficiencies_national.csv")
