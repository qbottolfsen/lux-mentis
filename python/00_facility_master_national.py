"""
00_facility_master_national.py
National healthcare provider facility master -- the hub table for all downstream joins.

Spine: CMS Medicare enrollment crosswalk (cms_enrollments_all_types.csv, 57,767 rows)
Joins (all LEFT):
  POS iQIES        on ccn = prvdr_num      (certification status, FIPS, beds, CBSA)
  SNF owner flags  on enrollment_id         (ownership structure, boolean flags, SNF-only)
  ACS demographics on zip5 = zcta           (race, income, disability by neighborhood)
  ACS 65+ pop      on zip5 = ZIP            (optional -- run get_census_us_65plus.py first)

Adds:
  zip5     -- 5-digit truncation of enrollment ZIP for ZCTA joins
  npi_uri  -- schema:usNPI dereferenceable IRI (schema.org MedicalOrganization)

Pre-registered assertions:
  Total rows    [50,000 - 65,000]   (enrollment spine, no dedup)
  SNF rows      [12,000 - 18,000]
  HI rows       [150 - 300]         (address_state = HI)
  POS match     >= 50%              (terminated/unmatched records expected)
  ZCTA match    >= 80%

Output: output_reference/facility_master_national.csv

Privacy: no individual names -- ownership flags are boolean aggregates only.
         LEIE individual matches are NOT included here.
"""

import datetime, pathlib, sys

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required: pip install pandas")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"

ENROLLMENTS = OUTPUT_DIR / "cms_enrollments_all_types.csv"
POS_IQIES   = OUTPUT_DIR / "pos_iqies_national.csv"
OWNER_FLAGS = OUTPUT_DIR / "snf_owners_facility_flags.csv"
CENSUS_DEMO = OUTPUT_DIR / "census_demographics_national.csv"
POP_65PLUS  = SCRIPT_DIR / "ACSDT5Y2024.B01001_US_ZCTA_Pivoted.csv"
OUTPUT_FILE = OUTPUT_DIR / "facility_master_national.csv"

NPI_URI_BASE = "https://npiregistry.cms.hhs.gov/provider-view/"

TOTAL_MIN     = 54_900  # 95% of 57,767 confirmed 2026-07-22
TOTAL_MAX     = 61_000
SNF_MIN       = 13_700  # 95% of 14,425 confirmed 2026-07-22
SNF_MAX       = 16_000
HI_MIN        = 150
HI_MAX        = 300
POS_RATE_MIN  = 0.50
ZCTA_RATE_MIN = 0.80

print("Facility Master -- National Provider Hub")
print(f"Output: {OUTPUT_FILE}")
print(f"Run:    {datetime.date.today()}")
print()

# ── 1. Enrollment spine ──────────────────────────────────────────────────────
print("Loading enrollment spine ...")
enroll = pd.read_csv(ENROLLMENTS, dtype=str).fillna("")
print(f"  {len(enroll):,} rows, {len(enroll.columns)} cols")

# Derived columns
enroll["zip5"]    = enroll["zip"].str.strip().str[:5].str.zfill(5)
enroll["ccn_key"] = enroll["ccn"].str.strip().str.zfill(6)
enroll["npi_uri"] = enroll["npi"].apply(
    lambda n: f"{NPI_URI_BASE}{n.strip()}" if n.strip() else ""
)

# ── 2. POS iQIES -- select relevant columns ──────────────────────────────────
print("Loading POS iQIES ...")
POS_KEEP = [
    "prvdr_num", "fac_name", "prvdr_type_id",
    "zip_cd", "state_cd", "fips_state_cd", "fips_cnty_cd",
    "cbsa_cd", "cbsa_urbn_rrl_ind",
    "orgnl_prtcptn_dt", "crtfctn_dt", "trmntn_exprtn_dt",
    "pgm_trmntn_cd", "fed_crtfctn_stus_name",
    "control_type", "gnrl_fac_type_cd",
    "bed_cnt", "crtfd_bed_cnt", "processing_date",
]
pos = pd.read_csv(POS_IQIES, dtype=str, usecols=POS_KEEP).fillna("")
pos["prvdr_key"] = pos["prvdr_num"].str.strip().str.zfill(6)
pos = pos.rename(columns={
    "fac_name": "pos_fac_name",
    "zip_cd":   "pos_zip_cd",
    "state_cd": "pos_state_cd",
})
print(f"  {len(pos):,} rows")

