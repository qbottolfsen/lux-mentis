# Lux Mentis
### National LTPAC Accountability Platform

A public-data accountability platform covering long-term and post-acute care (LTPAC) providers across all 50 states. Sources: CMS, OIG, Census Bureau, and publicly available HL7 FHIR-aligned data. No proprietary data, no claims data, no HIPAA-covered data anywhere in this project.

Two questions drive the work: where are elderly residents underserved by the supply of LTPAC providers, and of those providers, which carry the highest regulatory risk, financial stress, and workforce instability. Access and accountability are separate analytical layers on a shared data foundation. The data foundation comes first.

---

## Evidence Taxonomy

Every finding is assigned an evidence level. Nothing rises above Level 3 by design. This is a public-data observatory, not a regulatory body.

| Level | Label | Description |
|-------|-------|-------------|
| 1 | Observation | A data point exists. No claim of cause, pattern, or significance. |
| 2 | Association | Two variables move together. Directionality and magnitude noted. |
| 3 | Plausible Mechanism | An association is consistent with a known operational mechanism. |
| 4 | Finding | Validated conclusion supported by multiple independent data sources. *(Reserved for identity-confirmed, role-gated outputs only.)* |

---

## Findings

These observations come from CMS nursing home data current as of June 2026. The access layer (Phase 1, where elderly residents are underserved) has a known gap in five states until military installation ZIPs are populated — see Known Limitations. The regulatory and quality findings below are from Phase 2 CMS data, which is nationally complete.

**Universe note.** Five datasets cover different facility populations. The Medicare enrollment spine (14,425 facilities) is the declared denominator of record for percentage claims unless noted otherwise.

| Dataset | Rows | Unique CCNs | Notes |
|---------|------|-------------|-------|
| SNF Enrollments | 14,425 | 14,425 | Medicare-certified SNF spine; denominator of record |
| NH Provider Info (Care Compare) | 14,695 | 14,695 | +469 Medicaid-only NFs not in Medicare enrollment; −199 hospital-based swing beds (A-suffix CCNs) in enrollment but absent from Care Compare ratings |
| SNF Cost Report (HCRIS) | 14,933 rows | 14,120 | Multiple cost periods per facility; 13,644 enrolled facilities have a report; **781 enrolled with no cost report**; 476 CCNs filed but no longer in current enrollment |
| VBP Scored | 12,901 | 12,901 | Reconciled: 12,628 current enrolled + 273 prior-enrollment (scored on prior-year claims, since left current enrollment) = 12,901. 1,797 current enrolled below case minimum. 12,628 + 1,797 = 14,425 ✓ |
| PAC PUF | 14,161 | 14,161 | Facilities with sufficient Medicare PAC admissions to report |

**The accountability finding is not that the counts differ — it is what the gaps mean:**

- **199 Medicare-enrolled SNFs have no Care Compare rating.** A family checking a hospital-based swing bed facility finds nothing — not a low rating, no rating. These facilities are in the federal enrollment database but outside the quality-transparency system.
- **469 Medicaid-only NFs are on Care Compare but outside the Medicare payment-accountability machinery** — no VBP, no SNF QRP incentive structure, while serving predominantly Medicaid populations.
- **781 enrolled facilities have no cost report.** Financial stress analysis is structurally unavailable for them.

Staffing findings use the NH Provider Info universe (14,695). Deficiency and penalty rates use the enrollment spine (14,425). See `CORRECTIONS.md` for pending verification items.

### Value-Based Purchasing

78.6% of VBP-scored facilities (10,146 of 12,901) receive an incentive payment penalty (IPM < 1.0). 21.4% receive a bonus. None are neutral. 12,901 facilities are VBP-scored — 89.4% of all Medicare SNFs; the remainder fall below CMS's minimum case threshold. Of all SNFs nationally, 70.3% are receiving a VBP penalty. *(Level 1)*

### Staffing

**[PENDING — output CSV must be regenerated; see [CORRECTIONS.md](CORRECTIONS.md)]** The pipeline currently shows 74.5% of SNFs (10,951 of 14,695) with `meets_3442f_thresholds=False`. That figure was computed with an incorrect formula: the script applied the nurse aide threshold (2.45) to `total_hprd` (RN+LPN+CNA) rather than to the aide field (`cna_hprd`). The script is corrected; the corrected figure is **87.6% (12,868 of 14,695) — the share of SNFs that would not have met CMS-3442-F's final-state four-part standards** (RN HPRD ≥ 0.55, Weekend RN HPRD ≥ 0.55, Nurse Aide HPRD ≥ 2.45, Total Nurse HPRD ≥ 3.48). Both thresholds apply to `reported_*` (unadjusted PBJ) HPRD — confirmed by the rule text, which specifies enforcement independent of case-mix. This figure publishes once the output CSV is regenerated.

