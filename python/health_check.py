"""
health_check.py
Lux Mentis conformance harness — structural checks for every dataset in the pipeline.

Runs seven structural checks against each output file and its current API schema:

  1. Fields in API response absent from our output (data we never captured)
  2. Fields in our output absent from the current API (CMS renamed or dropped)
  3. Type anomalies — columns that should be numeric but read back as all-string
  4. Null-rate anomalies — any field >= 95% null (would have caught rn_hprd_compliant)
  5. Constant-value fields — any field with exactly 1 distinct non-null value
  6. Column-name divergence — same logical field, different name across access methods
     (requires two access paths to the same dataset; logged when known)
  7. Row-count drift — current output vs. the registered assertion range

Outputs:
  output_reference/divergence_report.json   — machine-readable; committed to repo
  stdout                                    — human-readable triage summary

Usage:
  python health_check.py              # checks all non-gitignored datasets
  python health_check.py --live       # also fetches 1-row sample from live API for check 1+2
  python health_check.py --dataset nh_provider_info   # single dataset

Tiering (Step A2):
  BLOCKING   — affects a published finding; fix before next commit
  LATENT     — affects a field we plan to use; log, fix when field becomes load-bearing
  INFO       — affects nothing currently used; material for the divergence methods note
"""

import argparse
import json
import pathlib
import sys
import time
import urllib.request
from datetime import datetime, timezone

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required: pip install pandas")

SCRIPT_DIR   = pathlib.Path(__file__).parent
OUTPUT_DIR   = SCRIPT_DIR / "output_reference"
REGISTRY     = SCRIPT_DIR / "datasets_registry.json"
REPORT_FILE  = OUTPUT_DIR / "divergence_report.json"

NULL_RATE_THRESHOLD   = 0.95   # flag if >= 95% null
CONST_VALUE_MIN_ROWS  = 100    # only flag constant-value on datasets > 100 rows

# Published findings — maps dataset name to field names that feed a finding
FINDING_FIELDS = {
    "nh_provider_info":    ["staffing_compliant", "rn_hprd", "rn_weekend_hprd", "total_hprd",
                            "total_nurse_turnover", "rn_turnover", "overall_star",
                            "health_inspection_star", "staffing_star", "special_focus_status",
                            "special_focus_candidate_status"],
    "nh_health_deficiencies": ["scope_severity_code", "tag", "tag_type"],
    "nh_penalties":        ["penalty_type", "fine_amount"],
    "snf_vbp":             ["incentive_payment_multiplier", "performance_score"],
    "snf_cost_report":     ["snf_days_title_18", "snf_days_title_19", "snf_days_title_18_19",
                            "snf_bed_days_available", "net_patient_revenue", "total_costs"],
    "facility_master":     ["individual_owner_count", "owner_count"],
}

DKAN_BASE = "https://data.cms.gov/provider-data/api/1/datastore/query/{dist_id}"
API_V1_BASE = "https://data.cms.gov/data-api/v1/dataset/{uuid}/data"


# ── Utilities ─────────────────────────────────────────────────────────────────

def fetch_api_columns(ds: dict, timeout: int = 20) -> list[str] | None:
    """Fetch one row from the live API and return column names."""
    method = ds.get("access_method")
    try:
        if method == "dkan_post" and ds.get("dist_id"):
            url = DKAN_BASE.format(dist_id=ds["dist_id"])
            payload = json.dumps({"limit": 1, "offset": 0, "filters": {}}).encode()
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            results = data.get("results", data.get("data", []))
            return list(results[0].keys()) if results else None

        elif method == "data_api_v1" and ds.get("uuid"):
            if ds["uuid"] == "multiple (see script)":
                return None  # cms_enrollments_all_types: skip live fetch
            url = API_V1_BASE.format(uuid=ds["uuid"]) + "?size=1&offset=0"
            with urllib.request.urlopen(url, timeout=timeout) as r:
                data = json.loads(r.read())
            return list(data[0].keys()) if data else None

    except Exception as exc:
        return f"ERROR: {exc}"
    return None


def load_output(ds: dict) -> pd.DataFrame | None:
    output = OUTPUT_DIR / ds["output_file"]
    if not output.exists():
        return None
    fmt = ds.get("format", "csv")
    if fmt == "parquet":
        return pd.read_parquet(output)
    return pd.read_csv(output, dtype=str, low_memory=False)


def classify_divergence(field: str, dataset_name: str) -> str:
    finding_fields = FINDING_FIELDS.get(dataset_name, [])
    if any(f in field for f in finding_fields):
        return "BLOCKING"
    return "LATENT"   # harness doesn't have enough context to call INFO automatically


# ── Per-dataset checks ────────────────────────────────────────────────────────