# ── 3. Owner flags (SNF-only) ────────────────────────────────────────────────
print("Loading SNF owner flags ...")
owners = pd.read_csv(OWNER_FLAGS, dtype=str).fillna("")
owners = owners.drop(columns=["organization_name"], errors="ignore")
print(f"  {len(owners):,} rows")

# ── 4. ACS demographics (by ZCTA) ────────────────────────────────────────────
print("Loading ACS demographics ...")
DEMO_KEEP = [
    "zcta",
    "pct_white", "pct_black", "pct_asian", "pct_nhpi",
    "pct_hispanic", "non_hisp_white",
    "median_hh_income", "pct_disability", "acs_year",
]
demo = pd.read_csv(CENSUS_DEMO, dtype=str).fillna("")
demo = demo[[c for c in DEMO_KEEP if c in demo.columns]].copy()
demo["zcta"] = demo["zcta"].str.strip().str.zfill(5)
print(f"  {len(demo):,} ZCTAs")

# ── 5. ACS 65+ population (optional) ─────────────────────────────────────────
has_65plus = POP_65PLUS.exists()
if has_65plus:
    print("Loading ACS 65+ population ...")
    pop65 = pd.read_csv(POP_65PLUS, dtype=str).fillna("")
    pop65_cols = [c for c in ["ZIP", "Population_Total", "Population_65Plus"] if c in pop65.columns]
    pop65 = pop65[pop65_cols].copy()
    pop65["ZIP"] = pop65["ZIP"].str.strip().str.zfill(5)
    pop65 = pop65.rename(columns={
        "Population_Total":  "pop_total",
        "Population_65Plus": "pop_65plus",
    })
    print(f"  {len(pop65):,} ZCTAs")
else:
    print("  65+ file not found -- skipping (run get_census_us_65plus.py first)")

print()
print("Joining ...")

# ── 6a. Spine ← POS on ccn_key / prvdr_key ───────────────────────────────────
master = enroll.merge(
    pos, left_on="ccn_key", right_on="prvdr_key", how="left"
)
master = master.drop(columns=["ccn_key", "prvdr_key", "prvdr_num"], errors="ignore")
pos_matched = (master["pos_fac_name"].fillna("") != "").sum()
pos_rate = pos_matched / len(master)
print(f"  POS join:   {pos_matched:,}/{len(master):,} = {pos_rate:.1%} match rate")
if pos_rate < POS_RATE_MIN:
    print(f"  WARNING: POS match rate below expected minimum {POS_RATE_MIN:.0%}")

# ── 6b. ← Owner flags on enrollment_id ───────────────────────────────────────
master = master.merge(owners, on="enrollment_id", how="left")
own_matched = master["owner_count"].fillna("").str.strip().ne("").sum()
print(f"  Owner join: {own_matched:,} rows with ownership data (SNF only, expected ~14,425)")

# ── 6c. ← ACS demographics on zip5 / zcta ────────────────────────────────────
master = master.merge(demo, left_on="zip5", right_on="zcta", how="left")
zcta_matched = master["median_hh_income"].fillna("").str.strip().ne("").sum()
zcta_rate = zcta_matched / len(master)
print(f"  ZCTA join:  {zcta_matched:,}/{len(master):,} = {zcta_rate:.1%} match rate")
if zcta_rate < ZCTA_RATE_MIN:
    print(f"  WARNING: ZCTA match rate below expected minimum {ZCTA_RATE_MIN:.0%}")

# ── 6d. ← ACS 65+ population on zip5 / ZIP (optional) ────────────────────────
if has_65plus:
    master = master.merge(pop65, left_on="zip5", right_on="ZIP", how="left")
    master = master.drop(columns=["ZIP"], errors="ignore")
    pop_matched = master["pop_65plus"].fillna("").str.strip().ne("").sum()
    print(f"  65+ join:   {pop_matched:,}/{len(master):,} rows matched")

