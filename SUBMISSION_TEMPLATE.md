# Submission Dossier Template

Per-issue template for reporting confirmed EXTERNAL-UNDOCUMENTED divergences to a federal agency
or public issue tracker. Draws from a DIVERGENCE_LOG.md entry.

**Human review gate — non-negotiable before any submission:**
1. Confirm expected-vs-actual values from the current output (not from memory)
2. Re-examine our own code end-to-end for any overlooked artifact or misread — our code is
   guilty until proven innocent, including at the point of submission, not just at discovery
3. Confirm reproducibility: can you produce the discrepancy on demand from both sources right now?
4. Name who reviewed and signed off

A submission that skips any of these steps is not a submission — it is a complaint. Do not send.

---

## Dossier Fields (fill all; mark N/A if not applicable)

**DIVERGENCE_LOG reference:** LMDL-[ID]
**Submission date:** YYYY-MM-DD
**Reviewer (human sign-off):** [Name]
**Submitted to:** [Channel from SUBMISSION_CONTACTS.md]
**Submission URL / tracking reference:** [GitHub issue URL, email thread ID, etc.]

---

### 1. What we observed

*State the divergence factually. No interpretation yet.*

> [Description of the observed discrepancy — row counts, field values, schema change. Quote
> actual numbers. Reference the dataset, the access method, and the date of pull.]

**Expected:** [What we expected based on documentation or prior behavior]
**Actual:** [What we observed]
**Date of pull:** [YYYY-MM-DD or date range]
**Access method:** [DKAN API / direct CSV download / data-api v1 / etc.]

---

### 2. Reproducibility

*A finding that does not reproduce is not a finding.*

We can reproduce this discrepancy on demand:
- **Source A** (expected): [URL/endpoint + query parameters that return the expected result]
- **Source B** (actual): [URL/endpoint or file path that returns the diverging result]
- **Reproduction steps:**
  1. [Step 1]
  2. [Step 2]
  3. [Step 3]

---

### 3. Our code review (the our-code-guilty-until-proven-innocent check)

*State what we ruled out on our end before filing.*

We examined the following potential sources of artifact in our pipeline:
- [ ] Pagination/truncation: [how we verified completeness]
- [ ] Deduplication: [how we verified no double-counting]
- [ ] Filtering: [what filters are applied and whether they could explain the discrepancy]
- [ ] Caching: [whether cached data could explain a vintage mismatch]
- [ ] Field binding: [whether a column name mismatch could explain the value difference]

**Conclusion:** [We ruled out the above because ...]

---

### 4. Documentation search

*Document-before-novel. What we searched and what we found.*

We searched the following documentation for an explanation of this behavior:
- [ ] [Document name and URL]
- [ ] [Document name and URL]

**Finding:** [The documentation does / does not account for this behavior. Quote the relevant passage if it does.]

---

### 5. Impact

*What this affects in our pipeline and for other consumers.*

- **Datasets affected in our pipeline:** [list]
- **Published figures affected (if any):** [list with current values]
- **Estimated downstream consumer impact:** [e.g., "any consumer using the DKAN API pagination pattern for this dataset will receive incomplete results"]

---

### 6. Question / request

*Frame as a question, not a gotcha. We may be missing something.*

> [We observed X. Our documentation search found Y. Is this expected behavior? If so, where is
> it documented? If not, here is a minimal reproducible case: ...]

---

### 7. Attachments

- [ ] Divergence log entry (LMDL-[ID] from DIVERGENCE_LOG.md)
- [ ] Code snippet demonstrating the issue
- [ ] Sample data (if not privacy-sensitive)
- [ ] Prior snapshot showing pre-divergence state (from health_snapshot.json, if applicable)

---
