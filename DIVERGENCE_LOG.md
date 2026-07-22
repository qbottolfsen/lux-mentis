# Lux Mentis — Divergence Log

Structured record of every divergence encountered — whether from our own code (INTERNAL), from
an agency's documented behavior (EXTERNAL-DOCUMENTED), or from unexplained source behavior
(EXTERNAL-UNDOCUMENTED). A resolved-internally issue still gets logged. No silent workaround.

**Boundary with CORRECTIONS.md:** CORRECTIONS.md records our published figures that changed —
what we said, what replaced it, why. This log records *source and pipeline divergences* — issues
with data provenance, schema, or behavior, and how we handled them. Many CORRECTIONS.md entries
have a corresponding log entry here; the two cross-reference each other.

**Self-resolving divergences:** if a divergence closes on a later pull with no agency documentation
explaining the change, it does not get marked closed and forgotten. It gets flagged MONITORING with
a note that it resolved without explanation. The vintage archive is the evidence base that makes
a self-resolving divergence provable rather than a memory. See B-note in directive 2026-07-21.

**Tiered claims:** entries carry the same protocol tiers as all other work product:
VERIFIED / CORROBORATED / INFERRED / ASSUMED.

---

## Log Entries

---

### LMDL-001

**Date observed:** 2026-07-21
**Date resolved:** 2026-07-21
**Title:** VBP script 05 pagination bug — 999 facilities silently dropped

**What it was:** `05_snf_vbp_national.py` produced 12,901 rows when the CMS DKAN API reported
a total count of 13,900 for distribution `cf1f058c-65d6-5496-9770-a244cfab2a13`. The 999-row gap
caused three published figures to be wrong.

**The error as it appeared:**
- `snf_vbp_national.csv`: 12,901 rows
- CMS DKAN API probe (`{"limit":1,"offset":0}`) returns `"count": 13900`
- Script 09 (independent direct-CSV download, same dataset): 13,900 rows
- All 12,901 CCNs in script 05 were present in script 09; 999 CCNs in script 09 were absent from
  script 05
- Missing states: AK (10), AL (224 of 225), AR (211), AZ (138), CA (416 of 1,084)

**Classification:** INTERNAL — our pagination bug. API was correct throughout.

**Root cause (VERIFIED):**
```python
# Buggy pattern:
all_rows = list(probe.get("results", []))  # probe = 1 row at offset 0
offset = PAGE_SIZE   # 1,000
# loop starts at offset 1,000 → rows at indices 1–999 are never fetched
```
The probe call (limit=1, offset=0) returned 1 row, which was added to `all_rows`. The main loop
then started at `offset = PAGE_SIZE = 1000`, skipping API result indices 1 through 999. The API
sorts facilities by an internal order placing AK/AL/AR/AZ/partial-CA first.

**Interim handling:** Published figures 78.6% (of VBP-scored) and 70.3% (of all SNFs) were derived
from the incomplete 12,901-row output. The 78.6% headline was arithmetically stable
(78.65% buggy vs 78.56% corrected, both round to 78.6%); the 70.3% "of all SNFs" figure was
materially wrong by 4 percentage points.

**Impact trace:**
- `snf_vbp_national.csv` — output file, directly wrong (12,901 rows instead of 13,900)
- README.md VBP section — three published figures affected:
  - "10,146 of 12,901" → corrected "10,920 of 13,900" (78.6% same)
  - "89.4% of all Medicare SNFs" → corrected "94.4%"
  - "70.3% of all SNFs nationally" → corrected "74.3%"
- README.md universe table row — reconciliation math updated
- Any downstream script joining on `snf_vbp_national.csv` would have been missing AK/AL/AR/AZ/CA rows
- `snf_vbp_detail` (script 09) was unaffected — independent API path, always had 13,900
- HI facilities: unaffected (39 correct in both outputs)
- Conformance harness: `snf_vbp` FINDING_FIELDS includes `incentive_payment_multiplier` and
  `performance_score` — harness did not detect the row count error because EXPECTED_MIN was 8,000,
  far below 12,901. EXPECTED_MIN updated to 13,000 post-fix.

**Agency/agencies involved:** N/A (internal bug)

**Status:** RESOLVED-INTERNAL

**Resolution:** Fixed pagination in `05_snf_vbp_national.py` — probe is now for count/schema
only; data fetch starts at offset 0. EXPECTED_MIN tightened from 8,000 to 13,000. CSV regenerated
2026-07-21: 13,900 rows confirmed. README and CORRECTIONS.md updated. See CORRECTIONS.md entry
2026-07-21.

---

### LMDL-002

