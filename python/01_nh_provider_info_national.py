"""
01_nh_provider_info_national.py
Nursing Home Provider Information -- national Five-Star and staffing summary.

Source: CMS Provider Data -- Nursing Home Care Compare
  Dataset:      Provider Information (4pq5-n9py)
  Distribution: c977e9dc-c100-5531-aeb5-80cdff2eacc5
  Endpoint:     https://data.cms.gov/provider-data/api/1/datastore/query/{distId}
  Updated:      Monthly
  Columns:      99 (all exact names confirmed 2026-07-15)

One row per SNF/NF -- the Five-Star backbone for all downstream quality analysis.
Contains the following, pre-aggregated from their source datasets by CMS:
  Five-Star ratings:  Overall, Health Inspection, QM (long/short-stay), Staffing (1-5)
  Staffing HPRD:      Total, RN, LPN, CNA, Weekend Total, Weekend RN (from PBJ quarterly)
  Turnover:           Total nursing, RN (rates); administrator count
  Inspection:         Latest survey date, weighted health score, deficiency/penalty counts
  Program flags:      Special Focus Facility, Abuse Icon, chain affiliation
  Geography:          Lat/lon, county, urban/rural
  Acuity:             Nursing case-mix index

Pipeline-computed fields (lm_ prefix = not from CMS API):
  lm_rn_meets_3442f          True if reported RN HPRD >= 0.55 (CMS-3442-F counterfactual)
  lm_aide_meets_3442f        True if reported Nurse Aide (CNA) HPRD >= 2.45
  lm_total_meets_3442f       True if reported Total Nurse HPRD >= 3.48
  lm_rn_weekend_meets_3442f  True if Weekend RN HPRD >= 0.55
  lm_meets_3442f_thresholds  True if all four met
  lm_chain_affiliated        Y/N derived from chain_name presence

Output: output_reference/nh_provider_info_national.csv

Pre-registered assertions:
  Total rows:               [12,000 -- 17,000]
  HI rows:                  [38 -- 46]
  Rows with overall rating: > 80%  (some new/exempt may lack ratings)
"""

import json, pathlib, sys, time, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required: pip install pandas")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_FILE = OUTPUT_DIR / "nh_provider_info_national.csv"

DIST_ID   = "c977e9dc-c100-5531-aeb5-80cdff2eacc5"
BASE_URL  = f"https://data.cms.gov/provider-data/api/1/datastore/query/{DIST_ID}"
PAGE_SIZE = 500

EXPECTED_MIN = 12_000
EXPECTED_MAX = 17_000
HI_MIN = 38
HI_MAX = 46

# CMS-3442-F minimum staffing thresholds (Final Rule, Jun 2024)
RN_HPRD_MIN    = 0.55
AIDE_HPRD_MIN  = 2.45   # nurse aide (CNA) minimum — tested against cna_hprd
TOTAL_HPRD_MIN = 3.48   # total nurse minimum — tested against total_hprd

# Exact source column names (confirmed from full 99-column probe 2026-07-15)
SRC = {
    "ccn":               "cms_certification_number_ccn",
    "name":              "provider_name",
    "address":           "provider_address",
    "city":              "citytown",
    "state":             "state",
    "zip":               "zip_code",
    "phone":             "telephone_number",
    "county":            "countyparish",
    "urban":             "urban",
    "ownership":         "ownership_type",
    "provider_type":     "provider_type",
    "in_hospital":       "provider_resides_in_hospital",
    "legal_name":        "legal_business_name",
    "beds":              "number_of_certified_beds",
    "census":            "average_number_of_residents_per_day",
    # Five-Star ratings -- facility-level (not chain average)
    "overall_star":      "overall_rating",
    "inspection_star":   "health_inspection_rating",
    "qm_star":           "qm_rating",
    "longstay_qm_star":  "longstay_qm_rating",
    "shortstay_qm_star": "shortstay_qm_rating",
    "staffing_star":     "staffing_rating",
    # Staffing HPRD (reported = direct PBJ count, not case-mix adjusted)
    "total_hprd":        "reported_total_nurse_staffing_hours_per_resident_per_day",
    "rn_hprd":           "reported_rn_staffing_hours_per_resident_per_day",
    "lpn_hprd":          "reported_lpn_staffing_hours_per_resident_per_day",
    "cna_hprd":          "reported_nurse_aide_staffing_hours_per_resident_per_day",
    # Weekend HPRD -- 24/7 RN presence proxy for CMS-3442-F
    "rn_weekend_hprd":   "registered_nurse_hours_per_resident_per_day_on_the_weekend",
    "total_weekend_hprd":"total_number_of_nurse_staff_hours_per_resident_per_day_on_t_4a14",
    # Turnover
    "total_turnover":    "total_nursing_staff_turnover",
    "rn_turnover":       "registered_nurse_turnover",
    "admin_left_count":  "number_of_administrators_who_have_left_the_nursing_home",
    # Case-mix
    "casemix_index":     "nursing_casemix_index",
    # Program flags
    "sff":               "special_focus_status",
    "abuse_icon":        "abuse_icon",
    "chain_name":        "chain_name",
    "chain_id":          "chain_id",
    # Inspection detail
    "survey_date":       "rating_cycle_1_standard_survey_health_date",
    "health_defic_c1":   "rating_cycle_1_total_number_of_health_deficiencies",
    "weighted_health_score": "total_weighted_health_survey_score",
    "infection_control_citations": "number_of_citations_from_infection_control_inspections",
    # Penalties
    "fine_count":        "number_of_fines",
    "fine_total":        "total_amount_of_fines_in_dollars",
    "payment_denials":   "number_of_payment_denials",
    "total_penalties":   "total_number_of_penalties",
    # Geography
    "lat":               "latitude",
    "lon":               "longitude",
}


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_page(offset: int) -> dict:
    payload = json.dumps({"limit": PAGE_SIZE, "offset": offset}).encode()
    req = urllib.request.Request(
        BASE_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())


