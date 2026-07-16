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

**rn_hprd_compliant and total_hprd_compliant columns — all null**
- The NH Provider Info output contains columns `rn_hprd_compliant` and `total_hprd_compliant`
  (columns 30–31 in the 50-column schema). Both are entirely null in the June 2026 pull.
- `staffing_compliant` (column 33) is populated: 10,951 False, 3,744 True. It is unclear whether
  this flag uses the proposed 0.4 RN HPRD threshold, a different threshold, or a composite.
- Action required: verify against Five-Star Technical Users' Guide what threshold
  `staffing_compliant` uses and why the individual HPRD compliant columns are null