**Date observed:** 2026-07-11 (first documented in audit)
**Date resolved:** N/A
**Title:** Five CMS datasets return materially different facility universes for the same provider type

**What it was:** The five primary SNF/NH datasets return different row counts, none of which are
simple subsets of each other. No single CMS dataset covers all SNFs for all purposes.

**The error as it appeared (CORROBORATED):**
| Dataset | Rows | Gap vs enrollment spine |
|---------|------|------------------------|
| SNF Enrollments (Medicare-certified) | 14,425 | baseline |
| NH Provider Info (Care Compare) | 14,695 | +270: includes 469 Medicaid-only NFs; −199 A-suffix swing beds absent from Care Compare |
| SNF Cost Report (HCRIS FY2023) | 14,933 rows / 14,120 unique CCNs | 13,644 enrolled with report; 781 enrolled with no cost report; 476 filed but not current |
| VBP Participants (FY2026) | 13,900 | 812 enrolled below case minimum; 287 prior-enrollment |
| PAC PUF | 14,161 | facilities with sufficient PAC admissions to report |

**Classification:** EXTERNAL-DOCUMENTED — each dataset's exclusion logic is documented by CMS
in the relevant dataset user guides and technical notes. The gaps are by design.

**Interim handling:** Denominator of record declared explicitly in README: "Medicare enrollment
spine (14,425) is the declared denominator of record for percentage claims unless noted otherwise."
Universe table in README documents the discrepancies and their meaning.

**Impact trace:**
- All percentage figures in README must specify which universe they use
- Staffing figures use NH Provider Info (14,695); deficiency/penalty rates use enrollment (14,425)
- The 781 enrolled facilities with no cost report create a structural gap in financial stress analysis
- The 199 Care-Compare-invisible facilities cannot receive Five-Star ratings
- 469 Medicaid-only NFs carry no VBP, QRP, or Medicare payment accountability

**Agency/agencies involved:** CMS (multiple programs)

**Status:** MONITORING — gaps exist by CMS design but the absolute counts shift with each
quarterly/annual refresh. Flag if any universe count moves by more than 2% on a re-pull.

**Resolution:** Not applicable (documented CMS behavior). Tracked here as a reference entry
for any downstream analysis that must navigate the universe question.

---

### LMDL-003

**Date observed:** 2026-07-11 (first documented in conformance harness)
**Date resolved:** N/A
**Title:** `used_in_five_star` flag — 100% null in both MDS QM and claims QM datasets, no CMS announcement

**What it was:** The CMS NH Provider Info and Quality Measures APIs include a `used_in_five_star`
flag intended to mark which quality measures are inputs to the Five-Star composite rating. Both
MDS QM and claims QM instances of this field are 100% null in the June 2026 pull. CMS appears
to have stopped populating the field without public documentation of the change.

**The error as it appeared:**
- `nh_mds_qm_national.parquet`: `used_in_five_star` — 100% null (249,815 rows)
- `nh_claims_qm_national.parquet`: `used_in_five_star` — 100% null (58,780 rows)
- Prior pulls (Hawaii v1): field was populated. Date of depopulation not confirmed.

**Classification:** EXTERNAL-UNDOCUMENTED — CMS appears to have removed the field's population
without documenting the change in any release notes or technical update we have found.

**Interim handling:** README discloses: "CMS stopped populating the field (confirmed in conformance
harness; documented in datasets_registry.json). The inputs shown here are identified from the
Five-Star Technical Users' Guide and CMS methodology documentation, not from the abandoned API flag."
Five-Star input identification currently uses manual reference to the Technical Users' Guide.

**Impact trace:**
- Cannot programmatically distinguish Five-Star-input QMs from non-input QMs
- Five-Star circularity caveat in README is substantiated but cannot be automated
- Any Phase 3 analysis that relies on this flag will produce incorrect filtering
- Finding: the Note in README § Five-Star Component Distribution is load-bearing disclosure

**Agency/agencies involved:** CMS (Care Compare / Five-Star program)

**Status:** OPEN — not confirmed whether this is permanent deprecation or a temporary data issue.
Monitor on next re-pull: if field is still null, escalate toward SUBMITTED.

**Resolution:** None yet. Candidates: (1) confirm via CMS Five-Star technical documentation whether
the flag is deprecated; (2) if deprecated without notice, this becomes a candidate for submission
to healthdata.gov or cdo@hhs.gov as an undocumented API change affecting downstream consumers.

---

### LMDL-004

**Date observed:** 2026-07-15 (first documented in audit)
**Date resolved:** N/A
**Title:** 199 Medicare-enrolled SNFs absent from Care Compare — no quality rating available

