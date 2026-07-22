# Corrections Log

Published figures that changed after the initial commit. Every entry states what was published,
what replaced it, why it changed, and the commit where the correction was made.

---

## Corrected

**2026-07-15 — Staffing non-compliance percentage wrong**
- Published: "75.5% of SNFs — 10,951 of 14,695"
- Corrected: "74.5% of SNFs — 10,951 of 14,695"
- Cause: transcription error — 74.5% written as 75.5% in initial README; 10,951 / 14,695 = 0.7451
- Commit: f05a5c6

**2026-07-15 — VBP penalty rate overstated denominator**
- Published: "78.6% of SNFs nationally receive a VBP incentive payment penalty"
- Corrected: "78.6% of VBP-scored facilities (10,146 of 12,901)"; added that 12,901 is 89.4%
  of the enrollment spine, and 70.3% of all SNFs nationally are receiving a VBP penalty
- Cause: 78.6% is of scored facilities only; ~10.6% of SNFs are below the case minimum threshold
  and not scored
- Commit: f05a5c6

**2026-07-15 — Five-Star gradient table mislabeled Level 2 (association)**
- Published: table labeled *(Level 2 — association)* with framing "these move together"
- Corrected: relabeled Level 1; reframed as distribution of constituent measures across the
  composite they build, not an independently discovered relationship
- Cause: citations and HPRD/turnover are inputs to the Five-Star composite; a composite
  correlating with its own inputs is arithmetic, not association
- Commit: 74c7de6

**2026-07-15 — staffing_compliant threshold: three successive corrections**

- Original phrasing (commit a033120): "not staffing compliant by CMS standards"
- First correction (commit c43b9b9): two-condition model (rn_hprd ≥ 0.55 AND rn_weekend_hprd ≥ 0.55); flagged as derived from data
- Second correction (commit 7f30b75): two-condition model was incomplete — added a third condition (total nurse HPRD ≥ 2.45) that resolved the ~14 residuals. Zero exceptions across all 14,695 facilities. *This second correction was itself wrong — see third correction below.*
- **Third correction (commit b963512 — BLOCKING):** The "Total Nurse HPRD ≥ 2.45" described in the second correction misidentifies both the field and the value. Per CMS-3442-F: 2.45 is the *nurse aide (CNA)* minimum and is applied to `cna_hprd`; the *total nurse* minimum is 3.48, applied to `total_hprd`. The script set `TOTAL_HPRD_MIN = 2.45` and applied it to `total_hprd` (RN+LPN+CNA) — the aide threshold on the wrong field — and never tested `cna_hprd` at all. The formula fit the data perfectly because it was circular: the script computed the flag with its own constants, then cross-validated the flag against those same constants. Under the rule's actual four-part formula (rn ≥ 0.55, weekend_rn ≥ 0.55, aide ≥ 2.45, total ≥ 3.48): **87.6% (12,868 of 14,695) would not have met the final-state thresholds.** 1,917 facilities that cleared the prior formula's wrong test would fail the corrected one.
- **Documentation check closed the open questions:** (1) HPRD basis: CMS-3442-F rule text says thresholds are "implemented and enforced independent of a facility's case-mix." Script SRC dict comment: "reported = direct PBJ count, not case-mix adjusted." `reported_*` fields are confirmed unadjusted; basis is correct. (2) The "gap" premise was wrong: `meets_3442f_thresholds` is not a CMS-published API field — it is entirely computed by this pipeline. Reading the SRC dict confirms no compliance flag is read from the API. CMS does not publish a staffing compliance determination in the NH Provider Info API; the field did briefly appear on the Care Compare website during Phase 1 enforcement (2024–2025), but never as an API value, and it is no longer displayed post-repeal. "74.5% is a floor relative to CMS's published flag" was a false framing; there is no CMS flag to compare against. The gap between 74.5% and 87.6% is old formula vs. corrected formula. (3) Rule status: Public Law 119-21 (Jul 2025) prohibited enforcement; CMS Federal Register Dec 2025 formally repealed the rule. Our June 2026 data is post-repeal. The 87.6% is a counterfactual — it describes the staffing landscape against thresholds that were repealed before they fully took effect.
- **Field rename (this commit):** `staffing_compliant` renamed to `meets_3442f_thresholds`; component flags renamed from `*_compliant` to `*_meets_3442f` pattern. The old names asserted regulatory non-compliance with a repealed rule. The new names describe the computation.
- **Subsequent rename (2026-07-21):** All five computed fields received `lm_` prefix (`lm_meets_3442f_thresholds`, `lm_rn_meets_3442f`, etc.) to distinguish pipeline-computed fields from CMS API source fields. `chain_affiliated` also renamed to `lm_chain_affiliated`.
- Status: script corrected and field names corrected; 87.6% counterfactual publishes after output CSV is regenerated.
- Commits: c43b9b9 (first), 7f30b75 (second — incomplete), b963512 (third — formula corrected), 7f25892 (fourth — HPRD basis closed), this commit (fifth — field rename; counterfactual reframe)

**2026-07-17 — 22.9% RN HPRD finding removed: unsourced figure, unsourced threshold**
- Published: "22.9% of all SNFs nationally have RN HPRD below 0.4, the threshold CMS has proposed
  as a minimum" (original); later reframed as "a more lenient floor than the 0.55 in the
  compliance definition" when the 87.6% counterfactual was added