print("NH Provider Information -- national Five-Star and staffing summary")
print(f"Source distribution: {DIST_ID}")
print(f"Output: {OUTPUT_FILE}")
print()

print("Probing ...")
probe = fetch_page(0)
total_count = probe.get("count", 0)
raw_cols = list(probe["results"][0].keys()) if probe.get("results") else []
print(f"  Reported count: {total_count:,}  |  Columns: {len(raw_cols)}")

# Verify key columns present
missing = [label for label, col in SRC.items() if col not in raw_cols]
if missing:
    print(f"  WARNING: {len(missing)} expected columns not found in source: {missing}")
else:
    print(f"  All {len(SRC)} expected columns confirmed present")
print()

print(f"Fetching {total_count:,} rows (page size {PAGE_SIZE}) ...")
all_rows = list(probe.get("results", []))
offset = PAGE_SIZE
page_num = 1
print(f"  Page  1: offset=     0  got={len(all_rows):,}  total={len(all_rows):,}")

while len(all_rows) < total_count:
    page_num += 1
    result = fetch_page(offset)
    rows = result.get("results", [])
    if not rows:
        break
    all_rows.extend(rows)
    print(f"  Page {page_num:2}: offset={offset:6,}  got={len(rows):,}  total={len(all_rows):,}")
    if len(rows) < PAGE_SIZE:
        break
    offset += PAGE_SIZE
    time.sleep(0.3)

print(f"  Fetched {len(all_rows):,} rows")
print()


# ── Build output ───────────────────────────────────────────────────────────────

def safe_float(v):
    try:
        return float(str(v).strip()) if v not in (None, "", "N/A", "Not Available") else None
    except (ValueError, TypeError):
        return None


def g(row, key):
    return row.get(SRC[key], "") if key in SRC else ""


out_rows = []
for r in all_rows:
    total_hprd     = safe_float(g(r, "total_hprd"))
    rn_hprd        = safe_float(g(r, "rn_hprd"))
    cna_hprd       = safe_float(g(r, "cna_hprd"))
    rn_weekend     = safe_float(g(r, "rn_weekend_hprd"))

    rn_ok          = rn_hprd    >= RN_HPRD_MIN    if rn_hprd    is not None else None
    cna_ok         = cna_hprd   >= AIDE_HPRD_MIN  if cna_hprd   is not None else None
    total_ok       = total_hprd >= TOTAL_HPRD_MIN if total_hprd is not None else None
    rn_weekend_ok  = rn_weekend >= RN_HPRD_MIN    if rn_weekend is not None else None
    all_ok         = bool(rn_ok and cna_ok and total_ok and rn_weekend_ok)

    chain = g(r, "chain_name")
    chain_affiliated = "Y" if chain and str(chain).strip() not in ("", "N/A") else "N"

    out_rows.append({
        "ccn":                        g(r, "ccn"),
        "provider_name":              g(r, "name"),
        "legal_business_name":        g(r, "legal_name"),
        "address":                    g(r, "address"),
        "city":                       g(r, "city"),
        "state":                      g(r, "state"),
        "zip":                        g(r, "zip"),
        "phone":                      g(r, "phone"),
        "county":                     g(r, "county"),
        "urban_rural":                g(r, "urban"),
        "lat":                        g(r, "lat"),
        "lon":                        g(r, "lon"),
        "ownership_type":             g(r, "ownership"),
        "provider_type":              g(r, "provider_type"),
        "in_hospital":                g(r, "in_hospital"),
        "certified_beds":             g(r, "beds"),
        "avg_daily_census":           g(r, "census"),
        # Five-Star
        "overall_star":               g(r, "overall_star"),
        "health_inspection_star":     g(r, "inspection_star"),
        "qm_star":                    g(r, "qm_star"),
        "longstay_qm_star":           g(r, "longstay_qm_star"),
        "shortstay_qm_star":          g(r, "shortstay_qm_star"),
        "staffing_star":              g(r, "staffing_star"),
        # Staffing HPRD
        "total_hprd":                 "" if total_hprd is None else total_hprd,
        "rn_hprd":                    "" if rn_hprd    is None else rn_hprd,
        "lpn_hprd":                   g(r, "lpn_hprd"),
        "cna_hprd":                   g(r, "cna_hprd"),
        "rn_weekend_hprd":            "" if rn_weekend is None else rn_weekend,
        "total_weekend_hprd":         g(r, "total_weekend_hprd"),
        "casemix_index":              g(r, "casemix_index"),
        # Compliance flags (CMS-3442-F)
        "lm_rn_meets_3442f":          "" if rn_ok         is None else str(rn_ok),
        "lm_aide_meets_3442f":        "" if cna_ok        is None else str(cna_ok),
        "lm_total_meets_3442f":       "" if total_ok      is None else str(total_ok),
        "lm_rn_weekend_meets_3442f":  "" if rn_weekend_ok is None else str(rn_weekend_ok),
        "lm_meets_3442f_thresholds":  str(all_ok),
        # Turnover
        "total_nurse_turnover":       g(r, "total_turnover"),
        "rn_turnover":                g(r, "rn_turnover"),
        "admin_left_count":           g(r, "admin_left_count"),
        # Program flags
        "special_focus_status":       g(r, "sff"),
        "abuse_icon":                 g(r, "abuse_icon"),
        "lm_chain_affiliated":         chain_affiliated,
        "chain_name":                 g(r, "chain_name"),
        "chain_id":                   g(r, "chain_id"),
        # Inspection
        "latest_standard_survey":     g(r, "survey_date"),
        "health_defic_cycle1":        g(r, "health_defic_c1"),
        "weighted_health_score":      g(r, "weighted_health_score"),
        "infection_control_citations":g(r, "infection_control_citations"),
        # Penalties
        "fine_count":                 g(r, "fine_count"),
        "fine_total_dollars":         g(r, "fine_total"),
        "payment_denials":            g(r, "payment_denials"),
        "total_penalties":            g(r, "total_penalties"),
    })

