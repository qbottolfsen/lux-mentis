"""
09_vbp_performance.py  —  national build
National LTPAC Platform
SNF Value-Based Purchasing (VBP) — facility performance integration.

VBP Program overview:
  CMS adjusts SNF Medicare payments (±2% pool) based on performance scores
  across 4 measures. Facilities scoring above a threshold receive a bonus
  (multiplier > 1.0); below threshold receive a payment reduction (< 1.0).

Measures:
  SNFRM  — Skilled Nursing Facility Readmission Measure (30-day)
  HAI    — Healthcare-Associated Infection rate (MRSA/C.diff)
  TNT    — Total Nursing Staff Turnover rate
  TNSH   — Total Nurse Staffing Hours per Resident Day (adjusted)

Each measure: Baseline (FY2022) | Performance (FY2024) | Achievement | Improvement | Measure Score

Sources:
  Dataset: 284v-j9fz  — CMS Provider Data: FY 2026 SNF VBP Facility-Level Dataset
  Facility file resolved at runtime from DKAN metastore (URL hash changes each update).
  Aggregate file (FY_2026_SNF_VBP_Aggregate_Performance.csv) is not indexed in DKAN;
  place it in input/ to enable national SNFRM benchmarks, or omit (optional enrichment).

Pre-registered assertions:
  Facility rows: [12,000 -- 15,500]  (12,901 scored + ~1,600 below case minimum expected)
  State column present: True
  HI rows: [30 -- 55]

Output (per-state run):
  output_reference/output_vbp/{STATE}/01_vbp_facility.csv   — per-facility scores, deltas, flags
  output_reference/output_vbp/{STATE}/02_vbp_state.csv      — state-level VBP summary
  output_reference/output_vbp/{STATE}/03_vbp_measures.csv   — individual measure component scores
  output_reference/output_vbp/{STATE}/00_vbp_summary.txt    — narrative

Output (national run, no --state):
  output_reference/output_vbp/national/01_vbp_facility.csv  — all states
  output_reference/output_vbp/national/02_vbp_state.csv     — state-level summary, all states
  output_reference/output_vbp/national/03_vbp_measures.csv
  output_reference/output_vbp/national/00_vbp_summary.txt

Run:
  python 09_vbp_performance.py              # all states
  python 09_vbp_performance.py --state HI   # single state
"""

import argparse
import io
import json
import math
import sys
import time
import urllib.request
from pathlib import Path
from datetime import date

import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
INPUT_DIR  = SCRIPT_DIR / "input"
OUT_BASE   = SCRIPT_DIR / "output_reference" / "output_vbp"
VINTAGE    = "FY2026"

# ── CMS Source ───────────────────────────────────────────────────────────────
DATASET_ID   = "284v-j9fz"
DKAN_META    = f"https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{DATASET_ID}"
FAC_FILENAME = "Facility_Performance"

NATIONAL_FAC_MIN = 12_000
NATIONAL_FAC_MAX = 15_500
HI_FAC_MIN = 30
HI_FAC_MAX = 55


def _resolve_facility_url() -> str:
    """Fetch DKAN metastore to get current download URL for facility performance file."""
    with urllib.request.urlopen(DKAN_META, timeout=30) as r:
        meta = json.loads(r.read())
    for dist in meta.get("distribution", []):
        url = dist.get("downloadURL", "")
        if FAC_FILENAME in url:
            return url
    raise RuntimeError(
        f"Facility Performance file not found in DKAN metadata for {DATASET_ID}. "
        f"Check https://data.cms.gov/provider-data/dataset/{DATASET_ID}"
    )


def _download_bytes(url: str, label: str = "", max_retries: int = 3) -> io.BytesIO:
    """Download URL with retries, return BytesIO buffer."""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "text/csv,*/*"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            print(f"  Downloaded {label or url}: {len(data):,} bytes")
            return io.BytesIO(data)
        except Exception as exc:
            if attempt < max_retries - 1:
                wait = 10 * (2 ** attempt)
                print(f"  HTTP error ({exc}); retry in {wait}s ...")
                time.sleep(wait)
            else:
                raise