**What it was:** 199 facilities with Medicare enrollment (A-suffix CCNs — hospital-based swing
beds) are present in the CMS enrollment database but absent from Care Compare. Families searching
for quality data on these facilities find nothing — not a low rating, no rating.

**The error as it appeared (CORROBORATED):**
- SNF Enrollments: 14,425 CCNs
- NH Provider Info (Care Compare): 14,695 CCNs
- Union: facilities in enrollment not in Care Compare = 199 (A-suffix CCNs)
- These 199 have no Five-Star rating, no deficiency citation history in Care Compare, no VBP score

**Classification:** EXTERNAL-DOCUMENTED — CMS excludes hospital-based swing beds from Care
Compare ratings. This is a program design decision, documented in CMS's Care Compare methodology.

**Interim handling:** Disclosed in README universe section. No analytical figures derived from
these facilities (they have no Care Compare data). Noted as an accountability gap for consumers.

**Impact trace:**
- Public-facing quality transparency gap for hospital-based swing bed patients
- Not a data error in our pipeline; both enrollment and Care Compare data are correctly consumed
- Relevant when scope expands to cross-provider-type quality comparison

**Agency/agencies involved:** CMS (Care Compare / Five-Star)

**Status:** MONITORING — documenting the gap, not a fix candidate from our side.

**Resolution:** Not applicable (documented CMS program design).

---

### LMDL-005

**Date observed:** 2026-07-15 (first documented in audit)
**Date resolved:** N/A
**Title:** 469 Medicaid-only NFs in Care Compare but outside Medicare payment-accountability machinery

**What it was:** 469 Medicaid-only nursing facilities appear in Care Compare (and are in NH Provider
Info) but are not Medicare-certified and therefore outside VBP, SNF QRP, and Medicare cost report
accountability. They serve predominantly Medicaid populations with no equivalent federal incentive
or accountability structure.

**The error as it appeared (CORROBORATED):**
- NH Provider Info: 14,695 CCNs
- SNF Enrollments (Medicare-certified): 14,425 CCNs
- Difference attributable to Medicaid-only NFs: ~469 (the balance after A-suffix swing beds)

**Classification:** EXTERNAL-DOCUMENTED — Medicaid-only facilities are a defined CMS program
category. Their presence in Care Compare but absence from Medicare programs is by design.

**Interim handling:** Disclosed in README. Not used as a denominator for any Medicare-program
percentage claim. Included in accountability analysis as a structural equity gap.

**Impact trace:**
- Population served: disproportionately Medicaid (lower-income, higher-acuity long-term residents)
- No VBP penalty/bonus mechanism, no QRP reporting requirement
- Financial data not in HCRIS (cost report is Medicare-program only)
- Relevant to any equity analysis comparing accountability structures by payer mix

**Agency/agencies involved:** CMS (Care Compare / Medicaid program)

**Status:** MONITORING — structural gap, not a pipeline error.

**Resolution:** Not applicable (documented CMS program design).

---

### LMDL-006

**Date observed:** 2026-07-21 (Part A investigation)
**Date resolved:** N/A
**Title:** Five-Star table aggregation in README not tracked in any committed script

**What it was:** The Five-Star star-band table in README (avg citations, RN HPRD, nurse turnover
by star tier 1–5) is a published figure that cannot be reproduced from any committed pipeline
script. Script 10 produces state-level aggregates; no committed script groups facilities by star
band and computes within-band averages.

**The error as it appeared (INFERRED):**
- Five-Star table values (1★: 47.2 cit / 0.50 HPRD / 54.9%; 5★: 12.8 / 0.95 / 38.2%) appear
  in README with no corresponding script
- `nh_state_benchmarks_national.csv` has state + national aggregate rows, not star-band rows
- No script in `python/` produces a star-band groupby output

**Classification:** INTERNAL — a committed computation artifact (one-off analysis that was not
captured in a rerunnable script).

**Interim handling:** Table is published in README as Level 1; values are CORROBORATED (inputs
are CMS-direct fields, aggregation is arithmetic) but cannot be regenerated or updated without
re-running the lost one-off computation.

**Impact trace:**
- Table cannot be regenerated on next Care Compare refresh without reconstructing the computation
- If CMS updates facility Five-Star ratings (they do, quarterly), the table will drift from current
  data without detection
- The harness cannot check this output because there is no output file to check

**Agency/agencies involved:** INTERNAL

**Status:** OPEN — needs a committed script to close.

**Resolution candidate:** Add star-band aggregation to script 10 or a new script 11. The
computation is: `nh_provider_info_national.csv.groupby("overall_star")[["health_inspection_star",
"rn_hprd", "total_nurse_turnover"]].mean()`. One paragraph of code; closes the tracking gap.

---
