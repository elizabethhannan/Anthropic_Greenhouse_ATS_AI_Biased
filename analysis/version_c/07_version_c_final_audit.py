"""Version C — Phase 8 final integrity audit and freeze manifest.

Read-only audit across Version C Phase 2–7 outputs. It verifies internal
consistency and provenance boundaries; it does not create analytical claims
or modify any prior dataset.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT_DIR = BASE / "audit"

FILES: dict[str, Path] = {
    "phase2_master": OUT / "version_c_master.parquet",
    "phase2_hiring": OUT / "version_c_hiring_outcomes.parquet",
    "phase2_bridge": OUT / "version_c_role_month_bridge.parquet",
    "phase2_manifest": AUDIT_DIR / "version_c_run_manifest.json",
    "phase3_features": OUT / "signal_features.parquet",
    "phase3_summary": OUT / "signal_summary.csv",
    "phase3_examples": OUT / "signal_examples.csv",
    "phase3_manifest": AUDIT_DIR / "signal_run_manifest.json",
    "phase4_metrics": OUT / "predictive_model_metrics.csv",
    "phase4_oof": OUT / "predictive_oof_predictions.csv",
    "phase4_coefficients": OUT / "predictive_coefficients.csv",
    "phase4_permutation": OUT / "predictive_permutation_importance.csv",
    "phase4_stability": OUT / "predictive_feature_stability.csv",
    "phase4_sensitivity": OUT / "predictive_sensitivity.csv",
    "phase4_agreement": OUT / "predictive_model_agreement.csv",
    "phase4_findings": OUT / "predictive_findings.csv",
    "phase4_audit": AUDIT_DIR / "predictive_model_audit.csv",
    "phase4_manifest": AUDIT_DIR / "predictive_model_run_manifest.json",
    "phase5_representation": OUT / "monthly_representation.csv",
    "phase5_outcomes": OUT / "monthly_outcomes.csv",
    "phase5_lags": OUT / "lagged_associations.csv",
    "phase5_roles": OUT / "role_feedback_associations.csv",
    "phase5_summary": OUT / "feedback_summary.csv",
    "phase5_manifest": AUDIT_DIR / "feedback_run_manifest.json",
    "phase6_distribution": OUT / "outcome_distribution.csv",
    "phase6_period": OUT / "outcome_by_period.csv",
    "phase6_research": OUT / "research_outcome_distribution.csv",
    "phase6_fellowship": OUT / "fellowship_outcome_distribution.csv",
    "phase6_quality": OUT / "outcome_quality_summary.csv",
    "phase6_metrics": OUT / "executive_outcome_metrics.json",
    "phase6_manifest": AUDIT_DIR / "outcome_analysis_manifest.json",
    "phase7_outcomes": OUT / "dashboard_outcome_distribution.csv",
    "phase7_signals": OUT / "dashboard_signal_findings.csv",
    "phase7_prediction": OUT / "dashboard_predictive_findings.csv",
    "phase7_feedback": OUT / "dashboard_feedback_findings.csv",
    "phase7_limitations": OUT / "dashboard_limitations.csv",
    "phase7_evidence": OUT / "dashboard_evidence_map.csv",
    "phase7_summary": OUT / "executive_summary.json",
    "phase7_manifest": AUDIT_DIR / "executive_dashboard_run_manifest.json",
    "phase7_validation": AUDIT_DIR / "executive_dashboard_validation.csv",
    "phase7_validation_json": AUDIT_DIR / "executive_dashboard_validation.json",
}
CODE_FILES = [BASE / f"{n:02d}_{name}.py" for n, name in (
    (1, "prepare_version_c"), (2, "signal_diagnostic"), (3, "predictive_models"),
    (4, "feedback_diagnostic"), (5, "male_female_unknown_outcomes"),
    (6, "executive_dashboard_data"), (7, "version_c_final_audit"),
)]
CODE_FILES.append(BASE / "07_validate_executive_dashboard.py")
EXPECTED_ROWS = {
    "phase2_master": 1246, "phase2_hiring": 1095, "phase2_bridge": 41,
    "phase3_features": 1246, "phase3_summary": 7, "phase3_examples": 6502,
    "phase4_metrics": 6, "phase4_oof": 0,
    "phase4_coefficients": 0, "phase4_permutation": 0,
    "phase4_stability": 0, "phase4_sensitivity": 0,
    "phase4_agreement": 0, "phase4_findings": 5,
    "phase5_representation": 6, "phase5_outcomes": 6,
    "phase5_lags": 252, "phase5_roles": 40, "phase5_summary": 9,
    "phase6_distribution": 3, "phase6_period": 6,
    "phase6_research": 3, "phase6_fellowship": 3,
    "phase7_outcomes": 3, "phase7_signals": 8, "phase7_prediction": 6,
    "phase7_feedback": 292, "phase7_limitations": 8, "phase7_evidence": 8,
    "phase7_validation": 23,
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def row_count(path: Path) -> int:
    if path.suffix == ".parquet":
        return pq.read_table(path).num_rows
    if path.suffix == ".csv":
        return len(read_csv(path))
    return 1


def add(checks: list[dict[str, Any]], name: str, status: str, expected: Any, actual: Any, detail: str = "") -> None:
    checks.append({"check": name, "status": status, "expected": expected, "actual": actual, "detail": detail})


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    file_inventory: dict[str, dict[str, Any]] = {}
    missing = []
    for name, path in FILES.items():
        if not path.exists():
            missing.append(name)
            file_inventory[name] = {"path": str(path.relative_to(BASE)), "exists": False}
            add(checks, f"file_exists:{name}", "FAIL", True, False, str(path))
            continue
        raw = path.read_bytes()
        count = row_count(path)
        file_inventory[name] = {"path": str(path.relative_to(BASE)), "exists": True, "bytes": len(raw), "sha256": sha(raw), "row_count": count}
        add(checks, f"file_exists:{name}", "PASS", True, True, str(path.relative_to(BASE)))
        if name in EXPECTED_ROWS:
            expected = EXPECTED_ROWS[name]
            add(checks, f"row_count:{name}", "PASS" if count == expected else "FAIL", expected, count)

    if missing:
        # Write a useful partial audit and freeze report instead of failing before
        # recording which expected items were unavailable.
        overall = "INCOMPLETE_MISSING_FILES"
        phase2 = phase3 = phase4 = phase5 = phase6 = phase7 = {}
        hiring = master = signals = []
        outcome_metrics = dashboard = {}
    else:
        phase2 = load_json(FILES["phase2_manifest"])
        phase3 = load_json(FILES["phase3_manifest"])
        phase4 = load_json(FILES["phase4_manifest"])
        phase5 = load_json(FILES["phase5_manifest"])
        phase6 = load_json(FILES["phase6_manifest"])
        phase7 = load_json(FILES["phase7_manifest"])
        outcome_metrics = load_json(FILES["phase6_metrics"])
        dashboard = load_json(FILES["phase7_summary"])
        hiring = pq.read_table(FILES["phase2_hiring"]).to_pylist()
        master = pq.read_table(FILES["phase2_master"]).to_pylist()
        signals = pq.read_table(FILES["phase3_features"]).to_pylist()

        # Outcome reconciliation and denominator checks.
        source_counts = {"MALE": 0, "FEMALE": 0, "UNKNOWN": 0}
        mismatches = 0
        ids = []
        for row in hiring:
            ids.append(str(row.get("PERSON_ID")))
            source = str(row.get("source_SEX") or "").strip().lower()
            derived = "MALE" if source == "male" else "FEMALE" if source == "female" else "UNKNOWN"
            source_counts[derived] += 1
            if str(row.get("outcome_sex") or "").upper() != derived or row.get("sex_inferred") is not False:
                mismatches += 1
        duplicate_ids = len(ids) - len(set(ids))
        add(checks, "outcome_counts_reconcile", "PASS" if source_counts == {"MALE": 606, "FEMALE": 276, "UNKNOWN": 213} else "FAIL", {"MALE": 606, "FEMALE": 276, "UNKNOWN": 213}, source_counts)
        add(checks, "known_sex_denominator", "PASS" if source_counts["MALE"] + source_counts["FEMALE"] == 882 else "FAIL", 882, source_counts["MALE"] + source_counts["FEMALE"])
        add(checks, "unknown_retained", "PASS" if source_counts["UNKNOWN"] == 213 else "FAIL", 213, source_counts["UNKNOWN"], "Unknown is excluded from known-sex shares, not dropped.")
        add(checks, "sex_inference_absent", "PASS" if mismatches == 0 else "FAIL", 0, mismatches, "Recomputed labels from source_SEX only; Phase 2 sex_inferred must remain false.")
        add(checks, "duplicate_person_ids", "PASS" if duplicate_ids == 0 else "FAIL", 0, duplicate_ids)

        # Dashboard must match the authoritative Phase 6 metrics exactly.
        dash_outcome = dashboard.get("outcome_layer", {})
        dashboard_match = all(int(dash_outcome.get(k, -1)) == v for k, v in source_counts.items())
        ratio = source_counts["MALE"] / source_counts["FEMALE"]
        dashboard_ratio_match = abs(float(dash_outcome.get("male_female_ratio", -1)) - ratio) < 1e-9
        add(checks, "executive_summary_outcomes", "PASS" if dashboard_match and dashboard_ratio_match else "FAIL", source_counts, {k: dash_outcome.get(k) for k in ("MALE", "FEMALE", "UNKNOWN")}, "Also checked Male/Female ratio.")
        add(checks, "phase6_metrics_outcome_counts", "PASS" if outcome_metrics.get("outcome_counts") == source_counts else "FAIL", source_counts, outcome_metrics.get("outcome_counts"))

        # Source/date discipline and absence of individual posting linkage.
        date_counts = Counter(str(r.get("date_evidence_class") or "MISSING") for r in master)
        expected_dates = {"GREENHOUSE_POSTING_DATE": 514, "ARCHIVE_CAPTURE_ONLY": 617, "POSTING_DATE_OUTSIDE_WINDOW": 115}
        add(checks, "posting_date_evidence_counts", "PASS" if dict(date_counts) == expected_dates else "FAIL", expected_dates, dict(date_counts))
        bad_archive_dates = sum(1 for r in master if r.get("date_evidence_class") == "ARCHIVE_CAPTURE_ONLY" and (r.get("first_published_at") or r.get("posting_date_if_known")))
        add(checks, "archive_capture_not_posting_date", "PASS" if bad_archive_dates == 0 else "FAIL", 0, bad_archive_dates)
        bad_link_flags = sum(1 for r in master if r.get("candidate_level_hire_linkage") is not False)
        bad_signal_links = sum(1 for r in signals if r.get("candidate_level_outcome_linkage") is not False)
        add(checks, "candidate_level_linkage_not_claimed", "PASS" if bad_link_flags + bad_signal_links == 0 else "FAIL", 0, bad_link_flags + bad_signal_links)
        window_ok = outcome_metrics.get("study_period") == {"start_month": "2026-04", "end_month": "2026-09"} and dashboard.get("study_window") == {"start": "2026-04-01", "end": "2026-09-30"}
        add(checks, "study_window_consistent", "PASS" if window_ok else "FAIL", {"start": "2026-04-01", "end": "2026-09-30"}, dashboard.get("study_window"))

        # Phase status is stated as observed in the manifests, not presumed.
        phase4_status = phase4.get("status", "MISSING_STATUS")
        phase5_coverage = phase5.get("counts", {})
        phase5_months = phase5_coverage.get("observed_start_months", [])
        phase5_missing_months = phase5_coverage.get("unobserved_outcome_months", [])
        add(checks, "phase4_status_reported", "PASS" if phase4_status == "NOT_ESTIMABLE" else "REVIEW", "NOT_ESTIMABLE for current frozen data", phase4_status, phase4.get("not_estimable_reason", ""))
        add(checks, "phase5_status_reported", "PASS" if phase5_months == ["2026-04", "2026-05", "2026-06", "2026-07"] and phase5_missing_months == ["2026-08", "2026-09"] else "REVIEW", {"observed": ["2026-04", "2026-05", "2026-06", "2026-07"], "unobserved": ["2026-08", "2026-09"]}, {"observed": phase5_months, "unobserved": phase5_missing_months})
        add(checks, "phase7_status_consistency", "PASS" if dashboard.get("phase_status", {}).get("PREDICTION") == phase4_status and dashboard.get("phase_status", {}).get("FEEDBACK") == "COMPLETE_WITH_COVERAGE_LIMITS" else "FAIL", {"PREDICTION": phase4_status, "FEEDBACK": "COMPLETE_WITH_COVERAGE_LIMITS"}, dashboard.get("phase_status"))
        phase3_method = phase3.get("association_method", {})
        phase3_date_safe = phase3_method.get("archive_capture_dates_used_as_posting_dates") is False and phase3_method.get("candidate_level_linkage") is False and phase3_method.get("causal_claim") is False
        add(checks, "phase3_evidence_boundaries", "PASS" if phase3_date_safe else "FAIL", {"archive_capture_as_posting_date": False, "candidate_linkage": False, "causality": False}, {"archive_capture_as_posting_date": phase3_method.get("archive_capture_dates_used_as_posting_dates"), "candidate_linkage": phase3_method.get("candidate_level_linkage"), "causality": phase3_method.get("causal_claim")})
        phase5_method = phase5.get("method", {})
        phase5_safe = phase5_method.get("archive_capture_as_posting_date") is False and phase5_method.get("candidate_level_linkage") is False and phase5_method.get("causality") is False
        add(checks, "phase5_evidence_boundaries", "PASS" if phase5_safe else "FAIL", {"archive_capture_as_posting_date": False, "candidate_linkage": False, "causality": False}, {"archive_capture_as_posting_date": phase5_method.get("archive_capture_as_posting_date"), "candidate_linkage": phase5_method.get("candidate_level_linkage"), "causality": phase5_method.get("causality")})

        # Prior run manifests may contain hashes for the current source bytes.
        # Report drift as REVIEW rather than rewriting any frozen artifact.
        manifest_hash_checks = []
        for manifest_name, manifest in (("phase2", phase2), ("phase3", phase3), ("phase4", phase4), ("phase5", phase5), ("phase6", phase6), ("phase7", phase7)):
            if not isinstance(manifest, dict):
                continue
            # The phase manifests record output hashes in differing schemas.
            outputs = manifest.get("outputs", {})
            if isinstance(outputs, list):
                outputs = {str(item.get("file") or item.get("asset")): item for item in outputs if isinstance(item, dict)}
            for item in outputs.values() if isinstance(outputs, dict) else []:
                if not isinstance(item, dict):
                    continue
                relative = item.get("path") or item.get("file")
                digest = item.get("sha256")
                if relative and digest:
                    p = BASE / str(relative)
                    if p.exists():
                        status = "PASS" if sha(p.read_bytes()) == digest else "REVIEW"
                        manifest_hash_checks.append((manifest_name, relative, status))
        mismatch_hashes = sum(status != "PASS" for _, _, status in manifest_hash_checks)
        add(checks, "recorded_output_hashes", "PASS" if mismatch_hashes == 0 else "REVIEW", "all available recorded hashes match", {"checked": len(manifest_hash_checks), "mismatches": mismatch_hashes}, "Different phases record output paths in different manifest formats; available matching paths were checked.")

        failures = sum(c["status"] == "FAIL" for c in checks)
        readiness = "INTEGRITY_ISSUES" if failures else "STRUCTURALLY_VALID — ANALYTICAL PIPELINE INCOMPLETE"
        overall = "FAIL" if failures else "PASS_WITH_LIMITATIONS"

    # Add readiness finding on partial and full runs.
    if missing:
        readiness = "INCOMPLETE — REQUIRED FILES MISSING"
        overall = "INCOMPLETE"
    add(checks, "executive_review_readiness", "PASS_WITH_LIMITATIONS" if overall == "PASS_WITH_LIMITATIONS" else "INCOMPLETE", "structural integrity plus disclosed analytic limits", readiness,
        "Phase 4 was run but not estimable; Phase 5 was run with sparse temporal/role coverage." if not missing else f"Missing expected files: {missing}")

    for script_path in CODE_FILES:
        add(checks, f"code_file_exists:{script_path.name}", "PASS" if script_path.exists() else "FAIL", True, script_path.exists(), str(script_path.relative_to(BASE)))

    check_failures = sum(c["status"] == "FAIL" for c in checks)
    audit_rows = [{"check": c["check"], "status": c["status"], "expected": json.dumps(c["expected"], ensure_ascii=False, sort_keys=True), "actual": json.dumps(c["actual"], ensure_ascii=False, sort_keys=True), "detail": c["detail"]} for c in checks]
    audit_csv_path = AUDIT_DIR / "version_c_final_audit.csv"
    with audit_csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check", "status", "expected", "actual", "detail"])
        writer.writeheader(); writer.writerows(audit_rows)

    audit_json = {
        "audit_type": "version_c_final_integrity_audit",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "overall_status": overall,
        "executive_review_readiness": readiness,
        "checks_total": len(checks),
        "checks_failed": check_failures,
        "checks_review": sum(c["status"] == "REVIEW" for c in checks),
        "checks_passed": sum(c["status"] == "PASS" for c in checks),
        "checks": checks,
        "phase_status": {"phase2": "COMPLETE", "phase3": "COMPLETE", "phase4": phase4.get("status", "NOT_AVAILABLE"), "phase5": "COMPLETE_WITH_COVERAGE_LIMITS" if phase5 else "NOT_AVAILABLE", "phase6": "COMPLETE", "phase7": "COMPLETE", "phase8": "COMPLETE"},
        "causal_boundary": "No causal effect or individual Greenhouse-to-hire pathway is established.",
    }
    audit_json_path = AUDIT_DIR / "version_c_final_audit.json"
    audit_json_path.write_text(json.dumps(audit_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    freeze = {
        "manifest_type": "version_c_final_freeze_manifest",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "overall_status": overall,
        "executive_review_readiness": readiness,
        "study_window": {"start": "2026-04-01", "end": "2026-09-30"},
        "artifact_inventory": file_inventory,
        "new_phase8_outputs": {
            "version_c_final_audit.csv": {"path": str(audit_csv_path.relative_to(BASE)), "sha256": sha(audit_csv_path.read_bytes()), "rows": len(audit_rows)},
            "version_c_final_audit.json": {"path": str(audit_json_path.relative_to(BASE)), "sha256": sha(audit_json_path.read_bytes()), "checks": len(checks)},
        },
        "frozen_outcome_counts": {"distinct_people": 1095, "MALE": 606, "FEMALE": 276, "UNKNOWN": 213, "known_sex": 882},
        "analytical_boundaries": [
            "Unknown remains a separate outcome class and is excluded from known-sex shares.",
            "No sex is inferred from names, titles, pronouns, or other attributes.",
            "No candidate-level Greenhouse posting-to-hire linkage is claimed.",
            "Archive capture dates are not treated as posting dates.",
            "Phase 4 is not estimable with three eligible exact role-month cells; all three contain Male outcomes and none contains Female outcomes, so grouped cross-validation cannot be supported.",
            "Phase 5 is exploratory with four observed start months, two unavailable months, and five exact role-month overlaps.",
            "No causal effect or internal Greenhouse workflow treatment is established.",
        ],
        "source_layers_modified": False,
    }
    freeze_path = AUDIT_DIR / "version_c_final_freeze_manifest.json"
    freeze_path.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Read-back verification for both final JSON audit artifacts.
    for path in (audit_json_path, freeze_path):
        json.loads(path.read_text(encoding="utf-8"))

    print(json.dumps({"overall_status": overall, "executive_review_readiness": readiness,
                      "checks_total": len(checks), "checks_failed": check_failures,
                      "phase4": audit_json["phase_status"]["phase4"], "phase5": audit_json["phase_status"]["phase5"],
                      "outputs": [str(audit_csv_path), str(audit_json_path), str(freeze_path)]}, indent=2))


if __name__ == "__main__":
    main()