df = pd.DataFrame(out_rows)


# ── Assertions ─────────────────────────────────────────────────────────────────

print("Assertions ...")

total = len(df)
if not (EXPECTED_MIN <= total <= EXPECTED_MAX):
    raise AssertionError(f"FAILED: total {total:,} outside [{EXPECTED_MIN:,}, {EXPECTED_MAX:,}]")
print(f"  PASS: total rows {total:,}")

hi = df[df["state"] == "HI"]
if not (HI_MIN <= len(hi) <= HI_MAX):
    raise AssertionError(f"FAILED: HI rows {len(hi)} outside [{HI_MIN}, {HI_MAX}]")
print(f"  PASS: HI rows {len(hi)}")

rated = df["overall_star"].replace("", None).notna().sum()
rated_pct = rated / total
if rated_pct < 0.80:
    raise AssertionError(f"FAILED: only {rated_pct:.1%} have overall rating")
print(f"  PASS: {rated_pct:.1%} of facilities have overall rating ({rated:,})")

rn_above    = (df["lm_rn_meets_3442f"]         == "True").sum()
tot_above   = (df["lm_total_meets_3442f"]      == "True").sum()
all_above   = (df["lm_meets_3442f_thresholds"] == "True").sum()
print(f"  INFO: RN HPRD >= 0.55 (3442-F threshold):          {rn_above:,} ({rn_above/total:.1%})")
print(f"  INFO: Total HPRD >= 3.48 (3442-F threshold):       {tot_above:,} ({tot_above/total:.1%})")
print(f"  INFO: Meets all 3442-F thresholds (counterfactual): {all_above:,} ({all_above/total:.1%})")


# ── Summary ────────────────────────────────────────────────────────────────────

print()
print("Five-Star distribution (overall):")
for star in ["5", "4", "3", "2", "1"]:
    n = (df["overall_star"].astype(str) == star).sum()
    bar = "#" * (n * 50 // total) if total else ""
    print(f"  {star} star: {n:5,} ({n/total*100:4.1f}%)  {bar}")

print()
print("Provider types:")
for pt, grp in df.groupby("provider_type"):
    n = len(grp)
    print(f"  {str(pt):<50} {n:6,} ({n/total*100:.1f}%)")

print()
print("Special program flags:")
sff_count    = df["special_focus_status"].str.strip().ne("").sum()
abuse_count  = df["abuse_icon"].str.strip().isin(["Y", "Yes", "yes"]).sum()
chain_count  = (df["lm_chain_affiliated"] == "Y").sum()
print(f"  Special Focus Facility:   {sff_count:,}")
print(f"  Abuse Icon:               {abuse_count:,}")
print(f"  Chain Affiliated:         {chain_count:,} ({chain_count/total:.1%})")

print()
hi_display = hi[["ccn", "provider_name", "overall_star", "rn_hprd",
                  "total_hprd", "lm_rn_meets_3442f", "lm_meets_3442f_thresholds",
                  "special_focus_status", "abuse_icon"]].copy()
hi_display = hi_display.sort_values("overall_star", ascending=False)
print(f"Hawaii facilities (n={len(hi)}):")
print(hi_display.to_string(index=False))


# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(df):,}")
print(f"Cols:   {len(df.columns)}")
print()
print("Join keys:")
print("  ccn  -->  facility_master_national.csv (ccn)")
print("       -->  nh_quality_measures, nh_penalties, nh_deficiencies, snf_vbp")
