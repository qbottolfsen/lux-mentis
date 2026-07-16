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

**2026-07-15 — staffing_compliant threshold confirmed; OBRA hypothesis refuted by data**

- Original phrasing (commit a033120): "not staffing compliant by CMS standards"
- Corrected phrasing: "fall below the threshold in CMS's proposed minimum staffing rule"
- Challenge raised: `rn_hprd_compliant` and `total_hprd_compliant` are all null; the correction was written without knowing what threshold `staffing_compliant` actually uses. Hypothesis was that it measures the OBRA 1987 requirement (RN on duty 8 consecutive hours daily, licensed nurse 24/7 — a shift-presence test, not HPRD-based), not the proposed HPRD minimums.
- Resolution: Data contradicts the OBRA hypothesis. Cross-tabulation shows `staffing_compliant=True` requires `rn_hprd ≥ 0.55` (no True facility has rn_hprd < 0.55; minimum observed is 0.551). Adding `rn_weekend_hprd ≥ 0.55` as a second condition explains 14,681 of 14,695 facilities (99.9%). OBRA does not define HPRD thresholds; this field clearly encodes one. The corrected phrasing is directionally right.
- Remaining gap: the exact threshold (0.55) and its weekend dimension are derived from data, not confirmed against CMS documentation. README updated to state the threshold explicitly; see also pending item below.
- Commit: this entry (README updated same commit)

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

**rn_hprd_compliant and total_hprd_compliant columns — all null; staffing_compliant threshold partially resolved**
- The NH Provider Info output contains `rn_hprd_compliant`, `total_hprd_compliant`, and
  `rn_weekend_compliant` (columns 30–32). All three are entirely null in the June 2026 pull.
- `staffing_compliant` (column 33) is populated: 10,951 False, 3,744 True. Data analysis
  confirms it encodes `(rn_hprd ≥ 0.55) AND (rn_weekend_hprd ≥ 0.55)` — 99.9% match rate.
- The null individual-component columns (rn_hprd_compliant, total_hprd_compliant) are likely
  scaffolding for the full proposed rule that was never populated after the rule was vacated.
  The composite `staffing_compliant` flag continued to be updated; the component flags did not.
- Remaining action: confirm the 0.55 threshold and weekend requirement against the Five-Star
  Technical Users' Guide. The data derivation is strong (99.9%) but not documentation-anchored.
