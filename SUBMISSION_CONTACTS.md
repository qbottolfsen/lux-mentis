# Submission Contacts — Federal Agency Reporting Channels

Maintained registry of reporting channels for data quality issues, schema divergences, and
anomalies identified in the Lux Mentis pipeline. Per-channel: what it accepts, the format
it expects, and whether auto-population from DIVERGENCE_LOG.md entries is feasible.

**Last verified:** 2026-07-21
**Auto-population status:** DORMANT — structure present; wiring activates on first confirmed
EXTERNAL-UNDOCUMENTED divergence entry. Do not submit without human review gate.

---

## CMS Provider Data (Care Compare, Five-Star, VBP, Cost Reports)

### CMS Feedback Form — Provider Data
- **Channel:** Web form
- **Last verified:** 2026-07-21  **Verify before use:** Yes — CMS has restructured QualityNet login paths
- **URL:** https://www.cms.gov/Medicare/Quality-Initiatives-Patient-Assessment-Instruments/NursingHomeQualityInits/Downloads/NH-Data-Submission-Form.pdf (paper form); online variant at https://qualitynet.cms.gov (requires QualityNet account for providers; public feedback path unclear)
- **What it accepts:** Data quality issues with CMS quality measure data, Care Compare display errors
- **Format:** Structured fields — Facility CCN, measure name, reported value, expected value, date observed
- **Auto-populate feasibility:** HIGH — DIVERGENCE_LOG fields map directly to CCN, expected-vs-actual, date observed
- **Limitations:** Primarily designed for provider-reported corrections, not third-party pipeline findings. Public-interest submissions may not have a clear acceptance path through this form.
- **Alternative:** CMS Data Contact (below)

### CMS Data Contact — healthdata.gov / Open Data
- **Channel:** Email
- **Last verified:** 2026-07-21  **Verify before use:** Yes — confirm data@cms.hhs.gov still routes to data quality team
- **URL:** https://healthdata.gov/contact
- **Email:** data@cms.hhs.gov (general); cdo@hhs.gov (HHS Chief Data Officer — explicitly solicits data quality findings from data consumers per HHS Open Data Policy)
- **What it accepts:** Schema changes without documentation, field depopulation without notice (cf. used_in_five_star), irreconcilable dataset counts across delivery channels
- **Format:** No structured form found as of 2026-07-21. Free-form email. CMS does publish a Data Issues Tracker at: https://data.cms.gov/provider-data/archived-data (limited scope)
- **Auto-populate feasibility:** MEDIUM — dossier template (see SUBMISSION_TEMPLATE.md) produces a structured email body; no form fields to auto-populate
- **Best for:** LMDL-003 type (field depopulated without announcement), LMDL-001 type if confirmed external

### CMS SNF VBP Technical Assistance
- **Channel:** Email + web
- **Last verified:** 2026-07-21 (URL); email confirmed in CMS VBP FAQ as of 2024 — **verify before use**
- **URL:** https://www.cms.gov/Medicare/Quality-Initiatives-Patient-Assessment-Instruments/Value-Based-Programs/SNF-VBP/SNF-VBP-Educational-Technical-Assistance
- **Email:** SNFVBPtechnicalassistance@cms.hhs.gov (from CMS VBP FAQ, last confirmed 2024; verify before use)
- **What it accepts:** Questions about VBP scoring, participant universe, case minimum thresholds
- **Format:** Email; structured question recommended
- **Auto-populate feasibility:** LOW — question-style, not a finding submission
- **Note:** Use for Branch 3 documentation queries (confirming whether API vs file universe difference is documented). Query first; submit finding only if query confirms undocumented.

---

## OIG (LEIE, exclusions)

