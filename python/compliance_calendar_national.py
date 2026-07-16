"""
compliance_calendar_national.py
Compliance deadline tracker -- national LTPAC provider universe.

For each facility in the master, computes or flags three compliance items:

  STATE LICENSE    All types -- from input/manual_license_dates.csv
                   No national API exists; add rows as dates become known.

  PBJ QUARTERLY    SNF only -- Payroll-Based Journal quarterly submission
                   Deadlines fixed by CMS calendar: Q1=May 15, Q2=Aug 14,
                   Q3=Nov 14, Q4=Feb 14. Source: 42 CFR §483.75(l)(2).

  COST REPORT      SNF only (where POS fy_end_mo_day_cd is available)
                   Due last day of 5th calendar month after fiscal year end.
                   Source: 42 CFR §413.20(b); CMS Form CMS-2540-10.

Each item carries:
  _term_date       Actual expiry / deadline date
  _action_date     Suggested date to begin compliance action (before term)
  _source          Authoritative source citation
  _reg_ref         Regulatory reference (CFR citation, statute, etc.)
  _alert           OVERDUE / CRITICAL / WARNING / UPCOMING / OK / MANUAL_CHECK / N_A

Alert thresholds (configurable below):
  OVERDUE:      term_date has passed
  CRITICAL:     term_date within CRITICAL_DAYS (30 days)
  WARNING:      action_date has passed but not yet CRITICAL
  UPCOMING:     action_date within UPCOMING_DAYS (90 days)
  OK:           action_date > 90 days away

Outputs:
  output_reference/compliance_calendar_national.csv  -- one row per facility
  output_reference/compliance_hotlist_national.csv   -- OVERDUE + CRITICAL + WARNING only

To add new state license dates: edit input/manual_license_dates.csv.
Required columns: ccn, license_type, term_date (YYYY-MM-DD), source, regulatory_ref.
"""

import calendar, csv, datetime, pathlib, sys

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required: pip install pandas")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
INPUT_DIR  = SCRIPT_DIR / "input"

MASTER_FILE       = OUTPUT_DIR / "facility_master_national.csv"
POS_FILE          = OUTPUT_DIR / "pos_iqies_national.csv"
MANUAL_LIC_FILE   = INPUT_DIR  / "manual_license_dates.csv"
CALENDAR_OUTPUT   = OUTPUT_DIR / "compliance_calendar_national.csv"
HOTLIST_OUTPUT    = OUTPUT_DIR / "compliance_hotlist_national.csv"

TODAY = datetime.date.today()

# Alert thresholds
CRITICAL_DAYS  = 30   # term date within this many days = CRITICAL
UPCOMING_DAYS  = 90   # action date within this many days = UPCOMING

# Action lead times (days before term/deadline to begin preparation)
STATE_LIC_ACTION_LEAD   = 90   # begin license renewal 90 days before expiry
PBJ_ACTION_LEAD         = 30   # submit PBJ 30 days before deadline
COST_REPORT_ACTION_LEAD = 30   # submit cost report 30 days before due date

# PBJ fixed deadlines (CMS PBJ rule -- calendar year, updated annually)
# Reference: 42 CFR §483.75(l)(2); CMS PBJ Submission Requirements
PBJ_SOURCE  = "CMS Payroll-Based Journal (PBJ) Submission Requirements"
PBJ_REG_REF = "42 CFR §483.75(l)(2)"

COST_SOURCE  = "CMS Medicare Cost Report (CMS-2540-10)"
COST_REG_REF = "42 CFR §413.20(b)"