# ── Column map: verbose CMS names → short keys ───────────────────────────────
COL_MAP = {
    "CMS Certification Number (CCN)":                                                   "ccn",
    "Provider Name":                                                                    "provider_name",
    "Provider Address":                                                                 "provider_address",
    "City/Town":                                                                        "city",
    "State":                                                                            "state",
    "ZIP Code":                                                                         "zip_code",
    "SNF VBP Program Ranking":                                                          "vbp_rank",
    "Baseline Period: FY 2022 Risk-Standardized Readmission Rate":                      "snfrm_base",
    "Performance Period: FY 2024 Risk-Standardized Readmission Rate":                   "snfrm_perf",
    "SNFRM Achievement Score":                                                          "snfrm_achievement",
    "SNFRM Improvement Score":                                                          "snfrm_improvement",
    "SNFRM Measure Score":                                                              "snfrm_score",
    "Baseline Period: FY 2022 Risk-Standardized Healthcare-Associated Infection Rate":  "hai_base",
    "Performance Period: FY 2024 Risk-Standardized Healthcare-Associated Infection Rate": "hai_perf",
    "SNF HAI Achievement Score":                                                        "hai_achievement",
    "SNF HAI Improvement Score":                                                        "hai_improvement",
    "SNF HAI Measure Score":                                                            "hai_score",
    "Baseline Period: FY 2022 Total Nursing Staff Turnover Rate":                       "turnover_base",
    "Performance Period: FY 2024 Total Nursing Staff Turnover Rate":                    "turnover_perf",
    "Total Nursing Staff Turnover Achievement Score":                                   "turnover_achievement",
    "Total Nursing Staff Turnover Improvement Score":                                   "turnover_improvement",
    "Total Nursing Staff Turnover Measure Score":                                       "turnover_score",
    "Baseline Period: FY 2022 Adjusted Total Nursing Staff Hours per Resident Day":     "staffing_hprd_base",
    "Performance Period: FY 2024 Adjusted Total Nursing Staff Hours per Resident Day":  "staffing_hprd_perf",
    "Total Nurse Staffing Achievement Score":                                           "staffing_achievement",
    "Total Nurse Staffing Improvement Score":                                           "staffing_improvement",
    "Total Nurse Staffing Measure Score":                                               "staffing_score",
    "Performance Score":                                                                "performance_score",
    "Incentive Payment Multiplier":                                                     "incentive_multiplier",
}

# Footnote columns — suppression reason for performance-period values
FOOTNOTE_MAP = {
    "Footnote -- Performance Period: FY 2024 Risk-Standardized Readmission Rate":                           "fn_snfrm",
    "Footnote -- Performance Period: FY 2024 Risk-Standardized Healthcare-Associated Infection Rate":       "fn_hai",
    "Footnote -- Performance Period: FY 2024 Total Nursing Staff Turnover Rate":                            "fn_turnover",
    "Footnote -- Performance Period: FY 2024 Adjusted Total Nursing Staff Hours per Resident Day":          "fn_staffing",
}

NULL_SENTINEL    = "---"
CASE_MIN_PHRASE  = "case minimum"

