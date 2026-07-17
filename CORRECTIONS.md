# Corrections Log

Published figures that changed after the initial commit. Every entry states what was published,
what replaced it, why it changed, and the commit where the correction was made.

---

## Corrected

**2026-07-15 — Staffing non-compliance percentage wrong**
- Published: "75.5% of SNFs — 10,951 of 14,695"
- Corrected: "74.5% of SNFs — 10,951 of 14,695"
- Cause: arithmetic error; 10,951 / 14,695 = 74.5%, not 75.5%
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
- Status: script corrected and field names corrected; 87.6% counterfactual publishes after output CSV is regenerated.
- Commits: c43b9b9 (first), 7f30b75 (second — incomplete), b963512 (third — formula corrected), 7f25892 (fourth — HPRD basis closed), this commit (fifth — field rename; counterfactual reframe)

---

## Pending verification

**RN HPRD — raw vs case-mix adjusted (affects 22.9% finding)**
- Published: "22.9% of all SNFs nationally have RN HPRD below 0.4, the threshold CMS has proposed
  as a minimum"
- Issue: CMS's proposed minimum staffing thresholds are specified in *unadjusted* hours per
  resident day. The `rn_hprd` column in NH Provider Info is labeled "hours per resident day" but
  does not specify whether case-mix adjustment has been applied. The pipeline value (national mean
  0.680) is consistent with CMS's published unadjusted national average, suggesting raw HPRD —
  but this has not been verified against the Five-Star Technical Users' Guide.
- Risk: if `rn_hprd` is case-mix adjusted and the 0.4 threshold is unadjusted, the 22.9% figure
  compares two different measures. The direction of error would be that we understate the
  non-compliance rate (adjusted HPRD is typically lower than raw, making the threshold harder to
  meet).
- Action required: verify against Five-Star Technical Users' Guide before treating 22.9% as final

**rn_meets_3442f and total_meets_3442f columns — all null in current CSV; RESOLVED**
- The NH Provider Info output (prior to regeneration) contains `rn_meets_3442f`, `total_meets_3442f`,
  and `rn_weekend_meets_3442f` as entirely null. (Formerly named `rn_hprd_compliant` etc. — renamed
  this session; see staffing correction above.)
- Explanation confirmed: these fields did not exist in earlier script versions that produced the
  current CSV. They are computed fields added during the threshold correction; they will be
  non-null (True/False) after the output is regenerated.
- `meets_3442f_thresholds` (the composite) is populated in the current CSV with the old formula's
  values (10,951 False, 3,744 True) — those values are superseded by the corrected formula.
- Resolved as a null issue. Values will be correct after CSV regeneration.