ALERT_PRIORITY = {
    "OVERDUE":       6,
    "CRITICAL":      5,
    "WARNING":       4,
    "UPCOMING":      3,
    "OK":            2,
    "MANUAL_CHECK":  1,
    "N_A":           0,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def compute_alert(term_date, action_date):
    """Return alert level string given term and action dates vs TODAY."""
    if term_date is None:
        return "MANUAL_CHECK"
    delta_term   = (term_date - TODAY).days
    delta_action = (action_date - TODAY).days
    if delta_term < 0:
        return "OVERDUE"
    if delta_term <= CRITICAL_DAYS:
        return "CRITICAL"
    if delta_action <= 0:
        return "WARNING"
    if delta_action <= UPCOMING_DAYS:
        return "UPCOMING"
    return "OK"


def max_alert(*alerts):
    """Return the highest-priority alert from a list."""
    return max(alerts, key=lambda a: ALERT_PRIORITY.get(a, -1))


def last_day_of_month(year, month):
    return calendar.monthrange(year, month)[1]


def add_months(d, n):
    """Add n months to date d, clamped to last day of the result month."""
    total = d.month + n
    y = d.year + (total - 1) // 12
    m = (total - 1) % 12 + 1
    return datetime.date(y, m, min(d.day, last_day_of_month(y, m)))


def next_pbj_deadline():
    """Return (deadline, quarter_label, action_date) for the next upcoming PBJ deadline."""
    y = TODAY.year
    # Fixed CMS calendar deadlines: Q1=May 15, Q2=Aug 14, Q3=Nov 14, Q4=Feb 14 next year
    candidates = [
        (datetime.date(y, 5, 15),     f"Q1 {y} (Jan-Mar {y})"),
        (datetime.date(y, 8, 14),     f"Q2 {y} (Apr-Jun {y})"),
        (datetime.date(y, 11, 14),    f"Q3 {y} (Jul-Sep {y})"),
        (datetime.date(y + 1, 2, 14), f"Q4 {y} (Oct-Dec {y})"),
    ]
    for dl, label in candidates:
        if dl >= TODAY:
            action = dl - datetime.timedelta(days=PBJ_ACTION_LEAD)
            return dl, label, action
    # All deadlines passed (shouldn't happen mid-year)
    dl = datetime.date(y + 1, 5, 15)
    return dl, f"Q1 {y+1} (Jan-Mar {y+1})", dl - datetime.timedelta(days=PBJ_ACTION_LEAD)


def parse_fy_end(fy_str):
    """
    Parse 'MM-DD' or 'M-D' from POS fy_end_mo_day_cd.
    Returns (most_recent_fy_end, next_fy_end) or (None, None) if unparseable.
    """
    if not fy_str or fy_str.strip() in ("", "Not Available", "Not Applicable"):
        return None, None
    parts = fy_str.strip().split("-")
    if len(parts) != 2:
        return None, None
    try:
        month, day = int(parts[0]), int(parts[1])
    except ValueError:
        return None, None
    # Clamp day to valid range for the month
    day = min(day, last_day_of_month(TODAY.year, month))
    this_year_end = datetime.date(TODAY.year, month, day)
    if this_year_end <= TODAY:
        most_recent = this_year_end
        next_end = datetime.date(TODAY.year + 1, month,
                                 min(day, last_day_of_month(TODAY.year + 1, month)))
    else:
        most_recent = datetime.date(TODAY.year - 1, month,
                                    min(day, last_day_of_month(TODAY.year - 1, month)))
        next_end = this_year_end
    return most_recent, next_end


def cost_report_due_date(fy_end):
    """Last day of the 5th calendar month after the FYE (42 CFR §413.20(b))."""
    m5 = add_months(fy_end, 5)
    return datetime.date(m5.year, m5.month, last_day_of_month(m5.year, m5.month))


# ── Load data ─────────────────────────────────────────────────────────────────

print(f"Compliance Calendar -- National LTPAC Providers")
print(f"Run: {TODAY}")
print()

print("Loading facility master ...")
master = pd.read_csv(MASTER_FILE, dtype=str).fillna("")
print(f"  {len(master):,} facilities")

print("Loading POS iQIES (fy_end_mo_day_cd) ...")
pos_fy = {}
with open(POS_FILE, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        ccn = row.get("prvdr_num", "").strip().zfill(6)
        fy  = row.get("fy_end_mo_day_cd", "").strip()
        if ccn and fy:
            pos_fy[ccn] = fy

print("Loading manual license dates ...")
manual_lic = {}   # ccn → {term_date, source, reg_ref, notes, license_type}
if MANUAL_LIC_FILE.exists():
    with open(MANUAL_LIC_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ccn = row.get("ccn", "").strip().zfill(6)
            raw_date = row.get("term_date", "").strip()
            try:
                td = datetime.date.fromisoformat(raw_date)
            except ValueError:
                continue
            manual_lic[ccn] = {
                "term_date":    td,
                "license_type": row.get("license_type", "State License"),
                "source":       row.get("source", "Manual input"),
                "reg_ref":      row.get("regulatory_ref", ""),
                "notes":        row.get("notes", ""),
            }
    print(f"  {len(manual_lic)} facilities with manual license dates")
else:
    print(f"  WARNING: {MANUAL_LIC_FILE} not found — no state license dates loaded")

# Pre-compute the shared PBJ deadline (same for all SNFs)
pbj_deadline, pbj_quarter, pbj_action = next_pbj_deadline()
print()
print(f"PBJ next deadline: {pbj_deadline}  ({pbj_quarter})")
print(f"  Action date:     {pbj_action}  ({PBJ_ACTION_LEAD} days before deadline)")
print()

# ── Build compliance rows ──────────────────────────────────────────────────────

print("Computing compliance items ...")

rows = []
for _, fac in master.iterrows():
    ccn   = str(fac.get("ccn", "")).strip().zfill(6)
    ptype = fac.get("provider_type_label", "")
    is_snf = (ptype == "SNF")

    base = {
        "ccn":                 fac.get("ccn", ""),
        "npi":                 fac.get("npi", ""),
        "npi_uri":             fac.get("npi_uri", ""),
        "org_name":            fac.get("org_name", ""),
        "provider_type":       ptype,
        "address_state":       fac.get("address_state", ""),
        "zip":                 fac.get("zip", ""),
    }

    # ── State license ─────────────────────────────────────────────────────────
    ml = manual_lic.get(ccn)
    if ml:
        sl_term   = ml["term_date"]
        sl_action = sl_term - datetime.timedelta(days=STATE_LIC_ACTION_LEAD)
        sl_alert  = compute_alert(sl_term, sl_action)
        sl_source = ml["source"]
        sl_regref = ml["reg_ref"]
        sl_type   = ml["license_type"]
        sl_notes  = ml["notes"]
    else:
        sl_term   = None
        sl_action = None
        sl_alert  = "MANUAL_CHECK"
        sl_source = "Not on file — add to input/manual_license_dates.csv"
        sl_regref = ""
        sl_type   = ""
        sl_notes  = ""

    # ── PBJ quarterly submission (SNF only) ────────────────────────────────────
    if is_snf:
        pbj_term    = pbj_deadline
        pbj_act     = pbj_action
        pbj_alert_v = compute_alert(pbj_term, pbj_act)
        pbj_src     = PBJ_SOURCE
        pbj_ref     = PBJ_REG_REF
        pbj_quarter_label = pbj_quarter
    else:
        pbj_term    = None
        pbj_act     = None
        pbj_alert_v = "N_A"
        pbj_src     = ""
        pbj_ref     = ""
        pbj_quarter_label = ""

    # ── Cost report (SNF where FYE is available) ───────────────────────────────
    fy_str = pos_fy.get(ccn, "")
    if is_snf and fy_str:
        most_recent_fy, next_fy = parse_fy_end(fy_str)
        if next_fy:
            cr_term     = cost_report_due_date(next_fy)
            cr_act      = cr_term - datetime.timedelta(days=COST_REPORT_ACTION_LEAD)
            cr_alert_v  = compute_alert(cr_term, cr_act)
            cr_fy_end   = str(next_fy)
            cr_src      = COST_SOURCE
            cr_ref      = COST_REG_REF
        else:
            cr_term    = None; cr_act    = None; cr_alert_v = "MANUAL_CHECK"
            cr_fy_end  = ""; cr_src = COST_SOURCE; cr_ref = COST_REG_REF
    elif is_snf:
        cr_term    = None; cr_act    = None; cr_alert_v = "MANUAL_CHECK"
        cr_fy_end  = ""; cr_src = COST_SOURCE; cr_ref = COST_REG_REF
    else:
        cr_term    = None; cr_act    = None; cr_alert_v = "N_A"
        cr_fy_end  = ""; cr_src = ""; cr_ref = ""

    overall = max_alert(sl_alert, pbj_alert_v, cr_alert_v)

    rows.append({
        **base,
        # State license
        "state_lic_type":        sl_type,
        "state_lic_term_date":   str(sl_term) if sl_term else "",
        "state_lic_action_date": str(sl_action) if sl_action else "",
        "state_lic_source":      sl_source,
        "state_lic_reg_ref":     sl_regref,
        "state_lic_notes":       sl_notes,
        "state_lic_alert":       sl_alert,
        # PBJ
        "pbj_quarter":           pbj_quarter_label,
        "pbj_term_date":         str(pbj_term) if pbj_term else "",
        "pbj_action_date":       str(pbj_act) if pbj_act else "",
        "pbj_source":            pbj_src,
        "pbj_reg_ref":           pbj_ref,
        "pbj_alert":             pbj_alert_v,
        # Cost report
        "cost_report_fy_end":    cr_fy_end,
        "cost_report_term_date": str(cr_term) if cr_term else "",
        "cost_report_action_date": str(cr_act) if cr_act else "",
        "cost_report_source":    cr_src,
        "cost_report_reg_ref":   cr_ref,
        "cost_report_alert":     cr_alert_v,
        # Overall
        "overall_alert":         overall,
    })

cal = pd.DataFrame(rows)

# ── Assertions ────────────────────────────────────────────────────────────────
print()
print("Assertions ...")
assert len(cal) == len(master), f"Row count mismatch: {len(cal)} vs {len(master)}"
print(f"  PASS: {len(cal):,} rows")

snf_pbj = cal[cal["pbj_alert"] != "N_A"]
assert len(snf_pbj) == 14425, f"Expected 14,425 SNF PBJ rows, got {len(snf_pbj):,}"
print(f"  PASS: SNF PBJ rows {len(snf_pbj):,}")

manual_matched = cal["state_lic_alert"].isin(["OVERDUE","CRITICAL","WARNING","UPCOMING","OK"]).sum()
print(f"  INFO: {manual_matched} facilities with known state license dates")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("Overall alert distribution:")
for lvl in ["OVERDUE", "CRITICAL", "WARNING", "UPCOMING", "OK", "MANUAL_CHECK"]:
    n = (cal["overall_alert"] == lvl).sum()
    if n:
        print(f"  {lvl:<12}  {n:6,}")

print()
print("State license alerts (facilities with known dates):")
lic_alerts = cal[cal["state_lic_alert"] != "MANUAL_CHECK"]["state_lic_alert"].value_counts()
for lvl in ["OVERDUE", "CRITICAL", "WARNING", "UPCOMING", "OK"]:
    n = lic_alerts.get(lvl, 0)
    if n:
        print(f"  {lvl:<12}  {n:3}")

print()
print(f"PBJ alert distribution (SNF, {len(snf_pbj):,} facilities):")
for lvl in ["OVERDUE", "CRITICAL", "WARNING", "UPCOMING", "OK"]:
    n = (snf_pbj["pbj_alert"] == lvl).sum()
    if n:
        print(f"  {lvl:<12}  {n:6,}")

cr_snf = cal[(cal["cost_report_alert"] != "N_A")]
print()
print(f"Cost report alert distribution (SNF, {len(cr_snf):,} with FYE data):")
for lvl in ["OVERDUE", "CRITICAL", "WARNING", "UPCOMING", "OK", "MANUAL_CHECK"]:
    n = (cr_snf["cost_report_alert"] == lvl).sum()
    if n:
        print(f"  {lvl:<12}  {n:6,}")

# ── Write outputs ─────────────────────────────────────────────────────────────
OUTPUT_DIR.mkdir(exist_ok=True)

cal.to_csv(CALENDAR_OUTPUT, index=False)
print()
print(f"Calendar output: {CALENDAR_OUTPUT}")
print(f"  Rows: {len(cal):,} | Cols: {len(cal.columns)}")

# Hotlist: OVERDUE + CRITICAL + WARNING, sorted by urgency then term date
hotlist = cal[cal["overall_alert"].isin(["OVERDUE", "CRITICAL", "WARNING"])].copy()
hotlist["_sort_key"] = hotlist["overall_alert"].map(ALERT_PRIORITY)
hotlist = hotlist.sort_values(["_sort_key", "state_lic_term_date", "pbj_term_date"],
                              ascending=[False, True, True])
hotlist = hotlist.drop(columns=["_sort_key"])
hotlist.to_csv(HOTLIST_OUTPUT, index=False)
print()
print(f"Hotlist output:  {HOTLIST_OUTPUT}")
print(f"  Rows: {len(hotlist):,} ({len(hotlist[hotlist['overall_alert']=='OVERDUE']):,} OVERDUE, "
      f"{len(hotlist[hotlist['overall_alert']=='CRITICAL']):,} CRITICAL, "
      f"{len(hotlist[hotlist['overall_alert']=='WARNING']):,} WARNING)")

print()
print("Column guide:")
print("  state_lic_term_date      Actual license expiry date (from source)")
print("  state_lic_action_date    Begin renewal application by this date")
print("  state_lic_source         Where the date came from")
print("  state_lic_reg_ref        Applicable statute / regulation")
print("  pbj_term_date            Next PBJ quarterly submission deadline")
print("  pbj_action_date          Target submission date (30 days before deadline)")
print("  pbj_reg_ref              42 CFR §483.75(l)(2)")
print("  cost_report_term_date    Annual cost report due date")
print("  cost_report_action_date  Target submission date (30 days before due)")
print("  cost_report_reg_ref      42 CFR §413.20(b)")
print("  overall_alert            Highest alert level across all items for this facility")
print()
print("To add state license dates: edit input/manual_license_dates.csv and rerun.")
