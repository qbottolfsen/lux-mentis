"""
11_nh_star_band_national.py
NH Five-Star band aggregation -- one row per overall star tier (1-5).

Computed from local outputs; no live API call.

Sources (both must already exist in output_reference/):
  nh_health_deficiencies_national.csv  -- one row per citation, all survey cycles
  nh_provider_info_national.csv        -- one row per facility, overall_star + staffing

Method:
  1. Count total citations per CCN across ALL survey cycles in the deficiencies file.
     (health_defic_cycle1 in provider_info = cycle 1 only; ~3x lower than all-cycle total.)
  2. Join per-CCN citation count with overall_star, rn_hprd, total_nurse_turnover
     from provider_info. Facilities with no deficiency record get citation count = 0.
  3. Group by overall_star; compute mean of each metric.

Output columns:
  overall_star            -- 1-5
  facility_count          -- number of facilities in star tier
  avg_total_citations     -- mean citation count across all survey cycles
  avg_rn_hprd             -- mean RN hours per resident day
  avg_total_turnover_pct  -- mean total nurse turnover (%)

Confirmed values (2026-07-22):
  1-star: 2,873 facilities | 47.2 citations | 0.50 HPRD | 54.9% turnover
  5-star: 3,045 facilities | 12.8 citations | 0.95 HPRD | 38.2% turnover

Output: output_reference/nh_star_band_national.csv

Pre-registered assertions (±5% on citations, tight on HPRD/turnover):
  Row count:  exactly 5 (one per star tier)
  1-star avg_total_citations: [44.9, 49.6]  (confirmed 47.2 ± 5%)
  5-star avg_total_citations: [12.2, 13.5]  (confirmed 12.8 ± 5%)
  1-star avg_rn_hprd:         [0.475, 0.525]
  5-star avg_rn_hprd:         [0.903, 0.998]
"""

import pathlib, sys

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required: pip install pandas")

SCRIPT_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output_reference"

DEFICIENCIES_FILE  = OUTPUT_DIR / "nh_health_deficiencies_national.csv"
PROVIDER_INFO_FILE = OUTPUT_DIR / "nh_provider_info_national.csv"
OUTPUT_FILE        = OUTPUT_DIR / "nh_star_band_national.csv"

# Confirmed values at ±5% for citation counts; ±5% for HPRD/turnover
EXPECTED = {
    1: {"fac": 2873, "cit_lo": 44.9, "cit_hi": 49.6, "hprd_lo": 0.475, "hprd_hi": 0.525, "turn_lo": 52.2, "turn_hi": 57.6},
    2: {"fac": 3025, "cit_lo": 33.5, "cit_hi": 37.1, "hprd_lo": 0.551, "hprd_hi": 0.609, "turn_lo": 46.8, "turn_hi": 51.8},
    3: {"fac": 2844, "cit_lo": 25.1, "cit_hi": 27.7, "hprd_lo": 0.599, "hprd_hi": 0.662, "turn_lo": 43.9, "turn_hi": 48.5},
    4: {"fac": 2783, "cit_lo": 18.8, "cit_hi": 20.8, "hprd_lo": 0.675, "hprd_hi": 0.746, "turn_lo": 40.9, "turn_hi": 45.2},
    5: {"fac": 3045, "cit_lo": 12.2, "cit_hi": 13.5, "hprd_lo": 0.903, "hprd_hi": 0.998, "turn_lo": 36.3, "turn_hi": 40.1},
}

print("NH Five-Star Band Aggregation")
print(f"Output: {OUTPUT_FILE}")
print()

for f in [DEFICIENCIES_FILE, PROVIDER_INFO_FILE]:
    if not f.exists():
        sys.exit(f"Required input not found: {f}\nRun the producing script first.")

# ── 1. Count total citations per CCN across all survey cycles ─────────────────
print("Loading deficiencies (counting citations per CCN across all survey cycles)...")
defi = pd.read_csv(DEFICIENCIES_FILE, dtype=str, usecols=["ccn"])
defi["ccn"] = defi["ccn"].str.strip().str.zfill(6)
cit_per_fac = defi.groupby("ccn").size().reset_index(name="total_citations")
print(f"  {len(defi):,} citation rows -> {len(cit_per_fac):,} unique CCNs")