*Rule status and framing: CMS-3442-F was repealed — Public Law 119-21 (Jul 2025) prohibited enforcement; CMS formally repealed it (Federal Register, Dec 2025). Our June 2026 data is post-repeal. CMS does not publish a staffing compliance determination in the NH Provider Info API; `lm_meets_3442f_thresholds` is computed entirely by this pipeline. The 87.6% is a counterfactual: it describes how many facilities would not have met the final-state thresholds against a standard that was repealed before those thresholds fully took effect (Phase 3, requiring all four minimums, was scheduled for 2027–2029). *(See [CORRECTIONS.md](CORRECTIONS.md))*

National average RN HPRD is 0.68. National nurse turnover is 46.1%. Geographic concentration against the 3442-F RN HPRD threshold (0.55): Louisiana 85%, Oklahoma 65.7%, Arkansas 58.4%, Texas 54% — each has a majority of its SNFs below that floor. *(Level 1 — counterfactual; see [CORRECTIONS.md](CORRECTIONS.md))*

### Deficiency Citations

418,479 health citations across the survey history in CMS Care Compare as of June 2026. The file carries multiple survey cycles per facility; data spans back to 2017 for some facilities, with the most recent surveys through May 2026.

92.2% of all citations are Level 2 — no actual harm, potential above minimal (scope/severity D, E, or F). The remainder by tier:

- **Level 4 — Immediate jeopardy (J/K/L):** 9,661 citations; 4,406 facilities (30.5% of all SNFs) have at least one on record
- **Level 3 — Actual harm (G/H/I):** 13,426 citations (3.2%)
- **Abuse, neglect, or exploitation:** 31,362 citations at any severity level across 9,714 facilities; of those, 4,360 reached actual harm or above (G+) affecting 2,746 facilities (19.0% of all SNFs)
- **Infection control:** 31,757 citations

44.4% of all SNFs (6,405 facilities) have at least one fine on record in CMS penalty data as of June 2026; total on record: $436 million.

Top deficiency categories nationally: Quality of Life and Care (107,576), Resident Rights (64,317), Resident Assessment and Care Planning (60,991). *(Level 1)*

### Five-Star Component Distribution

Five-Star is a composite of three domains: health inspection, staffing, and quality measures. The table below shows how the constituent measures of two of those domains distribute across each star tier. These are not independently discovered relationships — citations feed the inspection domain, and RN HPRD and turnover feed the staffing domain. What the table shows is the magnitude of spread across tiers and the absence of any inversion: every measure moves in the same direction across all five levels without exception. *(Level 1)*

*Divergence note: CMS provides a `used_in_five_star` flag in both the MDS QM and claims QM datasets to indicate which quality measures are Five-Star inputs. Both flags are 100% null in the June 2026 pull — CMS stopped populating the field (confirmed in conformance harness; documented in `datasets_registry.json`). The inputs shown here are identified from the Five-Star Technical Users' Guide and CMS methodology documentation, not from the abandoned API flag. This is material to the circularity question: without a populated flag, the data cannot itself distinguish Five-Star-input QMs from non-input QMs.*

| Star | Facilities | Avg citations | RN HPRD | Nurse turnover |
|------|-----------|---------------|---------|----------------|
| 1 ★ | 2,873 | 47.2 | 0.50 | 54.9% |
| 2 ★ | 3,025 | 35.3 | 0.58 | 49.3% |
| 3 ★ | 2,844 | 26.4 | 0.63 | 46.2% |
| 4 ★ | 2,783 | 19.8 | 0.71 | 43.0% |
| 5 ★ | 3,045 | 12.8 | 0.95 | 38.2% |

1-star facilities average 47.2 citations and 0.50 RN HPRD. 5-star facilities average 12.8 citations and 0.95 RN HPRD. The gap is nearly 4x on citations and nearly 2x on RN hours per resident day.

### Financial

National median operating margin: -3.9%. 1,060 facilities with margin below -5%. Most states have a negative median. The states with the weakest median margins are DC, New Hampshire, and Pennsylvania, all near -10%. The industry's cost structure is operating at a loss in most markets. Operating margin figures for CCRCs and hospital-based SNFs are unreliable — see Known Limitations. *(Level 1)*

### State Rankings