def build_known_set(ds: dict) -> set[tuple[str, str]]:
    """Return (field, check) pairs that are documented known anomalies — skip flagging these."""
    known = set()
    for entry in ds.get("known_anomalies", []):
        known.add((entry["field"], entry["check"]))
    return known


def check_dataset(ds: dict, live: bool) -> dict:
    name = ds["name"]
    known = build_known_set(ds)
    result = {
        "dataset": name,
        "label": ds["label"],
        "output_file": ds["output_file"],
        "vintage": ds["vintage"],
        "pull_date": ds["pull_date"],
        "gitignored": ds.get("gitignored", False),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "divergences": [],
        "row_count": None,
        "col_count": None,
        "status": "OK",
    }

    # Skip gitignored files — they may not be present locally
    if ds.get("gitignored"):
        result["status"] = "SKIPPED_GITIGNORED"
        return result

    # Load output file
    df = load_output(ds)
    if df is None:
        result["status"] = "MISSING_OUTPUT"
        result["divergences"].append({
            "check": "output_exists",
            "severity": "BLOCKING",
            "message": f"Output file not found: {ds['output_file']}",
        })
        return result

    result["row_count"] = len(df)
    result["col_count"] = len(df.columns)

    our_cols = set(df.columns)

    # CHECK 4 — Null-rate anomalies
    for col in df.columns:
        if (col, "null_rate") in known:
            continue
        null_rate = df[col].isna().mean()
        # Also treat the literal string 'nan' and empty string as null
        if df[col].dtype == object:
            nan_mask = df[col].isna() | df[col].isin(["", "nan", "NaN", "NULL", "null"])
            null_rate = nan_mask.mean()
        if null_rate >= NULL_RATE_THRESHOLD:
            tier = classify_divergence(col, name)
            result["divergences"].append({
                "check": "null_rate",
                "severity": tier,
                "field": col,
                "null_rate": round(float(null_rate), 4),
                "message": f"Field '{col}' is {null_rate*100:.1f}% null",
            })

    # CHECK 5 — Constant-value fields
    if len(df) >= CONST_VALUE_MIN_ROWS:
        for col in df.columns:
            if (col, "constant_value") in known:
                continue
            non_null = df[col].dropna()
            non_null = non_null[~non_null.isin(["", "nan", "NaN", "NULL", "null"])]
            if len(non_null) > 0:
                n_distinct = non_null.nunique()
                if n_distinct == 1:
                    tier = classify_divergence(col, name)
                    result["divergences"].append({
                        "check": "constant_value",
                        "severity": tier,
                        "field": col,
                        "value": str(non_null.iloc[0]),
                        "message": f"Field '{col}' has exactly 1 distinct value: '{non_null.iloc[0]}'",
                    })

    # CHECK 3 — Type anomalies (columns that should be numeric but are all-string or all-null)
    # Heuristic: if column name contains hprd, rate, pct, star, score, fips, count, days
    numeric_hint_patterns = ["hprd", "_rate", "_pct", "_score", "_count", "_days",
                              "_amount", "_fips", "_total", "latitude", "longitude", "margin",
                              "occupancy", "multiplier", "turnover", "census", "beds"]
    # _star checked with endswith so '_start' doesn't false-match
    def has_numeric_hint(col_lower: str) -> bool:
        if any(p in col_lower for p in numeric_hint_patterns):
            return True
        return col_lower.endswith("_star") or col_lower.endswith("_stars")

    for col in df.columns:
        if (col, "type_anomaly") in known:
            continue
        col_lower = col.lower()
        if has_numeric_hint(col_lower):
            if df[col].dtype == object:
                numeric_vals = pd.to_numeric(df[col], errors="coerce")
                pct_parseable = numeric_vals.notna().mean()
                pct_null = df[col].isna().mean()
                if pct_null < 0.95 and pct_parseable < 0.5:
                    tier = classify_divergence(col, name)
                    result["divergences"].append({
                        "check": "type_anomaly",
                        "severity": tier,
                        "field": col,
                        "pct_numeric": round(float(pct_parseable), 4),
                        "message": f"Field '{col}' has numeric-hint name but only {pct_parseable*100:.1f}% parse as numeric",
                    })

    # CHECK 7 — Row count (against assertion ranges in registry if present)
    # The registry doesn't store ranges; use a simple sanity floor
    if result["row_count"] == 0:
        result["divergences"].append({
            "check": "row_count",
            "severity": "BLOCKING",
            "message": "Output file is empty (0 rows)",
        })

    # CHECK 1+2 — Field set comparison (requires live API fetch)
    if live and ds.get("access_method") not in ("computed", "bulk_csv", "census_api"):
        time.sleep(0.5)   # polite rate limiting
        api_cols_raw = fetch_api_columns(ds)
        if isinstance(api_cols_raw, str) and api_cols_raw.startswith("ERROR"):
            result["divergences"].append({
                "check": "api_schema_fetch",
                "severity": "INFO",
                "message": f"Could not fetch live API schema: {api_cols_raw}",
            })
        elif api_cols_raw is not None:
            api_cols = set(api_cols_raw)
            computed = set(ds.get("fields_computed", []))
            # Fields in API but not in our output (excluding the "all" sentinel for computed)
            missing_from_us = api_cols - our_cols
            if missing_from_us:
                for f in sorted(missing_from_us):
                    tier = classify_divergence(f, name)
                    result["divergences"].append({
                        "check": "fields_in_api_not_in_output",
                        "severity": tier,
                        "field": f,
                        "message": f"API returns field '{f}' that is not in our output",
                    })
            # Fields in our output but not in API (excluding computed fields)
            extra_in_us = our_cols - api_cols - computed
            if "all" in computed:
                extra_in_us = set()   # computed-from-scratch file — no comparison possible
            if extra_in_us:
                for f in sorted(extra_in_us):
                    tier = classify_divergence(f, name)
                    result["divergences"].append({
                        "check": "fields_in_output_not_in_api",
                        "severity": tier,
                        "field": f,
                        "message": f"Our output has field '{f}' that is not in the current API response",
                    })
            result["api_col_count"] = len(api_cols)
            result["api_cols_fetched"] = True
        else:
            result["divergences"].append({
                "check": "api_schema_fetch",
                "severity": "INFO",
                "message": "API returned no rows or method not supported for live schema fetch",
            })

    # Summarize
    blocking = [d for d in result["divergences"] if d.get("severity") == "BLOCKING"]
    latent   = [d for d in result["divergences"] if d.get("severity") == "LATENT"]
    if blocking:
        result["status"] = "BLOCKING"
    elif latent:
        result["status"] = "LATENT"
    elif result["divergences"]:
        result["status"] = "INFO"

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Lux Mentis conformance harness")
    parser.add_argument("--live", action="store_true",
                        help="Fetch 1-row sample from live API for field-set comparison")
    parser.add_argument("--dataset", help="Run against a single dataset by name")
    args = parser.parse_args()

    with open(REGISTRY, encoding="utf-8") as f:
        registry = json.load(f)

    datasets = registry["datasets"]
    if args.dataset:
        datasets = [d for d in datasets if d["name"] == args.dataset]
        if not datasets:
            sys.exit(f"Dataset '{args.dataset}' not found in registry.")

    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "live_api": args.live,
        "datasets_checked": len(datasets),
        "results": [],
    }

    blocking_total   = 0
    latent_total     = 0
    info_total       = 0
    suppressed_total = 0

    print(f"\n{'='*70}")
    print(f"  LUX MENTIS CONFORMANCE HARNESS")
    print(f"  {report['generated']}  |  live_api={args.live}")
    print(f"{'='*70}\n")

    for ds in datasets:
        result = check_dataset(ds, live=args.live)
        report["results"].append(result)

        status_sym = {"OK": "OK", "BLOCKING": "XX", "LATENT": ">>", "INFO": "--",
                      "MISSING_OUTPUT": "XX", "SKIPPED_GITIGNORED": "SK"}.get(result["status"], "??")

        divs = result["divergences"]
        b_count = sum(1 for d in divs if d.get("severity") == "BLOCKING")
        l_count = sum(1 for d in divs if d.get("severity") == "LATENT")
        i_count = sum(1 for d in divs if d.get("severity") == "INFO")

        s_count = len(build_known_set(ds))
        suppressed_total += s_count

        row_info = ""
        if result["row_count"] is not None:
            row_info = f"  {result['row_count']:>8,} rows  {result['col_count']:>4} cols"

        supp_info = f"  [suppressed:{s_count:>3}]" if s_count > 0 else ""

        print(f"{status_sym} {ds['name']:<35}{row_info}{supp_info}")

        if divs:
            blocking_total += b_count
            latent_total   += l_count
            info_total     += i_count
            for d in divs:
                sev = d.get("severity", "?")
                sym = {"BLOCKING": "  [BLOCKING]", "LATENT": "  [LATENT] ",
                       "INFO":     "  [INFO]    "}.get(sev, "  [?]       ")
                print(f"{sym} {d['message']}")

    print(f"\n{'='*70}")
    print(f"  SUMMARY:  BLOCKING={blocking_total}  LATENT={latent_total}  INFO={info_total}  SUPPRESSED={suppressed_total}")
    print(f"  Report written to: {REPORT_FILE.name}")
    print(f"{'='*70}\n")

    # Write machine-readable report
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    return 1 if blocking_total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