# ── 2. Load provider info ─────────────────────────────────────────────────────
print("Loading provider info (overall_star, rn_hprd, total_nurse_turnover)...")
info = pd.read_csv(PROVIDER_INFO_FILE, dtype=str,
                   usecols=["ccn", "overall_star", "rn_hprd", "total_nurse_turnover"])
info["ccn"] = info["ccn"].str.strip().str.zfill(6)
info = info[info["overall_star"].isin(["1", "2", "3", "4", "5"])].copy()
info["overall_star"]          = info["overall_star"].astype(int)
info["rn_hprd"]               = pd.to_numeric(info["rn_hprd"], errors="coerce")
info["total_nurse_turnover"]  = pd.to_numeric(info["total_nurse_turnover"], errors="coerce")
print(f"  {len(info):,} facilities with rated star tier (1-5)")

# ── 3. Join: left join so unmatched facilities get citation_count = 0 ─────────
merged = info.merge(cit_per_fac, on="ccn", how="left")
merged["total_citations"] = merged["total_citations"].fillna(0).astype(int)
matched = (merged["total_citations"] > 0).sum()
print(f"  {matched:,} of {len(merged):,} facilities matched to deficiency records")
print()

# ── 4. Star-band aggregation ──────────────────────────────────────────────────
result = (
    merged.groupby("overall_star")
    .agg(
        facility_count         =("ccn",                  "count"),
        avg_total_citations    =("total_citations",       "mean"),
        avg_rn_hprd            =("rn_hprd",               "mean"),
        avg_total_turnover_pct =("total_nurse_turnover",  "mean"),
    )
    .round({"avg_total_citations": 1, "avg_rn_hprd": 2, "avg_total_turnover_pct": 1})
    .reset_index()
)

# ── 5. Assertions ─────────────────────────────────────────────────────────────
print("Assertions ...")

if len(result) != 5:
    raise AssertionError(f"FAILED: expected 5 star tiers, got {len(result)}")
print(f"  PASS: 5 star tiers present")

for _, row in result.iterrows():
    s    = int(row["overall_star"])
    exp  = EXPECTED[s]
    fac  = int(row["facility_count"])
    cit  = float(row["avg_total_citations"])
    hprd = float(row["avg_rn_hprd"])
    turn = float(row["avg_total_turnover_pct"])

    if fac != exp["fac"]:
        raise AssertionError(f"FAILED: {s}-star facility count {fac} != expected {exp['fac']}")
    if not (exp["cit_lo"] <= cit <= exp["cit_hi"]):
        raise AssertionError(f"FAILED: {s}-star avg citations {cit} outside [{exp['cit_lo']}, {exp['cit_hi']}]")
    if not (exp["hprd_lo"] <= hprd <= exp["hprd_hi"]):
        raise AssertionError(f"FAILED: {s}-star avg HPRD {hprd} outside [{exp['hprd_lo']}, {exp['hprd_hi']}]")
    if not (exp["turn_lo"] <= turn <= exp["turn_hi"]):
        raise AssertionError(f"FAILED: {s}-star avg turnover {turn} outside [{exp['turn_lo']}, {exp['turn_hi']}]")

    print(f"  PASS: {s}-star  {fac:,} fac  {cit:.1f} citations  {hprd:.2f} HPRD  {turn:.1f}% turnover")

# ── 6. Summary ────────────────────────────────────────────────────────────────
print()
print("Star-band summary (matches published README table):")
print(f"{'Star':<6} {'Facilities':>12} {'Avg citations':>14} {'RN HPRD':>9} {'Turnover':>10}")
for _, row in result.iterrows():
    print(f"  {int(row['overall_star']):<4} {int(row['facility_count']):>12,} {row['avg_total_citations']:>14.1f} {row['avg_rn_hprd']:>9.2f} {row['avg_total_turnover_pct']:>9.1f}%")
print()
print("NOTE: avg_total_citations = citations across ALL survey cycles.")
print("      health_defic_cycle1 in nh_provider_info = most recent cycle only (~3x lower).")

# ── 7. Write ──────────────────────────────────────────────────────────────────
OUTPUT_DIR.mkdir(exist_ok=True)
result.to_csv(OUTPUT_FILE, index=False)

print()
print(f"Output: {OUTPUT_FILE}")
print(f"Rows:   {len(result)}  Cols: {len(result.columns)}")
print()
print("Join keys:")
print("  overall_star  ->  nh_provider_info_national.csv (row-level groupby key)")
print("  Sources:  nh_health_deficiencies_national.csv + nh_provider_info_national.csv")