Hawaii leads nationally on overall Five-Star at 3.59 (national average: 3.01). Missouri (2.48), Louisiana (2.51), and Illinois (2.56) are at the bottom. Texas has the highest immediate jeopardy citation rate per facility — 1.98 IJ citations per SNF, 2,326 total — and the second-highest penalty dollar total ($58M across 823 facilities). Illinois leads nationally in total fines at $70 million across 472 penalized facilities. Louisiana has 85% of its SNFs below the 0.55 RN HPRD counterfactual threshold. *(Level 1)*

**Hawaii: composite rating vs. inspection record.** Hawaii ranks first nationally in overall Five-Star (3.59), driven by a QM star of 4.5 and staffing star of 4.3. Its health inspection star is 2.9 — below the national average of 3.0. Separately, 14.3% of Hawaii's 42 SNFs carry active SFF or SFF Candidate status (1 active, 5 candidates), compared to 3.6% nationally (86 active SFF, 440 candidates). The state with the highest composite rating also carries roughly four times the national SFF concentration. These are not contradictory — the composite blends three domains, and they do not move together here. QM and staffing pull Hawaii's overall star up while the inspection domain lags. The most plausible mechanism is survey frequency: if Hawaii facilities receive more frequent standard surveys within CMS's regional scheduling, each facility accumulates more citation events over any fixed window, which suppresses the inspection star independent of underlying quality. That is a hypothesis, not a confirmed finding. *(Level 3 — plausible mechanism)*

---

## Architecture

Two layers run against the same data environment.

```
D:\national_ltpac\
├── sql\           Phase 1 — Access analysis (SQL Server + Census + NPI)
├── python\        Phase 2 — CMS quality, regulatory, and financial data
│   ├── 00_*.py         Level 0: foundation / reference tables
│   ├── 01–10_*.py      Level 2: NH quality, VBP, cost, survey
│   ├── reference_*.py  Reference crosswalks (F-tag, ICD-10, RBCS, taxonomy)
│   └── output_reference\   All generated CSVs (see Output Inventory below)
└── README.md
```

**Phase 1 (SQL)** builds the access analysis: Census 65+ population by ZCTA against LTPAC provider counts from NPPES. Outputs are SQL Server tables used for the access and gap analysis and state rankings.

**Phase 2 (Python)** builds the accountability layer: CMS quality measures, deficiency citations, penalties, VBP scores, cost report financials, staffing, and ownership data. Outputs are written to `output_reference/` as CSV or Parquet depending on file size (see Output Formats below).

**Build order:** Complete the data layer before any analytical or screening work. Within Phase 2, Level 0 (foundation) runs before Level 2 (quality and financial). The full provider type landscape (SNF, HHA, Hospice, Dialysis) needs to be in place before cross-provider analysis.

---

## Phase 1 — Access Analysis (SQL)

Run in order. Scripts 01-02 can run in parallel with 03-04 since Census and NPI loads are independent.

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `sql/01_census_national_create.sql` | Creates `ref.Census_US_65Plus` |
| 2 | `python/get_census_us_65plus.py` | Pulls all US ZCTA data from Census API. Verify ~33K rows before proceeding. |
| 3 | `sql/02_census_national_load.sql` | Bulk loads the Census CSV |
| 4 | `sql/03_us_ltpac_filter.sql` | Filters NPI to active LTPAC providers, all states |
| 5 | `sql/04_us_ltpac_by_zip.sql` | Aggregates by ZIP, carries State column |
| 6 | `sql/07_mil_installations_load.sql` | Populates military installation ZIPs from HIFLD. Complete before running step 7. |
| 7 | `sql/05_us_analysis.sql` | ZIP-level rates, flags, ZIPLabel |
| 8 | `sql/06_us_ltpac_by_state.sql` | State-level rollup |

**SQL tables created:**

| Table | Description |
|-------|-------------|
| `ref.Census_US_65Plus` | ~33K ZCTAs, all US |
| `dbo.US_LTPAC_Providers` | Active LTPAC providers, all states |
| `dbo.US_LTPAC_ByZIP` | Provider counts by ZIP with State column |
| `dbo.US_LTPAC_Analysis` | ZIP-level rates + reliability flags |
| `dbo.US_LTPAC_ByState` | State-level rollup |

**Reliability flags** use the three-tier system (`*`, `**`, `***`) from the Hawaii project. See that project's README for the "flag, don't drop" design rationale.

**Military installations:** `ref.MilitaryInstallation_ZIPs` was seeded by the Hawaii project. `sql/07_mil_installations_load.sql` contains INSERT templates for all other states; populate before running step 7. States with large military presences (CA, TX, VA, FL, NC) have the most impact on state rankings if left unpopulated.

