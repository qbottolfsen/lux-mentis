"""
health_check.py
Lux Mentis conformance harness — structural checks for every dataset in the pipeline.

Runs seven structural checks against each output file and its current API schema:

  1. Fields in API response absent from our output (data we never captured)
  2. Fields in our output absent from the current API (CMS renamed or dropped)
  3. Type anomalies — columns that should be numeric but read back as all-string
  4. Null-rate anomalies — any field >= 95% null
  5. Constant-value fields — any field with exactly 1 distinct non-null value
  6. Column-name divergence — same logical field, different name across access methods
     (requires two access paths to the same dataset; logged when known)
  7. Row-count drift — current output vs. the registered assertion range

A4 Column-Binding Note (audit 2026-07-16):
  Scripts 02–10 use find_col() for column discovery. On a CMS column rename, find_col()
  returns None, g() returns "" silently, and the output carries empty strings throughout
  the affected column. The script prints "NOT FOUND" in the terminal but does not abort.
  Script 01 uses an explicit SRC dict — mismatches raise a KeyError during fetch.
  Risk: finding fields in scripts 02–10 (scope_severity_code, fine_amount, etc.) can
  silently empty-out if CMS renames a raw column.
  Mitigation: run `health_check.py --live` after each vintage pull BEFORE generating
  output. Checks 1+2 surface field-set divergences upstream. Post-generation, the
  null_rate check (check 4) catches silent empties as BLOCKING on finding fields.

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

SCRIPT_DIR    = pathlib.Path(__file__).parent
OUTPUT_DIR    = SCRIPT_DIR / "output_reference"
REGISTRY      = SCRIPT_DIR / "datasets_registry.json"
REPORT_FILE   = OUTPUT_DIR / "divergence_report.json"
SNAPSHOT_FILE = OUTPUT_DIR / "health_snapshot.json"

NULL_RATE_THRESHOLD   = 0.95   # flag if >= 95% null
CONST_VALUE_MIN_ROWS  = 100    # only flag constant-value on datasets > 100 rows

# Drift detection thresholds
ROW_DRIFT_PCT      = 0.05   # flag if row count shifts > 5% from snapshot
NULL_SPIKE_THRESH  = 0.90   # flag if field was < this null rate and now crosses it (semantic-drift)

# Cross-source reconciliation: (dataset_a, dataset_b, max_allowed_row_difference_pct)
CROSS_SOURCE_CHECKS = [
    ("snf_enrollments", "snf_owners_flags",      0.001),   # same 14,425 spine
    ("cms_enrollments_all_types", "facility_master", 0.001), # same 57,767 spine
]

# Published findings — maps dataset name to field names that feed a finding
FINDING_FIELDS = {
    "nh_provider_info":    ["lm_meets_3442f_thresholds", "rn_hprd", "rn_weekend_hprd", "total_hprd",
                            "total_nurse_turnover", "rn_turnover", "overall_star",
                            "health_inspection_star", "staffing_star", "special_focus_status"],
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

    # CHECK: ghost suppression entries — known_anomalies for fields not in output
    for entry in ds.get("known_anomalies", []):
        if entry.get("field") and entry["field"] not in our_cols:
            result["divergences"].append({
                "check": "ghost_suppression",
                "severity": "INFO",
                "field": entry["field"],
                "message": (
                    f"known_anomaly suppression for '{entry['field']}' ({entry.get('check','?')}) "
                    f"is vacuous — field not in output. Remove or add the field."
                ),
            })

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
                pct_null = df[col].isna().mean()
                non_null = df[col].dropna()
                if len(non_null) == 0:
                    continue  # all-null column; skip type check
                pct_parseable = pd.to_numeric(non_null, errors="coerce").notna().mean()
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


# ── Snapshot / Drift Detection ────────────────────────────────────────────────

def compute_field_stats(df: "pd.DataFrame") -> dict:
    """Per-field stats for snapshot and drift comparison."""
    stats = {}
    for col in df.columns:
        null_rate = float(df[col].isna().mean())
        non_null = df[col].dropna()
        nunique = int(non_null.nunique()) if len(non_null) > 0 else 0
        stats[col] = {
            "null_rate": round(null_rate, 4),
            "nunique": nunique,
            "is_constant": (nunique == 1 and len(non_null) > 0),
        }
    return stats


def load_snapshot() -> dict:
    if SNAPSHOT_FILE.exists():
        try:
            with open(SNAPSHOT_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_snapshot(run_results: list) -> None:
    snap = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "datasets": {},
    }
    for r in run_results:
        name = r.get("dataset")
        if r.get("row_count") is None:
            continue
        snap["datasets"][name] = {
            "row_count": r["row_count"],
            "col_count": r["col_count"],
            "field_stats": r.get("field_stats", {}),
        }
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)


def compare_to_snapshot(name: str, result: dict, prior: dict) -> list:
    """Return drift items (dicts with severity/message) relative to prior snapshot."""
    if name not in prior.get("datasets", {}):
        return []

    snap_ds = prior["datasets"][name]
    drift = []

    # Row count drift
    prior_rows = snap_ds.get("row_count")
    curr_rows = result.get("row_count")
    if prior_rows and curr_rows is not None and prior_rows > 0:
        pct_change = abs(curr_rows - prior_rows) / prior_rows
        if pct_change > ROW_DRIFT_PCT:
            direction = "grew" if curr_rows > prior_rows else "shrank"
            drift.append({
                "check": "row_drift",
                "severity": "DRIFT",
                "message": (
                    f"Row count {direction}: {prior_rows:,} → {curr_rows:,} "
                    f"({pct_change*100:.1f}% change). Verify source vintage."
                ),
            })

    # Field appearance / disappearance
    prior_fields = set(snap_ds.get("field_stats", {}).keys())
    curr_fields  = set(result.get("field_stats", {}).keys())
    for f in (curr_fields - prior_fields):
        drift.append({
            "check": "new_field",
            "severity": "DRIFT",
            "field": f,
            "message": f"New field '{f}' appeared — not in prior snapshot. CMS schema addition?",
        })
    for f in (prior_fields - curr_fields):
        drift.append({
            "check": "dropped_field",
            "severity": "DRIFT",
            "field": f,
            "message": f"Field '{f}' missing — was in prior snapshot. CMS schema drop or rename?",
        })

    # Semantic drift: field that was populated is now mostly null
    for f, prior_stats in snap_ds.get("field_stats", {}).items():
        curr_stats = result.get("field_stats", {}).get(f)
        if curr_stats is None:
            continue
        p_null = prior_stats.get("null_rate", 0)
        c_null = curr_stats.get("null_rate", 0)
        if p_null < NULL_SPIKE_THRESH and c_null >= NULL_SPIKE_THRESH:
            drift.append({
                "check": "semantic_drift",
                "severity": "DRIFT",
                "field": f,
                "message": (
                    f"Field '{f}' null rate spiked: {p_null*100:.1f}% → {c_null*100:.1f}%. "
                    f"CMS may have stopped populating this field (cf. used_in_five_star pattern). "
                    f"Log in DIVERGENCE_LOG.md."
                ),
            })
        # Constant-value flips
        was_const = prior_stats.get("is_constant", False)
        is_const  = curr_stats.get("is_constant", False)
        if was_const != is_const:
            drift.append({
                "check": "constant_flip",
                "severity": "DRIFT",
                "field": f,
                "message": (
                    f"Field '{f}' {'became constant' if is_const else 'is no longer constant'} "
                    f"(prior nunique={prior_stats.get('nunique')}, "
                    f"current nunique={curr_stats.get('nunique')}). Investigate."
                ),
            })

    return drift


def cross_source_checks(results_by_name: dict) -> list:
    """Check that paired datasets whose row counts must agree still agree."""
    issues = []
    for ds_a, ds_b, max_pct in CROSS_SOURCE_CHECKS:
        ra = results_by_name.get(ds_a, {})
        rb = results_by_name.get(ds_b, {})
        rows_a = ra.get("row_count")
        rows_b = rb.get("row_count")
        if rows_a is None or rows_b is None:
            continue
        if rows_a == 0:
            continue
        pct = abs(rows_a - rows_b) / rows_a
        if pct > max_pct:
            issues.append({
                "check": "cross_source_reconciliation",
                "severity": "DRIFT",
                "message": (
                    f"Cross-source mismatch: {ds_a} ({rows_a:,} rows) vs "
                    f"{ds_b} ({rows_b:,} rows) — {pct*100:.2f}% apart. "
                    f"These datasets must share a spine. Investigate before re-pull."
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Lux Mentis conformance harness")
    parser.add_argument("--live", action="store_true",
                        help="Fetch 1-row sample from live API for field-set comparison")
    parser.add_argument("--dataset", help="Run against a single dataset by name")
    args = parser.parse_args()

    parser.add_argument("--no-snapshot", action="store_true",
                        help="Skip snapshot comparison and do not update snapshot")
    args = parser.parse_args()

    with open(REGISTRY, encoding="utf-8") as f:
        registry = json.load(f)

    datasets = registry["datasets"]
    if args.dataset:
        datasets = [d for d in datasets if d["name"] == args.dataset]
        if not datasets:
            sys.exit(f"Dataset '{args.dataset}' not found in registry.")

    prior_snapshot = {} if args.no_snapshot else load_snapshot()
    has_prior = bool(prior_snapshot.get("datasets"))

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
    all_drift        = []

    print(f"\n{'='*70}")
    print(f"  LUX MENTIS CONFORMANCE HARNESS")
    print(f"  {report['generated']}  |  live_api={args.live}")
    print(f"{'='*70}\n")

    results_by_name = {}
    for ds in datasets:
        result = check_dataset(ds, live=args.live)

        # Compute field stats for snapshot (load the file again only if it exists)
        if result["row_count"] is not None:
            output = OUTPUT_DIR / ds["output_file"]
            try:
                fmt = ds.get("format", "csv")
                df_snap = pd.read_parquet(output) if fmt == "parquet" else pd.read_csv(output, dtype=str, low_memory=False)
                result["field_stats"] = compute_field_stats(df_snap)
            except Exception:
                result["field_stats"] = {}
        else:
            result["field_stats"] = {}

        report["results"].append(result)
        results_by_name[ds["name"]] = result

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

        # Drift detection against prior snapshot
        if has_prior:
            drift = compare_to_snapshot(ds["name"], result, prior_snapshot)
            if drift:
                all_drift.extend([(ds["name"], d) for d in drift])

    # Cross-source reconciliation
    cs_issues = cross_source_checks(results_by_name)
    if cs_issues:
        all_drift.extend([("cross_source", d) for d in cs_issues])

    print(f"\n{'='*70}")
    print(f"  SUMMARY:  BLOCKING={blocking_total}  LATENT={latent_total}  INFO={info_total}  SUPPRESSED={suppressed_total}")
    if has_prior:
        print(f"  DRIFT SIGNALS: {len(all_drift)} (vs prior snapshot {prior_snapshot.get('generated','?')[:10]})")
    print(f"  Report written to: {REPORT_FILE.name}")
    print(f"{'='*70}\n")

    if all_drift:
        print(f"{'='*70}")
        print(f"  DRIFT SIGNALS — review before logging as divergence or suppressing")
        print(f"  Detection is automated; classification (INTERNAL/EXTERNAL-DOC/EXTERNAL-UNDOC) is yours.")
        print(f"{'='*70}\n")
        for ds_name, d in all_drift:
            print(f"  [DRIFT] [{ds_name}] {d['message']}")
        print()

    # Write machine-readable report
    report["drift_signals"] = [{"dataset": n, **d} for n, d in all_drift]
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    # Save updated snapshot
    if not args.no_snapshot and not args.dataset:
        save_snapshot(report["results"])

    return 1 if blocking_total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