NUMERIC_COLS = [
    "vbp_rank",
    "snfrm_base","snfrm_perf","snfrm_achievement","snfrm_improvement","snfrm_score",
    "hai_base","hai_perf","hai_achievement","hai_improvement","hai_score",
    "turnover_base","turnover_perf","turnover_achievement","turnover_improvement","turnover_score",
    "staffing_hprd_base","staffing_hprd_perf",
    "staffing_achievement","staffing_improvement","staffing_score",
    "performance_score","incentive_multiplier",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_csv_safe(src, **kwargs):
    """Accept a file path or io.BytesIO; try multiple encodings."""
    for enc in ("cp1252", "utf-8", "latin-1"):
        try:
            if isinstance(src, io.BytesIO):
                src.seek(0)
            return pd.read_csv(src, dtype=str, keep_default_na=False, encoding=enc, **kwargs)
        except UnicodeDecodeError:
            continue
    name = src.name if hasattr(src, "name") else repr(src)
    raise ValueError(f"Cannot decode {name}")


def assert_count(label, actual, expected, context=""):
    if actual != expected:
        msg = f"  ASSERTION FAIL [{label}]: expected {expected}, got {actual}"
        if context: msg += f" — {context}"
        print(msg)
        return False
    print(f"  ASSERTION OK  [{label}]: {actual}")
    return True


def to_float(s):
    try:
        v = float(str(s).strip())
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None


def suppression_reason(footnote_val):
    v = str(footnote_val).strip()
    if v in ("", NULL_SENTINEL):
        return ""
    if CASE_MIN_PHRASE in v.lower():
        return "VOL_SUPPRESSED"
    return "SUPPRESSED"


# ── Load ──────────────────────────────────────────────────────────────────────

def load_vbp(src, state_filter=None):
    """Load VBP facility file from path or BytesIO; filter to one state if --state is given."""
    raw = read_csv_safe(src)
    print(f"  VBP raw total rows: {len(raw)}")

    if "State" not in raw.columns:
        raise KeyError(f"Expected 'State' column not found. Columns: {list(raw.columns[:10])}")

    raw["State"] = raw["State"].str.strip().str.upper()

    if state_filter:
        df = raw[raw["State"] == state_filter.upper()].copy()
        print(f"  VBP rows for {state_filter}: {len(df)}")
        if len(df) == 0:
            avail = sorted(raw["State"].unique())
            raise ValueError(f"No rows for state '{state_filter}'. Available: {avail}")
    else:
        df = raw.copy()
        print(f"  Processing all states: {df['State'].nunique()} states, {len(df)} facilities")

    # Extract footnotes before renaming
    fn_cols = {}
    for src, dst in FOOTNOTE_MAP.items():
        if src in df.columns:
            fn_cols[dst] = df[src].values

    rename = {k: v for k, v in COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = df[c].replace(NULL_SENTINEL, "")

    for dst, vals in fn_cols.items():
        df[dst] = vals
        df[f"{dst}_flag"] = [suppression_reason(v) for v in vals]

    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def load_vbp_national_agg(src=None):
    """Return dict of national average rates from aggregate file, or {} if unavailable."""
    nat = {}
    if src is None:
        return nat
    try:
        agg = read_csv_safe(src)
        for col in agg.columns:
            v = to_float(agg[col].iloc[0]) if len(agg) else None
            if v is None:
                continue
            cl = col.lower()
            if "baseline" in cl and "readmission" in cl:
                nat["snfrm_base_national"] = v
            elif "performance" in cl and "readmission" in cl:
                nat["snfrm_perf_national"] = v
    except Exception as e:
        print(f"  WARNING: Could not parse aggregate file — {e}")
    return nat


# ── Rank / tier computation ───────────────────────────────────────────────────

def _tier(score, q25, median, q75):
    if pd.isna(score):   return "NO_SCORE"
    if score <= q25:     return "BOTTOM_QUARTILE"
    if score <= median:  return "BELOW_MEDIAN"
    if score <= q75:     return "ABOVE_MEDIAN"
    return "TOP_QUARTILE"


def compute_ranks_and_tiers(df):
    """
    Add national and state-relative percentile ranks + tier labels.
    Returns (scored_df, national_quartiles_dict).
    scored_df contains only facilities with a performance_score.
    """
    scored = df[df["performance_score"].notna()].copy()

    # National percentile rank
    scored["national_pct_rank"] = scored["performance_score"].rank(pct=True).round(3)

    nat_q25 = scored["performance_score"].quantile(0.25)
    nat_med  = scored["performance_score"].median()
    nat_q75  = scored["performance_score"].quantile(0.75)
    print(f"  National VBP — Q1={nat_q25:.1f}  Median={nat_med:.1f}  Q3={nat_q75:.1f}  n={len(scored)}")

    scored["national_vbp_tier"] = scored["performance_score"].apply(
        lambda s: _tier(s, nat_q25, nat_med, nat_q75)
    )

    # State-relative percentile rank and tier
    state_groups = []
    for _, grp in scored.groupby("state"):
        grp = grp.copy()
        grp["state_pct_rank"] = grp["performance_score"].rank(pct=True).round(3)
        sq25 = grp["performance_score"].quantile(0.25)
        smed  = grp["performance_score"].median()
        sq75  = grp["performance_score"].quantile(0.75)
        grp["state_vbp_tier"] = grp["performance_score"].apply(
            lambda s: _tier(s, sq25, smed, sq75)
        )
        state_groups.append(grp)
    scored = pd.concat(state_groups, ignore_index=True)

    # Payment direction
    scored["payment_direction"] = scored["incentive_multiplier"].apply(
        lambda x: "BONUS"   if pd.notna(x) and x > 1.0
        else     ("PENALTY" if pd.notna(x) and x < 1.0 else "NEUTRAL")
    )

    # Deltas (positive = worsening for readmission/HAI/turnover; positive = improvement for staffing HPRD)
    for base_col, perf_col, delta_col in [
        ("snfrm_base",        "snfrm_perf",        "snfrm_delta"),
        ("turnover_base",     "turnover_perf",      "turnover_delta"),
        ("staffing_hprd_base","staffing_hprd_perf", "staffing_hprd_delta"),
    ]:
        if base_col in scored.columns and perf_col in scored.columns:
            scored[delta_col] = (scored[perf_col] - scored[base_col]).round(4)

    nat_quartiles = {"q25": nat_q25, "median": nat_med, "q75": nat_q75, "n": len(scored)}
    return scored, nat_quartiles


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SNF VBP performance — national or per-state")
    parser.add_argument("--state", default=None,
                        help="2-letter state code (e.g. HI). Omit for all states.")
    args = parser.parse_args()

    scope = args.state.upper() if args.state else "NATIONAL"
    out_dir = OUT_BASE / (args.state.upper() if args.state else "national")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== SNF VBP Performance [{scope}] ===")

    # Download facility file from CMS DKAN (resolves URL from metastore to handle hash changes)
    print("Resolving VBP facility file from DKAN metastore ...")
    fac_url = _resolve_facility_url()
    print(f"  URL: {fac_url}")
    fac_buf = _download_bytes(fac_url, label="VBP facility file")

    # Aggregate file — not indexed in DKAN; use local copy from input/ if present
    agg_src = None
    local_agg = INPUT_DIR / "FY_2026_SNF_VBP_Aggregate_Performance.csv"
    if local_agg.exists():
        agg_src = local_agg
        print(f"  Aggregate file: {local_agg}")
    else:
        print("  Aggregate file not found in input/ — national SNFRM benchmarks will be omitted.")

    # Row-count assertion on raw download
    raw_check = read_csv_safe(io.BytesIO(fac_buf.getvalue()))
    total_raw = len(raw_check)
    if not (NATIONAL_FAC_MIN <= total_raw <= NATIONAL_FAC_MAX):
        raise AssertionError(
            f"FAILED: facility file has {total_raw:,} rows — expected [{NATIONAL_FAC_MIN:,}, {NATIONAL_FAC_MAX:,}]"
        )
    print(f"  PASS: {total_raw:,} rows in facility file")
    hi_raw = (raw_check.get("State", raw_check.get("state", "")) == "HI").sum() if "State" in raw_check.columns or "state" in raw_check.columns else 0
    state_col_raw = "State" if "State" in raw_check.columns else ("state" if "state" in raw_check.columns else None)
    if state_col_raw:
        hi_n = (raw_check[state_col_raw].str.strip().str.upper() == "HI").sum()
        if not (HI_FAC_MIN <= hi_n <= HI_FAC_MAX):
            raise AssertionError(f"FAILED: HI facility rows {hi_n} outside [{HI_FAC_MIN}, {HI_FAC_MAX}]")
        print(f"  PASS: {hi_n} HI rows")
    del raw_check

    # Always load the full national dataset so national percentile ranks are
    # computed against all facilities, even when outputting a single state.
    print("Loading full VBP dataset (national ranks require all rows) ...")
    vbp_all = load_vbp(fac_buf, state_filter=None)

    print("Loading VBP national aggregate ...")
    nat_agg = load_vbp_national_agg(agg_src)
    for k, v in nat_agg.items():
        print(f"  {k}: {v:.5f}")

    print("Computing national and state-relative ranks ...")
    scored_all, nat_q = compute_ranks_and_tiers(vbp_all)

    # Merge ranks back onto full national dataset
    rank_cols = [c for c in [
        "ccn","national_pct_rank","national_vbp_tier",
        "state_pct_rank","state_vbp_tier","payment_direction",
        "snfrm_delta","turnover_delta","staffing_hprd_delta",
    ] if c in scored_all.columns]
    out_all = vbp_all.merge(scored_all[rank_cols], on="ccn", how="left")
    out_all["in_vbp"] = out_all["performance_score"].notna()

    # Filter to requested state (output only), ranks already national
    if args.state:
        out_df = out_all[out_all["state"] == args.state.upper()].copy()
        print(f"  Output filtered to {scope}: {len(out_df)} facilities")
    else:
        out_df = out_all

    n_scored  = int(out_df["in_vbp"].sum())
    n_total   = len(out_df)
    n_bonus   = int((out_df.get("payment_direction","") == "BONUS").sum())   if "payment_direction" in out_df.columns else 0
    n_penalty = int((out_df.get("payment_direction","") == "PENALTY").sum()) if "payment_direction" in out_df.columns else 0

    # ── Output 01: facility VBP ───────────────────────────────────────────────
    facility_cols = [
        "ccn","provider_name","provider_address","city","state","zip_code",
        "in_vbp","vbp_rank","performance_score","incentive_multiplier",
        "payment_direction",
        "national_pct_rank","national_vbp_tier",
        "state_pct_rank","state_vbp_tier",
        "snfrm_base","snfrm_perf","snfrm_score","snfrm_delta",
        "hai_base","hai_perf","hai_score",
        "turnover_base","turnover_perf","turnover_score","turnover_delta",
        "staffing_hprd_base","staffing_hprd_perf","staffing_score","staffing_hprd_delta",
        "fn_snfrm_flag","fn_hai_flag","fn_turnover_flag","fn_staffing_flag",
    ]
    out1_cols = [c for c in facility_cols if c in out_df.columns]
    out1 = out_dir / "01_vbp_facility.csv"
    out_df[out1_cols].sort_values(
        ["state","performance_score"] if "state" in out_df.columns else ["performance_score"],
        na_position="last"
    ).to_csv(out1, index=False, encoding="utf-8")
    print(f"\nWrote {out1}: {n_total} facilities")

    # ── Output 02: state summary ──────────────────────────────────────────────
    if "state" in out_df.columns:
        rankable = out_df[out_df["performance_score"].notna()].copy()
        state_summary = rankable.groupby("state").agg(
            facility_count            = ("ccn",               "count"),
            avg_performance_score     = ("performance_score", "mean"),
            min_performance_score     = ("performance_score", "min"),
            max_performance_score     = ("performance_score", "max"),
            bonus_count               = ("payment_direction", lambda x: (x == "BONUS").sum()),
            penalty_count             = ("payment_direction", lambda x: (x == "PENALTY").sum()),
            nat_bottom_quartile_count = ("national_vbp_tier", lambda x: (x == "BOTTOM_QUARTILE").sum()),
            nat_top_quartile_count    = ("national_vbp_tier", lambda x: (x == "TOP_QUARTILE").sum()),
        ).round(2).reset_index()
        out2 = out_dir / "02_vbp_state.csv"
        state_summary.to_csv(out2, index=False, encoding="utf-8")
        print(f"Wrote {out2.name}: {len(state_summary)} states/territories")

    # ── Output 03: measure components ────────────────────────────────────────
    measure_cols = [
        "ccn","provider_name","state","performance_score",
        "national_vbp_tier","state_vbp_tier",
        "snfrm_score","fn_snfrm_flag",
        "hai_score","fn_hai_flag",
        "turnover_score","fn_turnover_flag",
        "staffing_score","fn_staffing_flag",
    ]
    out3_cols = [c for c in measure_cols if c in out_df.columns]
    out3 = out_dir / "03_vbp_measures.csv"
    out_df[out3_cols].sort_values("performance_score", na_position="last").to_csv(
        out3, index=False, encoding="utf-8"
    )
    print(f"Wrote {out3.name}: {n_total} facilities")

    # ── Summary text ──────────────────────────────────────────────────────────
    summary_lines = [
        f"SNF VBP PERFORMANCE — {VINTAGE}",
        f"Scope: {scope}",
        f"Run date: {date.today().isoformat()}",
        f"Data: CMS dataset {DATASET_ID} ({VINTAGE})",
        "",
        f"UNIVERSE: {n_total} facilities ({n_scored} with VBP score, "
        f"{n_total - n_scored} below case minimum / not scored)",
        f"  Bonus (multiplier > 1.0):   {n_bonus}",
        f"  Penalty (multiplier < 1.0): {n_penalty}",
        "",
        f"NATIONAL VBP DISTRIBUTION (n={nat_q['n']} scored facilities):",
        f"  Q1={nat_q['q25']:.1f}  Median={nat_q['median']:.1f}  Q3={nat_q['q75']:.1f}",
        "",
    ]

    if nat_agg:
        summary_lines.append("NATIONAL SNFRM BENCHMARKS (readmission):")
        for k, v in nat_agg.items():
            summary_lines.append(f"  {k}: {v:.5f}")
        summary_lines.append("")

    if scope != "NATIONAL" and "state" in out_df.columns:
        st_scored = out_df[out_df["performance_score"].notna()]
        if len(st_scored):
            sq25 = st_scored["performance_score"].quantile(0.25)
            smed  = st_scored["performance_score"].median()
            sq75  = st_scored["performance_score"].quantile(0.75)
            summary_lines += [
                f"{scope} VBP DISTRIBUTION (n={len(st_scored)} scored facilities):",
                f"  Q1={sq25:.1f}  Median={smed:.1f}  Q3={sq75:.1f}",
                "",
                f"BOTTOM 5 {scope} VBP PERFORMERS:",
            ]
            for _, row in st_scored.sort_values("performance_score").head(5).iterrows():
                mult_s = f"{row['incentive_multiplier']:.4f}" if pd.notna(row.get("incentive_multiplier")) else "N/A"
                summary_lines.append(
                    f"  {str(row.get('provider_name',''))[:45]:<45} "
                    f"Score={row.get('performance_score',0):.2f}  Multiplier={mult_s}  "
                    f"NatTier={row.get('national_vbp_tier','')}"
                )
            summary_lines += ["", f"TOP 5 {scope} VBP PERFORMERS:"]
            for _, row in st_scored.sort_values("performance_score", ascending=False).head(5).iterrows():
                mult_s = f"{row['incentive_multiplier']:.4f}" if pd.notna(row.get("incentive_multiplier")) else "N/A"
                summary_lines.append(
                    f"  {str(row.get('provider_name',''))[:45]:<45} "
                    f"Score={row.get('performance_score',0):.2f}  Multiplier={mult_s}  "
                    f"NatTier={row.get('national_vbp_tier','')}"
                )
            summary_lines.append("")

    summary_lines += [
        "METHODOLOGY NOTE: VBP Performance Score is a composite of 4 measure scores.",
        "  Facilities missing case minimums on 1+ measures are still in the program",
        "  but scored only on available measures — composite may be artificially",
        "  inflated or deflated. See fn_*_flag columns for per-measure suppression status.",
        "  national_vbp_tier: relative to full national distribution.",
        "  state_vbp_tier:    relative to within-state distribution only.",
    ]

    summary_text = "\n".join(summary_lines)
    print()
    print(summary_text)
    out0 = out_dir / "00_vbp_summary.txt"
    out0.write_text(summary_text, encoding="utf-8")
    print(f"\nWrote {out0.name}")
    print("Done.")


if __name__ == "__main__":
    main()