- Removed: the figure was never computed by any pipeline script. Script 01 has used
  `RN_HPRD_MIN = 0.55` since its first commit (5161467). No 0.4 threshold appears anywhere
  in the codebase. The figure was hand-inserted in the original README with no source.
- Threshold provenance: CMS-3442-F finalized 0.55 RN HPRD. The October 2022 NPRM also
  proposed 0.55. No CMS document proposes or finalizes 0.4 as an RN HPRD minimum — confirmed
  by web search against CMS sources. The original attribution ("threshold CMS has proposed")
  was false. The reframing ("more lenient floor") was worse — a sourceless number with no
  explanation.
- Status: both the figure (22.9%) and the threshold (0.4) are ASSUMED — no pipeline provenance,
  no regulatory citation. Figure removed from README. Basis verification (column is unadjusted
  PBJ HPRD) is still correct and documented below; it verifies the column binding for the 87.6%
  finding, not a separate 22.9% finding that no longer exists.
- Note: `rn_hprd` binding remains CORROBORATED (SRC dict line 88, script comment, CMS rule text
  — three concordant sources). This covers the 87.6% counterfactual, not the removed 22.9%.

---

## Pending verification

**RN HPRD — raw vs case-mix adjusted (affects 87.6% counterfactual) — RESOLVED**
- Question: does `rn_hprd` bind to the unadjusted (PBJ-direct) column or a case-mix-adjusted
  variant?
- Resolved: Script 01 SRC dict maps `rn_hprd` to the explicit CMS column name
  `reported_rn_staffing_hours_per_resident_per_day` (line 88). The script comment states
  "reported = direct PBJ count, not case-mix adjusted." The CMS-3442-F rule text confirms
  thresholds apply "independent of a facility's case-mix." Three concordant sources (explicit
  column binding, script comment, rule text) establish that `rn_hprd` is unadjusted PBJ HPRD.
- Note: script 01 uses an explicit SRC dict, not find_col(). The A4 fix to find_col() does not
  affect this binding.

**SCOPE_SEVERITY grid (02_nh_deficiencies_national.py lines 77-90) — VERIFIED**
- Question: does the A-L parsing dict match the authoritative CMS source?
- Verified: read against SOM Appendix P (CMS Pub. 100-07 State Operations, Transmittal 156,
  June 10, 2016, "IV. Deficiency Categorization" and the Scope and Severity Grid reproduced
  in Virginia DHS P-02055). The dict matches the grid exactly:
  - Level 1 (No Actual Harm, Minimal): A=Isolated, B=Pattern, C=Widespread
  - Level 2 (No Actual Harm, >Minimal): D=Isolated, E=Pattern, F=Widespread
  - Level 3 (Actual Harm): G=Isolated, H=Pattern, I=Widespread
  - Level 4 (Immediate Jeopardy): J=Isolated, K=Pattern, L=Widespread
- G+ (severity_level >= 3) correctly captures G, H, I, J, K, L — the full set of Actual Harm
  and Immediate Jeopardy citations. The 19.0% G+ abuse/neglect finding is CORROBORATED:
  parse table VERIFIED + count is a Level 1 pipeline computation from verified data.

**Category-based deficiency flags (02_nh_deficiencies_national.py) — VERIFIED against D22**
- Question: do `is_abuse_neglect`, `is_infection_ctrl_cat`, `is_resident_rights`, and `is_quality_care`
  correctly identify the right F-tags, or does the substring match produce false positives/negatives?
- Verified: read all 28 distinct category values from reference_ftag_citations.csv (D22).
  Each substring match resolves to exactly one category — no overlap, no false positives:
  - `is_abuse_neglect` (`"abuse"` or `"neglect"` in category): captures only
    "Freedom from Abuse, Neglect, and Exploitation Deficiencies" — 17 F-tags (F-0221 to F-0943)
  - `is_infection_ctrl_cat` (`"infection control"` in category): captures only
    "Infection Control Deficiencies" — 10 F-tags (F-0880 to F-0945)
  - `is_resident_rights` (`"resident rights"` in category): captures only
    "Resident Rights Deficiencies" — 88 F-tags
  - `is_quality_care` (`"quality of life"` in category): captures only
    "Quality of Life and Care Deficiencies" — 57 F-tags
- Perfect concordance across all 28 categories. Zero false positives, zero false negatives.
- Note: `is_infection_control` (separate field, line 299) reads directly from the CMS API
  field `is_ic` (infection control inspection flag) — not a substring match; not covered here.
- Status: all four category-based flags elevated from INFERRED to VERIFIED.

**lm_rn_meets_3442f and lm_total_meets_3442f columns — all null in current CSV; RESOLVED**
- The NH Provider Info output (prior to regeneration) contains `lm_rn_meets_3442f`, `lm_total_meets_3442f`,
  and `lm_rn_weekend_meets_3442f` as entirely null. (Formerly `rn_hprd_compliant` → `rn_meets_3442f`
  → `lm_rn_meets_3442f` — lm_ prefix applied 2026-07-21 to mark pipeline-computed fields.)
- Explanation confirmed: these fields did not exist in earlier script versions that produced the
  current CSV. They will be non-null (True/False) after the output is regenerated.
- `lm_meets_3442f_thresholds` (the composite) is populated in the current CSV with the old formula's
  values (10,951 False, 3,744 True) — those values are superseded by the corrected formula.
- Resolved as a null issue. Values will be correct after CSV regeneration.