### OIG Fraud, Waste and Abuse Hotline
- **Channel:** Web form + phone
- **Last verified:** 2026-07-21  **Verify before use:** Yes — OIG redesigns report-fraud pages periodically
- **URL:** https://oig.hhs.gov/fraud/report-fraud/
- **What it accepts:** Active fraud, excluded individuals practicing — NOT data quality issues
- **Format:** Structured form (name, address, incident description)
- **Auto-populate feasibility:** N/A — not relevant for data quality divergences
- **Note:** Not the right channel for LEIE data schema issues. For LEIE file format questions: exclusions@oig.hhs.gov (from LEIE download page)

### OIG Data Quality — LEIE file issues
- **Channel:** Email
- **Last verified:** 2026-07-21  **Verify before use:** Yes — confirm exclusions@oig.hhs.gov still routes to LEIE team
- **Email:** exclusions@oig.hhs.gov
- **What it accepts:** Questions about LEIE file format, field definitions, apparent data errors
- **Format:** Free-form email
- **Auto-populate feasibility:** MEDIUM — dossier template applicable

---

## HHS / Cross-Agency

### HHS Chief Data Officer (CDO)
- **Channel:** Email
- **Last verified:** 2026-07-21  **Verify before use:** Yes — HHS leadership changes can affect CDO routing
- **Email:** cdo@hhs.gov
- **URL:** https://www.hhs.gov/about/agencies/asa/ocio/data-governance/index.html
- **What it accepts:** Per HHS Open Data Policy: data quality issues, schema documentation gaps, field definition discrepancies. Explicitly intended for data consumers reporting pipeline issues.
- **Format:** No structured form. Free-form email with structured content preferred.
- **Auto-populate feasibility:** HIGH — dossier template maps directly; this is the best general channel for EXTERNAL-UNDOCUMENTED findings
- **Best for:** LMDL-003 (used_in_five_star deprecation without notice), any field depopulation without documentation

### healthdata.gov Issue Tracker
- **Channel:** GitHub Issues (public)
- **Last verified:** 2026-07-21  **Verify before use:** Yes — HHS GitHub org structure shifts; confirm repo path
- **URL:** https://github.com/HHS/healthdata.gov (repo may vary; check current HHS GitHub org)
- **What it accepts:** Dataset-specific issues, documentation gaps, API schema discrepancies
- **Format:** GitHub issue — title, description, steps to reproduce
- **Auto-populate feasibility:** HIGH — dossier template fields map to GitHub issue body; reproducible-case field maps to steps-to-reproduce
- **Note:** Public record. Any submission here is visible. Ensure human review gate passes before filing.

---

## Research note (B3a task — completed 2026-07-21)

**Structured web form vs. email inbox findings:**

| Agency/Channel | Has structured form? | Auto-populate viable? |
|---------------|---------------------|----------------------|
| CMS QualityNet (provider) | YES (provider portal, account required) | NO (not our channel) |
| CMS data@cms.hhs.gov | NO (email only) | YES via dossier template |
| HHS cdo@hhs.gov | NO (email only) | YES via dossier template |
| healthdata.gov GitHub | YES (GitHub Issues) | YES — highest fidelity |
| OIG exclusions@oig.hhs.gov | NO (email only) | YES via dossier template |
| SNF VBP TA email | NO (email only) | NO (query, not finding) |

**Conclusion:** No federal agency relevant to this pipeline currently offers a structured API or
web form for third-party data quality submissions. All channels accept email or GitHub issues.
The dossier template (SUBMISSION_TEMPLATE.md) is the deliverable for all channels. GitHub Issues
(healthdata.gov or CMS provider-data GitHub) is the highest-fidelity channel because the
submission becomes a public record and can include reproducibility artifacts.

**Build recommendation when auto-populate activates:** target GitHub Issues API first
(POST /repos/{owner}/{repo}/issues — documented at docs.github.com/rest). Fields from
DIVERGENCE_LOG entry → issue title, body template → body. One function, no complex mapping.
Email channels are a fallback when GitHub is not appropriate (e.g., if the issue involves
individual-level data that should not be public).

---
