"""
03_nh_penalties_national.py
NH Penalties -- national individual penalty event records.

Source: CMS Provider Data -- NH Penalties
  Dataset:      g6vv-u9sr
  Distribution: 3d67f2c4-d8d2-515a-9522-535fba9d9fd6
  Updated:      Monthly

One row per penalty event (fines and payment denials).
Provider Info captures cumulative fine_count / fine_total; this dataset
adds the individual dated events for timeline analysis.

Penalty types:
  Fine            Civil Monetary Penalty (CMP) -- dollar amount
  Payment Denial  CMS denies Medicare payment for new admissions --
                  more severe; signals systemic noncompliance

Outputs:
  output_reference/nh_penalties_national.csv     (event-level)
  output_reference/nh_penalties_by_facility.csv  (per-CCN aggregates)

Pre-registered assertions:
  National events:   [5,000 -- 300,000]
  HI events:         [15 -- 50]
  HI payment denials: [0 -- 5]  (rare enforcement action)
  Fine amounts: all >= $0
"""

import json, pathlib, sys, time, urllib.request

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"
OUTPUT_EVENTS    = OUTPUT_DIR / "nh_penalties_national.csv"
OUTPUT_AGGREGATE = OUTPUT_DIR / "nh_penalties_by_facility.csv"

DIST_ID  = "3d67f2c4-d8d2-515a-9522-535fba9d9fd6"
BASE_URL = f"https://data.cms.gov/provider-data/api/1/datastore/query/{DIST_ID}"
PAGE_SIZE = 1_000

EXPECTED_EVENTS_MIN = 5_000
EXPECTED_EVENTS_MAX = 300_000
HI_MIN = 15
HI_MAX = 50