---

## Phase 2 — CMS Quality & Regulatory Data (Python)

All scripts run from `D:\national_ltpac\python\`. Run Level 0 scripts first; Level 2 scripts depend on the foundation they establish. Reference crosswalks can run at any time.

### Level 0 — Foundation Data

| Script | Output | Rows | Description |
|--------|--------|------|-------------|
| `00_snf_enrollments_national.py` | `snf_enrollments_national.csv` | 14,425 | All Medicare-certified SNFs with NPI + CCN crosswalk |
| `00_snf_owners_national.py` | `snf_owners_national.csv` *(gitignored)* | 280,207 | Raw ownership records (individual names; gitignored) |
| | `snf_owners_facility_flags.csv` | 14,425 | Per-facility PE/REIT/holding company flags (public) |
| `00_pos_iqies_national.py` | `pos_iqies_national.parquet` | 77,283 | All active provider types (182 cols) including NF, ALF, CCRC |
| `00_cms_enrollments_all_types.py` | `cms_enrollments_all_types.csv` | 57,767 | All Medicare-enrolled provider types with NPI |
| `00_facility_master_national.py` | `facility_master_national.csv` | 57,767 | Facility spine with CCN + NPI + geography (60 cols) |
| `00_census_demographics_national.py` | `census_demographics_national.csv` | 33,772 | ACS 5-year demographics by ZCTA |
| `00_leie_national.py` | `leie_national.csv` *(gitignored)* | 83,665 | OIG exclusion list (individual names; gitignored) |

The `compliance_calendar_national.py` script generates `compliance_calendar_national.csv` (57,767 rows x 27 cols) and `compliance_hotlist_national.csv` (14,425 rows) from the facility master and enrollment data. Run after `00_facility_master_national.py`.

### Level 2 — NH Quality, Regulatory, Financial

All Level 2 scripts pull from the CMS Provider Data DKAN API. Run in any order after Level 0 is complete.

| Script | Output | Rows | Description |
|--------|--------|------|-------------|
| `01_nh_provider_info_national.py` | `nh_provider_info_national.csv` | 14,695 | Five-Star ratings, staffing HPRD, turnover, SFF flags |
| `02_nh_deficiencies_national.py` | `nh_health_deficiencies_national.parquet` | 418,479 | Citation-level health deficiencies with F-tag + scope/severity |
| | `nh_fire_deficiencies_national.parquet` | 200,030 | Citation-level fire safety deficiencies |
| `03_nh_penalties_national.py` | `nh_penalties_national.csv` | 15,181 | Individual penalty events (fines + payment denials) |
| | `nh_penalties_by_facility.csv` | 6,405 | Per-CCN penalty aggregates |
| `04_nh_quality_measures_national.py` | `nh_mds_qm_national.parquet` | 249,815 | MDS-based quality measures (17 per facility) |
| | `nh_claims_qm_national.parquet` | 58,780 | Claims-based QMs (4 risk-adjusted measures) |
| | `nh_qrp_national.parquet` | 837,615 | SNF Quality Reporting Program measures (57 per facility) |
| `05_snf_vbp_national.py` | `snf_vbp_national.csv` | 12,901 | VBP performance scores + IPM multiplier |
| `06_pac_puf_national.py` | `pac_puf_national.csv` | 14,161 | PAC utilization, therapy intensity, diagnosis mix (71 cols) |
| `07_snf_cost_report_national.py` | `snf_cost_report_national.csv` | 14,933 | HCRIS: payer mix, operating margin, occupancy (24 cols) |
| `08_nh_survey_summary_national.py` | `nh_survey_summary_national.csv` | 42,953 | Deficiency category totals per survey cycle (42 cols) |
| `10_nh_state_benchmarks_national.py` | `nh_state_benchmarks_national.csv` | 54 | State and national averages for all Five-Star fields |

Script `09_vbp_performance.py` generates analytical summaries in `output_vbp/national/` and `output_vbp/HI/`. Run after `05_snf_vbp_national.py`.

### Reference Crosswalks

No dependencies. Run at any time.

| Script | Output | Rows | Description |
|--------|--------|------|-------------|
| `reference_ftag_citations.py` | `reference_ftag_citations.csv` | 643 | All F/K/E-tags with category and severity tier |
| `reference_icd10_ccsr.py` | `icd10_ccsr_reference.csv` | 75,725 | ICD-10-CM codes mapped to CCSR categories |
| `reference_measure_intervals.py` | `reference_measure_intervals.csv` | 47 | QM measure codes with collection periods |
| `reference_rbcs_crosswalk.py` | `reference_rbcs_crosswalk.csv` | 18,384 | HCPCS to RBCS procedure categories; 99307-99310 = SNF E&M |
| `reference_npi_taxonomy_crosswalk.py` | `reference_npi_taxonomy_crosswalk.csv` | 67 | Medicare specialty codes (alphanumeric: C6, B4, etc.) to taxonomy |

**Taxonomy note:** The 67-row CMS crosswalk covers newer alphanumeric specialty codes only. It does not include the full NUCC taxonomy code set or the classic physician specialty numbers (01-99). The authoritative source is the NUCC provider taxonomy CSV at nucc.org. Phase 3 physician analysis requires that file before SNF attendance analysis can run.

---

## Gitignore Policy

| Pattern | Reason |
|---------|--------|
| `python/output_reference/leie_national.csv` | Individual names, DOBs, exclusion history (role-gated) |
| `python/output_reference/snf_owners_national.csv` | Individual owner names (role-gated) |
| `*.env`, `.env` | API keys |
| `__pycache__/`, `*.pyc` | Build artifacts |

The public-facing facility-level flags (`snf_owners_facility_flags.csv`, compliance outputs) contain no individual names and are committed to the repository.

**LEIE match policy:** Name matches between CMS ownership records and the OIG LEIE are Level 1 (Observation) only. Individual match details are never a public product. They are held in access-controlled local logs and require confirmed identity (DOB + state + NPI cross-reference) before any finding is reported. Facility-level flags (CCN, exclusion type code, verification status) are public.

---

## Output Formats

Most files in `output_reference/` are CSV. Six write to Parquet (`.parquet`, pyarrow backend):

| File | Parquet size | CSV equivalent |
|------|-------------|----------------|
| `pos_iqies_national.parquet` | 6.7 MB | 166 MB |
| `nh_health_deficiencies_national.parquet` | 3.2 MB | 150 MB |
| `nh_fire_deficiencies_national.parquet` | 1.6 MB | 61 MB |
| `nh_mds_qm_national.parquet` | 4.4 MB | 48 MB |
| `nh_qrp_national.parquet` | 1.8 MB | 83 MB |
| `nh_claims_qm_national.parquet` | 1.6 MB | 10 MB |

The original CSVs for these six files ranged from 10 MB to 166 MB. Three were over GitHub's 100 MB per-file hard limit, and the others were close enough to matter. The options were to drop columns, gzip the CSVs, or switch to Parquet. Dropping columns was ruled out immediately. That kind of decision gets made upfront, before Phase 3 analysis runs, which is exactly when you can't know what a later script will need. The goal was to change the container without touching the data.

Parquet with pyarrow keeps every row and every column. It reads back into pandas with `pd.read_parquet()` the same way CSV reads work everywhere else in the pipeline. The data types survive the round trip without being re-parsed from strings, so numeric fields come back as numbers instead of objects. The files are 6 to 50 times smaller than the CSV equivalents.

The CSV versions of these six files are excluded in `.gitignore`. Anyone who has them locally from a run before this change can keep them; the scripts write Parquet going forward.

```python
# Read example -- same pattern as the CSV reads in every other script
df = pd.read_parquet("output_reference/nh_health_deficiencies_national.parquet")
```

---

## Conformance Harness

`python/health_check.py` runs structural conformance checks against every output file in the pipeline. Run after any re-pull or schema-affecting change.

```
python python\health_check.py              # local files only
python python\health_check.py --live       # also fetches 1-row sample from live API
python python\health_check.py --dataset nh_provider_info  # single dataset
```

Seven checks per dataset: fields in API not in our output (missed data), fields in output not in API (CMS renamed or dropped), type anomalies, null-rate anomalies (≥95% null), constant-value fields, column-name divergence across access methods, row-count anomalies. Each finding is tiered BLOCKING (touches a published finding), LATENT (touches a field we will use), or INFO (touches nothing current).

Known patterns — field is expected null, expected constant, or a documented CMS behavioral decision — are registered in `python/datasets_registry.json` with a `known_anomalies` entry explaining why. The harness skips them on subsequent runs and reports only new findings. The distinction between "known expected" and "newly appeared" is preserved in the report.

Output: `python/output_reference/divergence_report.json` — machine-readable, committed to repo, regenerated on every run.

**Current status (2026-07-15):** BLOCKING=2, LATENT=2.
- [BLOCKING] `facility_master.individual_owner_count` — 25% parseable as numeric; blocks identity-gap quantification; investigate before Phase 3 owner analysis
- [BLOCKING] `facility_master.owner_count` — 25% parseable as numeric; same issue (was accidentally suppressed in prior harness run; now surfaced)
- [LATENT] `census_demographics.pct_disability` — 98.3% null; ACS S1811 ZCTA coverage gap
- [LATENT] `reference_measure_intervals.measure_date_range` — 100% null; computed field not populated

---

## Phase 3 — Planned

The national SNF data layer is complete. Phase 3 pulls the remaining LTPAC provider types and adds supporting data sources. Same rule: data layer for each provider type before any cross-provider analysis.

### LTPAC Provider Types (not yet pulled)

| Provider Type | CMS Dataset | Notes |
|---------------|-------------|-------|
| Home Health Agencies | `6jpm-sxkc` (provider info), `97z8-de96` (national averages) | Same DKAN pattern as NH |
| Hospice | `yc9t-dgbk` (general info), `252m-zfp9` (provider data) | Same DKAN pattern as NH |
| Dialysis / ESRD | `23ew-n7w9` (facility listing) | Same DKAN pattern |
| IRF / LTACH | PAC PUF already pulled with SNF-only filter | Expand filter to all post-acute types |

### Additional Data Sources

| Source | Data | Notes |
|--------|------|-------|
| HRSA shortage areas | HPSA/MUA flags by FIPS | Access and workforce context |
| SAM.gov exclusions | Entity-level debarment and exclusion | Key expires 2026-10-13; cross-reference with LEIE |
| PBJ raw daily staffing | Raw staffing by day + employee type | `7e0d53ba` (nurse), `b497431a` (non-nurse) |
| CMS Physician/Supplier Procedure Summary | HCPCS 99307-99310 SNF E&M visit counts | Requires NUCC taxonomy CSV first |
| NUCC taxonomy CSV | Full provider taxonomy code set | Download from nucc.org; replaces the 67-row CMS crosswalk |

---

## Publication Direction

Two publication standards apply.

**DCAT-US v3.0** covers dataset catalog entries (data.gov or platform-native catalog). Required fields: identifier, spatial, temporal, distribution, and publisher per the GSA schema.

**HL7 FHIR R4 (US Core STU 9)** covers interoperability with health systems. Facility data maps to FHIR resource types as follows:

| Platform Data | FHIR Resource |
|---------------|---------------|
| Facility spine (CCN, NPI, address, type) | `Organization` + `Location` |
| Physician/practitioner data | `Practitioner` + `PractitionerRole` |
| Quality measure scores | `MeasureReport` |
| Deficiency citations | `DetectedIssue` |
| Staffing data | `Coverage` / custom extension |

FHIR output is a Phase 3 task. Current CSVs are the internal data layer. Do not design CSV schemas around FHIR yet. Design them for analytical correctness and map to FHIR at publication time.

---

## API Patterns

Two CMS API patterns are in use. Know which one a dataset requires before writing a new script.

**DKAN JSON POST:** CMS Provider Data (Care Compare) datasets.
```
POST https://data.cms.gov/provider-data/api/1/datastore/query/{dist_id}
Body: {"limit": 1000, "offset": 0, "filters": {}}
```
Returns snake_case keys. Columns longer than 55 characters get a hash-truncated suffix (e.g., `_4a14`). Paginate by offset until results length < limit. Used by scripts 01-08, 10, and reference crosswalks that use DKAN dist_ids.

**data-api v1 GET:** CMS research and administrative datasets.
```
GET https://data.cms.gov/data-api/v1/dataset/{UUID}/data?filter[FIELD]=VALUE&size=500&offset=N
```
Returns plain JSON array. Paginate until empty or length < page_size. Used by Level 0 scripts, PAC PUF (06), SNF Cost Report (07), and reference crosswalks that use UUIDs.

**Column name resolution:** Use the `find_col()` helper (defined in each script) to match columns by case-insensitive substring, with an `exclude=` parameter to skip unwanted matches. Do not hardcode column names; they differ between DKAN snake_case and data-api title case.

**Caching:** Large national datasets cache to `output_reference/cache/*.csv.gz` with an 8-day TTL. Pass `--refresh` to force a re-fetch.

**Column gotchas confirmed from data:**
- SNF Cost Report: use `SNF Days Title XVIII/XIX/Total` and `SNF Bed Days Available`, NOT `Total Days Title X` variants (those are VA-only days and will corrupt payer mix calculations)
- State benchmarks: aggregate row uses `"NATION"` not `"US"` in the state identifier column
- PAC PUF: `filter[SMRY_CTGRY]=PROVIDER` to get facility-level rows only

---

## Data Sources

All data is publicly available. No proprietary, claims, or HIPAA-covered data is used anywhere in this project.

| Dataset | Source | API Pattern | Vintage |
|---------|--------|-------------|---------|
| SNF Enrollments | [CMS](https://data.cms.gov/provider-data/dataset/ynj2-r877) | data-api v1 | Jun 2026 |
| SNF All Owners | [CMS](https://data.cms.gov/provider-data/dataset/y2hd-n93e) | DKAN POST | Jun 2026 |
| POS iQIES | [CMS](https://data.cms.gov/provider-data/dataset/78qn-5c2k) | data-api v1 | Jun 2026 |
| OIG LEIE | [OIG](https://oig.hhs.gov/exclusions/exclusions_list.asp) | Bulk CSV download | Jul 2026 |
| NH Provider Info | [CMS](https://data.cms.gov/provider-data/dataset/4pq5-n9py) | DKAN POST | Jun 2026 |
| NH Health Deficiencies | [CMS](https://data.cms.gov/provider-data/dataset/r5ix-sfxw) | DKAN POST | Jun 2026 |
| NH Fire Deficiencies | [CMS](https://data.cms.gov/provider-data/dataset/uqmn-txpn) | DKAN POST | Jun 2026 |
| NH Penalties | [CMS](https://data.cms.gov/provider-data/dataset/g6vv-u9sr) | DKAN POST | Jun 2026 |
| NH Quality Measures (MDS) | [CMS](https://data.cms.gov/provider-data/dataset/djen-97ju) | DKAN POST | Jun 2026 |
| NH Quality Measures (Claims) | [CMS](https://data.cms.gov/provider-data/dataset/ijh5-nb2v) | DKAN POST | Jun 2026 |
| SNF QRP Measures | [CMS](https://data.cms.gov/provider-data/dataset/s27t-fmkv) | DKAN POST | Jun 2026 |
| SNF VBP Performance | [CMS](https://data.cms.gov/provider-data/dataset/gevg-xm8s) | DKAN POST | FY2026 |
| PAC PUF | [CMS](https://data.cms.gov/Medicare-Post-Acute-Care-and-Hospice/Post-Acute-Care-and-Hospice-Public-Use-File/a4wi-zeqm) | data-api v1 | RY2025 |
| SNF Cost Report (HCRIS) | [CMS](https://data.cms.gov/provider-data/dataset/rkq7-bekx) | data-api v1 | FY2023 |
| NH Survey Summary | [CMS](https://data.cms.gov/provider-data/dataset/tbry-pc2d) | DKAN POST | Jun 2026 |
| NH State Benchmarks | [CMS](https://data.cms.gov/provider-data/dataset/xcdc-v8bm) | DKAN POST | Jun 2026 |
| RBCS Crosswalk | [CMS](https://data.cms.gov/Medicare-Part-B-National-Summary-Data-File/Restructured-BETOS-Classification-System/p9hm-gnbi) | data-api v1 | Current |
| ICD-10-CM / CCSR | [AHRQ](https://www.hcup-us.ahrq.gov/toolssoftware/ccsr/ccs_refined.jsp) | Bulk download | FY2025 |
| ACS 5-Year (Census) | [Census Bureau](https://data.census.gov/table/ACSDT5Y2024.B01001) | Census API | 2024 5-Year |
| CMS NPPES NPI | [CMS](https://npiregistry.cms.hhs.gov/) | Bulk download (loaded in SQL) | Mar 2026 |
| NUCC Taxonomy | [NUCC](https://www.nucc.org/index.php/code-sets-mainmenu-41/provider-taxonomy-mainmenu-40/csv-mainmenu-57) | CSV download (needed for Phase 3) | v25.1 |

---

## How to Run

**Prerequisites:**
```
Python 3.13+
pip install pandas requests pyarrow
```

**Phase 1 (SQL):** Requires SQL Server 2025 with the `HEALTHCARE_DATA` database from the Hawaii project. NPI and NUCC tables (`dbo.NPIData`, `ref.NUCC_Taxonomy`) are already loaded nationally.

**Phase 2 (Python) — execution order:**
```
# Level 0: Foundation (run first; order within group does not matter)
python python\00_snf_enrollments_national.py
python python\00_pos_iqies_national.py
python python\00_cms_enrollments_all_types.py
python python\00_snf_owners_national.py
python python\00_facility_master_national.py
python python\00_leie_national.py
python python\00_census_demographics_national.py
python python\compliance_calendar_national.py

# Reference crosswalks (any time)
python python\reference_ftag_citations.py
python python\reference_icd10_ccsr.py
python python\reference_measure_intervals.py
python python\reference_rbcs_crosswalk.py
python python\reference_npi_taxonomy_crosswalk.py

# Level 2: Quality / Financial (after Level 0)
python python\01_nh_provider_info_national.py
python python\02_nh_deficiencies_national.py
python python\03_nh_penalties_national.py
python python\04_nh_quality_measures_national.py
python python\05_snf_vbp_national.py
python python\06_pac_puf_national.py
python python\07_snf_cost_report_national.py
python python\08_nh_survey_summary_national.py
python python\10_nh_state_benchmarks_national.py
```

Each script prints pre-registered assertion counts and exits with a non-zero code if output row counts or column names deviate from expected values. Do not proceed past a failed assertion. The script will describe the mismatch.

On Windows, if encoding issues occur:
```
$env:PYTHONIOENCODING="utf-8"; python python\01_nh_provider_info_national.py
```

---

## Known Limitations

**SNF-only in current build.** Phase 2 covers skilled nursing facilities. Home health, hospice, dialysis, IRF, and LTACH are planned for Phase 3 but not yet pulled. Cross-provider-type analysis requires all types to be present.

**LEIE matches are name-only observations.** No confirmed findings. DOB, state, and NPI cross-reference are required before reporting any individual. Individual match details are never published without confirmed identity.

**NUCC taxonomy crosswalk incomplete.** The 67-row CMS taxonomy file covers newer alphanumeric Medicare specialty codes (C6=Hospitalist, C0=Sleep Medicine, etc.) but not the classic physician specialty range (01-99). The full NUCC taxonomy CSV from nucc.org is required before Phase 3 physician SNF attendance analysis can run.

**PAC PUF SNF filter only.** `pac_puf_national.csv` was pulled with `filter[SMRY_CTGRY]=PROVIDER` and contains all SNFs. The same UUID (`eaed338b`) contains IRF, LTACH, and HHA rows. Re-pull without the SNF filter for Phase 3 multi-provider analysis.

**BCDA (bulk claims) requires institutional access.** The CMS Beneficiary Claims Data API is not available to individual researchers. Blue Button 2.0 is beneficiary-consent only. Claims-based quality measures from the existing CMS QM pull are the available proxy for outcomes.

**Cost report margins unreliable for CCRCs and hospital-based SNFs.** HCRIS `net patient revenue` does not capture entrance fee revenue for continuing care retirement communities or cost-allocated revenue for hospital-based SNFs. Operating margin for these facility types should not be compared to standard SNF margins.

**VBP NULL sentinel.** CMS uses `---` (three dashes) to indicate facilities that did not meet minimum case thresholds for VBP scoring. This is parsed to NaN in the pipeline output and is not a data error. Affects approximately 3% of facilities nationally.

**State benchmarks aggregate row.** The NH State Benchmarks dataset uses `"NATION"` (not `"US"`) as the identifier for the national aggregate row. Scripts that compare to national averages must match on `"NATION"`.

---

## Commercial Use

This repository is a public, timestamped record of original analytical work. The methodology is the work: the architecture decisions, the source verification approach, the documented rationale for each pivot when assumptions were corrected by authoritative data. Commit timestamps and script docstrings preserve that record.

**Free use covers:** research, education, journalism, policy analysis, and non-commercial public interest work.

**Licensing is required for:** incorporating this framework into a commercial product, selling or sublicensing outputs derived from this methodology, or building derivative commercial tools (health plan analytics, compliance software, credentialing systems, risk scoring products).

**Tiered access model:**

| Tier | Audience | Content | Access |
|------|----------|---------|--------|
| Public | Anyone | Facility-level regulatory flags, quality data, workforce signals | Open (this repository) |
| Professional | Health plans, compliance teams, post-acute consultants | Verified findings with source chains | Licensed, account-gated |
| Restricted | Credentialing admins, compliance officers, investigators | Identity-confirmed individual findings | EMR/ADP system integration only (admin role, audit-logged; never standalone) |

The individual findings tier is not a public product. Confirmed individual adverse findings belong inside systems with role-based access controls and organizational accountability.

Contact: qbottolfsen@gmail.com

---

*SNF data vintages: CMS NH Jun 2026 · PBJ 2023Q1-2025Q4 · VBP FY2026 · HCRIS FY2023 · OIG LEIE Jul 2026 · ACS 2024 5-Year · Phase 2 build completed 2026-07-15*
