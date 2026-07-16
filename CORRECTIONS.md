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
- **Third correction (this entry — BLOCKING; output CSV must be regenerated):** The "Total Nurse HPRD ≥ 2.45" described in the second correction misidentifies both the field and the value. Per CMS-3442-F: 2.45 is the *nurse aide (CNA)* minimum and is applied to `cna_hprd`; the *total nurse* minimum is 3.48, applied to `total_hprd`. The script set `TOTAL_HPRD_MIN = 2.45` and applied it to `total_hprd` (RN+LPN+CNA) — the aide threshold on the wrong field — and never tested `cna_hprd` at all. The formula fit the data perfectly because it was circular: the script computed the flag with its own constants, then cross-validated the flag against those same constants. Under the rule's actual four-part formula (rn ≥ 0.55, weekend_rn ≥ 0.55, aide ≥ 2.45, total ≥ 3.48): **12,868 of 14,695 facilities fail — 87.6%.** 1,917 facilities that currently pass `staffing_compliant` would fail the rule. The published 74.5% is a floor.
- Source: threshold_verify.py cross-tabulation; CMS-3442-F Final Rule text
- Status: script corrected; output CSV must be regenerated; README carries PENDING flag until 74.5% is replaced with 87.6%
- Commits: c43b9b9 (first correction), 7f30b75 (second — incomplete), this commit (third)

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

**rn_hprd_compliant and total_hprd_compliant columns — all null; RESOLVED**
- The NH Provider Info output contains `rn_hprd_compliant`, `total_hprd_compliant`, and
  `rn_weekend_compliant` (columns 30–32). All three are entirely null in the June 2026 pull.
- Explanation confirmed: CMS-3442-F was vacated in 2025. CMS stopped populating the individual
  component compliance flags after the vacatur but has continued updating the composite
  `staffing_compliant` field. The null fields are regulatory history frozen at the point of
  vacatur; they are not data errors.
- `staffing_compliant` (column 33) is populated: 10,951 False, 3,744 True. Three-condition
  definition confirmed from CMS-3442-F and cross-validated against all 14,695 rows.
- Resolved. No further action required on null columns.