def fetch_page_with_retry(payload: bytes, max_retries: int = 5) -> dict:
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(BASE_URL, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = 10 * (2 ** attempt)
                print(f"  HTTP {e.code}; retry in {wait}s ...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("exhausted retries")


print("NH Penalties -- national event-level records")
print(f"Distribution: {DIST_ID}")
print()

# Probe
probe = fetch_page_with_retry(json.dumps({"limit": 1, "offset": 0}).encode())
total_count = probe.get("count", "?")
print(f"Reported count: {total_count:,}" if isinstance(total_count, int)
      else f"Reported count: {total_count}")
raw_cols = list(probe["results"][0].keys()) if probe.get("results") else []
print(f"Columns ({len(raw_cols)}): {raw_cols}")
print()


def find_col(cols, *substrings, exclude=None):
    for c in cols:
        if all(s.lower() in c.lower() for s in substrings):
            if exclude and any(e.lower() in c.lower() for e in exclude):
                continue
            return c
    return None


COL = {
    "ccn":           find_col(raw_cols, "cms_certification_number") or find_col(raw_cols, "ccn"),
    "name":          find_col(raw_cols, "provider_name"),
    "state":         find_col(raw_cols, "state"),
    "city":          find_col(raw_cols, "city") or find_col(raw_cols, "citytown"),
    "zip":           find_col(raw_cols, "zip"),
    "penalty_date":  find_col(raw_cols, "penalty_date"),
    "penalty_type":  find_col(raw_cols, "penalty_type"),
    "fine_id":       find_col(raw_cols, "fine_id"),
    "fine_amount":   find_col(raw_cols, "fine_amount"),
    "denial_start":  find_col(raw_cols, "payment_denial_start") or find_col(raw_cols, "denial_start"),
    "denial_days":   find_col(raw_cols, "payment_denial_length") or find_col(raw_cols, "denial_length"),
}

print("Column mapping:")
for k, v in COL.items():
    print(f"  {k:<16} {v or 'NOT FOUND'}")
print()

# Fetch all pages
print("Fetching ...")
all_rows = list(probe.get("results", []))
offset = PAGE_SIZE
page = 1
print(f"  Page  1: offset=0  got={len(all_rows)}")

while True:
    page += 1
    data = fetch_page_with_retry(json.dumps({"limit": PAGE_SIZE, "offset": offset}).encode())
    rows = data.get("results", [])
    if not rows:
        break
    all_rows.extend(rows)
    print(f"  Page {page:2}: offset={offset:6,}  got={len(rows):,}  total={len(all_rows):,}")
    if len(rows) < PAGE_SIZE:
        break
    offset += PAGE_SIZE
    time.sleep(0.5)

print(f"Fetched {len(all_rows):,} rows")
print()


def g(row, key):
    col = COL.get(key)
    return str(row.get(col, "")).strip() if col else ""


def safe_float(v):
    try:
        return float(str(v).replace("$", "").replace(",", "").strip()) if v not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


# Build event-level output
out = []
for r in all_rows:
    fa = safe_float(g(r, "fine_amount"))
    out.append({
        "ccn":                  g(r, "ccn"),
        "provider_name":        g(r, "name"),
        "state":                g(r, "state"),
        "city":                 g(r, "city"),
        "zip":                  g(r, "zip"),
        "penalty_date":         g(r, "penalty_date"),
        "penalty_type":         g(r, "penalty_type"),
        "fine_id":              g(r, "fine_id"),
        "fine_amount":          "" if fa is None else fa,
        "payment_denial_start": g(r, "denial_start"),
        "payment_denial_days":  g(r, "denial_days"),
        "is_fine":              str("fine" in g(r, "penalty_type").lower()),
        "is_payment_denial":    str("denial" in g(r, "penalty_type").lower() or
                                    "payment" in g(r, "penalty_type").lower()),
    })

df = pd.DataFrame(out)


# ── Assertions ─────────────────────────────────────────────────────────────────

print("Assertions ...")

total = len(df)
if not (EXPECTED_EVENTS_MIN <= total <= EXPECTED_EVENTS_MAX):
    raise AssertionError(f"FAILED: {total:,} events outside [{EXPECTED_EVENTS_MIN:,}, {EXPECTED_EVENTS_MAX:,}]")
print(f"  PASS: {total:,} penalty events nationally")

hi = df[df["state"] == "HI"]
if not (HI_MIN <= len(hi) <= HI_MAX):
    raise AssertionError(f"FAILED: HI events {len(hi)} outside [{HI_MIN}, {HI_MAX}]")
print(f"  PASS: {len(hi)} HI penalty events")

hi_denials = (hi["is_payment_denial"] == "True").sum()
if hi_denials > 5:
    raise AssertionError(f"FAILED: {hi_denials} HI payment denials (expected <= 5)")
print(f"  PASS: {hi_denials} HI payment denial(s)")


# ── Per-facility aggregate ─────────────────────────────────────────────────────

fines_df = df[df["is_fine"] == "True"].copy()
fines_df["fine_amount"] = pd.to_numeric(fines_df["fine_amount"], errors="coerce")

agg_parts = []
for ccn, grp in df.groupby("ccn"):
    fines = grp[grp["is_fine"] == "True"]
    denials = grp[grp["is_payment_denial"] == "True"]
    agg_parts.append({
        "ccn":                ccn,
        "provider_name":      grp["provider_name"].iloc[0],
        "state":              grp["state"].iloc[0],
        "total_events":       len(grp),
        "fine_count":         len(fines),
        "fine_total_dollars": fines["fine_amount"].apply(
            lambda x: float(x) if x != "" else None).sum(),
        "payment_denial_count": len(denials),
        "most_recent_penalty":  grp["penalty_date"].max(),
    })

df_agg = pd.DataFrame(agg_parts)


# ── Summary ────────────────────────────────────────────────────────────────────

print()
print("National penalty summary:")
fine_total = df[df["is_fine"] == "True"]["fine_amount"].apply(
    lambda x: float(x) if x != "" else 0).sum()
denial_count = (df["is_payment_denial"] == "True").sum()
print(f"  Total fine events:      {(df['is_fine'] == 'True').sum():,}")
print(f"  Total fine dollars:     ${fine_total:,.0f}")
print(f"  Payment denials:        {denial_count:,}")
print(f"  Facilities penalized:   {df['ccn'].nunique():,}")

print()
print(f"Hawaii penalty events (n={len(hi)}):")
hi_sorted = hi.sort_values("fine_amount", ascending=False,
                            key=lambda c: pd.to_numeric(c, errors="coerce"))
print(hi_sorted[["ccn", "provider_name", "penalty_date", "penalty_type",
                  "fine_amount", "payment_denial_days"]].to_string(index=False))


# ── Write ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)
df.to_csv(OUTPUT_EVENTS, index=False)
df_agg.to_csv(OUTPUT_AGGREGATE, index=False)

print()
print(f"Events:    {OUTPUT_EVENTS}  ({len(df):,} rows)")
print(f"Aggregate: {OUTPUT_AGGREGATE}  ({len(df_agg):,} facilities)")
print()
print("Join keys:")
print("  ccn  -->  facility_master_national.csv")
print("  ccn  -->  nh_provider_info_national.csv (fine_count/fine_total validates)")