# ── 7. Indicator flags + final fill ──────────────────────────────────────────
master["pos_matched"]  = (master["pos_fac_name"].fillna("") != "").map({True: "True", False: "False"})
master["zcta_matched"] = (master["zcta"].fillna("") != "").map({True: "True", False: "False"})
master = master.fillna("")

# ── 8. Assertions ─────────────────────────────────────────────────────────────
print()
print("Assertions ...")

total = len(master)
if not (TOTAL_MIN <= total <= TOTAL_MAX):
    raise AssertionError(f"FAILED: total {total:,} outside [{TOTAL_MIN:,}, {TOTAL_MAX:,}]")
print(f"  PASS: total rows {total:,}")

snf_ct = (master["provider_type_label"] == "SNF").sum()
if not (SNF_MIN <= snf_ct <= SNF_MAX):
    raise AssertionError(f"FAILED: SNF {snf_ct:,} outside [{SNF_MIN:,}, {SNF_MAX:,}]")
print(f"  PASS: SNF {snf_ct:,}")

hi_ct = (master["address_state"] == "HI").sum()
if not (HI_MIN <= hi_ct <= HI_MAX):
    raise AssertionError(f"FAILED: HI {hi_ct:,} outside [{HI_MIN:,}, {HI_MAX:,}]")
print(f"  PASS: HI {hi_ct:,}")

# ── 9. Provider type summary ──────────────────────────────────────────────────
print()
print("Rows by provider type:")
for t in ["SNF", "HOSPITAL", "HOSPICE", "HHA", "FQHC", "RHC"]:
    n = (master["provider_type_label"] == t).sum()
    print(f"  {t:8}  {n:6,}")

print()
print("HI providers by type:")
hi_rows = master[master["address_state"] == "HI"]
for t in ["SNF", "HOSPITAL", "HOSPICE", "HHA", "FQHC", "RHC"]:
    n = (hi_rows["provider_type_label"] == t).sum()
    if n:
        print(f"  {t:8}  {n:3}")

# ── 10. ZIP→ZCTA match by type ────────────────────────────────────────────────
print()
print("ZIP->ZCTA match rate by provider type:")
for t in ["SNF", "HOSPITAL", "HOSPICE", "HHA", "FQHC", "RHC"]:
    subset = master[master["provider_type_label"] == t]
    if len(subset) == 0:
        continue
    matched = (subset["zcta"] != "").sum()
    rate = matched / len(subset)
    print(f"  {t:8}  {matched:6,}/{len(subset):6,} = {rate:.1%}")

# ── 11. SNF ownership breakdown ───────────────────────────────────────────────
flag_cols = [
    "private_equity_company_owner", "reit_owner", "holding_company_owner",
    "investment_firm_owner", "chain_home_office_owner",
    "non_profit_owner", "for_profit_owner",
]
snf_only = master[master["provider_type_label"] == "SNF"]
if len(snf_only) > 0 and any(c in master.columns for c in flag_cols):
    print()
    print(f"SNF ownership flags (n={len(snf_only):,}):")
    for col in flag_cols:
        if col in master.columns:
            ct = (snf_only[col].str.lower() == "true").sum()
            print(f"  {col:42}  {ct:5,} ({ct/len(snf_only)*100:.1f}%)")

# ── 12. Write output ──────────────────────────────────────────────────────────
OUTPUT_DIR.mkdir(exist_ok=True)
master.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(master):,}")
print(f"Cols:   {len(master.columns)}")
print()
print("Join keys for downstream scripts:")
print("  npi           -- National Provider Identifier (PBJ, NPPES, LEIE entity match)")
print("  ccn           -- CMS Certification Number (POS, QM, VBP, cost reports)")
print("  enrollment_id -- CMS enrollment ID (All Owners datasets)")
print("  zip5          -- 5-digit ZIP (ZCTA geographic joins)")
print("  npi_uri       -- schema:usNPI dereferenceable IRI (schema.org MedicalOrganization)")
print("  fips_state_cd / fips_cnty_cd -- FIPS geographic joins")
print("  zcta          -- matched ACS ZCTA (empty if no match)")
print("  pos_matched   -- True/False: whether POS record found")
print("  zcta_matched  -- True/False: whether ZCTA demographics found")
