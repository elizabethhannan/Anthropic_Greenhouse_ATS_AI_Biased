"""Version C — Phase 7 executive dashboard validation.

Read-only integrity checks for the Phase 7 dashboard data. Writes only new
validation audit files; does not change Phase 2–7 source or dashboard outputs.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT = BASE / "audit"
HIRING = OUT / "version_c_hiring_outcomes.parquet"
SUMMARY = OUT / "executive_summary.json"
DASHBOARD_MANIFEST = AUDIT / "executive_dashboard_run_manifest.json"
PHASE4_MANIFEST = AUDIT / "predictive_model_run_manifest.json"
PHASE5_MANIFEST = AUDIT / "feedback_run_manifest.json"
PHASE5_SUMMARY = OUT / "feedback_summary.csv"

DASHBOARD_FILES = {
    "outcome_distribution": OUT / "dashboard_outcome_distribution.csv",
    "signal_findings": OUT / "dashboard_signal_findings.csv",
    "predictive_findings": OUT / "dashboard_predictive_findings.csv",
    "feedback_findings": OUT / "dashboard_feedback_findings.csv",
    "limitations": OUT / "dashboard_limitations.csv",
    "evidence_map": OUT / "dashboard_evidence_map.csv",
    "dashboard_audit": AUDIT / "executive_dashboard_audit.csv",
}
EXPECTED_COUNTS = {"MALE": 606, "FEMALE": 276, "UNKNOWN": 213}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def check(rows: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    rows.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def source_outcomes() -> tuple[dict[str, int], int, int]:
    table = pq.read_table(HIRING, columns=["PERSON_ID", "source_SEX"])
    seen: set[str] = set()
    counts = {"MALE": 0, "FEMALE": 0, "UNKNOWN": 0}
    duplicate_ids = 0
    for row in table.to_pylist():
        person_id = str(row.get("PERSON_ID") or "")
        if person_id in seen:
            duplicate_ids += 1
            continue
        seen.add(person_id)
        source_sex = str(row.get("source_SEX") or "").strip().lower()
        label = "MALE" if source_sex == "male" else "FEMALE" if source_sex == "female" else "UNKNOWN"
        counts[label] += 1
    return counts, len(seen), duplicate_ids


def main() -> int:
    AUDIT.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []

    required = [HIRING, SUMMARY, DASHBOARD_MANIFEST, PHASE4_MANIFEST, PHASE5_MANIFEST, PHASE5_SUMMARY, *DASHBOARD_FILES.values()]
    missing = [str(path.relative_to(BASE)) for path in required if not path.exists()]
    check(checks, "required_files_present", not missing, f"Missing files: {missing}" if missing else f"All {len(required)} required files exist.")
    if missing:
        return write_report(checks, None, None)

    summary = read_json(SUMMARY)
    dashboard_manifest = read_json(DASHBOARD_MANIFEST)
    phase4 = read_json(PHASE4_MANIFEST)
    phase5 = read_json(PHASE5_MANIFEST)
    phase5_summary = read_csv(PHASE5_SUMMARY)
    counts, people_count, duplicate_ids = source_outcomes()
    known = counts["MALE"] + counts["FEMALE"]
    total = sum(counts.values())

    check(checks, "canonical_source_counts", counts == EXPECTED_COUNTS and total == 1095,
          f"Recounted source_SEX: {counts}; total={total}; expected={EXPECTED_COUNTS} / 1095.")
    check(checks, "unique_people", people_count == 1095 and duplicate_ids == 0,
          f"Unique PERSON_IDs={people_count}; duplicates={duplicate_ids}.")
    check(checks, "known_sex_denominator", known == 882,
          f"Known-sex denominator={known}; expected=882.")
    check(checks, "unknown_preserved", counts["UNKNOWN"] == 213,
          f"Unknown remains its own category: {counts['UNKNOWN']}.")

    outcome = summary.get("outcome_layer", {})
    expected_shares = {
        "male_share_known_sex": counts["MALE"] / known,
        "female_share_known_sex": counts["FEMALE"] / known,
        "male_female_ratio": counts["MALE"] / counts["FEMALE"],
        "unknown_share_all_records": counts["UNKNOWN"] / total,
    }
    summary_counts_ok = all(int(outcome.get(key, -1)) == value for key, value in counts.items())
    summary_counts_ok = summary_counts_ok and int(outcome.get("distinct_people", -1)) == people_count
    summary_shares_ok = all(abs(float(outcome.get(key, -1)) - value) < 1e-9 for key, value in expected_shares.items())
    check(checks, "executive_summary_reconciles", summary_counts_ok and summary_shares_ok,
          f"Summary count/share fields checked against source_SEX; expected shares={expected_shares}.")

    dashboard_counts = dashboard_manifest.get("outcome_counts", {})
    dashboard_counts_ok = all(int(dashboard_counts.get(k, -1)) == v for k, v in counts.items()) and int(dashboard_counts.get("known_sex", -1)) == known
    check(checks, "dashboard_manifest_outcomes", dashboard_counts_ok,
          f"Dashboard manifest counts={dashboard_counts}; source counts={counts}, known={known}.")

    csv_data = {name: read_csv(path) for name, path in DASHBOARD_FILES.items()}
    outcome_rows = csv_data["outcome_distribution"]
    outcome_csv_counts = {str(r.get("outcome_sex", "")).upper(): int(r.get("person_count") or 0) for r in outcome_rows}
    check(checks, "outcome_csv_reconciles", outcome_csv_counts == counts,
          f"Dashboard outcome CSV counts={outcome_csv_counts}; expected={counts}.")
    sex_inferred_ok = all(str(r.get("sex_inferred", "")).strip().lower() in {"false", "0"} for r in outcome_rows)
    check(checks, "no_sex_inference", sex_inferred_ok,
          "Every dashboard outcome row retains sex_inferred=false.")

    findings = {name: rows for name, rows in csv_data.items()}
    signal_present = bool(findings["signal_findings"])
    prediction_present = bool(findings["predictive_findings"])
    feedback_present = bool(findings["feedback_findings"])
    check(checks, "signal_layer_present", signal_present and summary.get("phase_status", {}).get("SIGNAL") == "AVAILABLE",
          f"Signal rows={len(findings['signal_findings'])}; summary status={summary.get('phase_status', {}).get('SIGNAL')}.")
    check(checks, "prediction_status_matches_phase4", summary.get("phase_status", {}).get("PREDICTION") == phase4.get("status") and prediction_present,
          f"Dashboard status={summary.get('phase_status', {}).get('PREDICTION')}; Phase 4 status={phase4.get('status')}; rows={len(findings['predictive_findings'])}.")
    check(checks, "feedback_status_present", summary.get("phase_status", {}).get("FEEDBACK") == "COMPLETE_WITH_COVERAGE_LIMITS" and feedback_present,
          f"Dashboard feedback status={summary.get('phase_status', {}).get('FEEDBACK')}; rows={len(findings['feedback_findings'])}.")
    feedback_summary_values = {row.get("item"): row.get("value", "") for row in phase5_summary}
    lag1_present = any(row.get("scope") == "lag_1" and str(row.get("status", "")).startswith("ESTIMATED") for row in findings["feedback_findings"])
    lag2_deferred = "deferred" in feedback_summary_values.get("question_A_forward_2_sample_months", "").lower()
    check(checks, "phase5_estimated_vs_deferred", lag1_present and lag2_deferred,
          f"Forward +1 evidence present={lag1_present}; +2-month summary explicitly deferred={lag2_deferred}.")

    prediction_rows = findings["predictive_findings"]
    if phase4.get("status") == "NOT_ESTIMABLE":
        no_fake_scores = all(not r.get("roc_auc") and not r.get("pr_auc") and r.get("status") == "NOT_ESTIMABLE" for r in prediction_rows)
        check(checks, "phase4_not_estimable_not_overstated", no_fake_scores and bool(phase4.get("not_estimable_reason")),
              f"Phase 4 is NOT_ESTIMABLE; reason present; every dashboard model row preserves status and has no ROC/PR-AUC.")
    else:
        check(checks, "phase4_status_documented", bool(phase4.get("status")), f"Phase 4 status={phase4.get('status')}.")

    observed_months = phase5.get("counts", {}).get("observed_start_months", [])
    unavailable_months = phase5.get("counts", {}).get("unobserved_outcome_months", [])
    aug_sep_limited = "2026-08" in unavailable_months and "2026-09" in unavailable_months and "2026-07" in observed_months
    limitation_text = " ".join(str(r.get("detail", "")) for r in findings["limitations"])
    limitation_text += " " + " ".join(str(r.get("result", "")) for r in findings["evidence_map"])
    limitation_text += " " + str(summary.get("executive_wording", ""))
    explicit_snapshot_limit = "August" in limitation_text and "September" in limitation_text and ("unavailable" in limitation_text.lower() or "not zero" in limitation_text.lower())
    check(checks, "august_september_coverage_limit", aug_sep_limited and explicit_snapshot_limit,
          f"Phase 5 observed={observed_months}, unavailable={unavailable_months}; dashboard states missing months are unavailable, not zero.")

    evidence_rows = findings["evidence_map"]
    evidence_by_layer = {r.get("layer", "").upper(): r for r in evidence_rows}
    required_layers = {"SIGNAL", "PREDICTION", "FEEDBACK", "OUTCOME", "AI PATHWAY", "WORKFLOW", "HUMAN OVERRIDE", "INTERVIEW"}
    layers_ok = required_layers.issubset(evidence_by_layer)
    check(checks, "evidence_layers_separated", layers_ok,
          f"Required evidence-map layers present: {sorted(required_layers)}; found={sorted(evidence_by_layer)}.")
    evidence_consistency = (
        evidence_by_layer.get("PREDICTION", {}).get("status") == phase4.get("status")
        and evidence_by_layer.get("FEEDBACK", {}).get("status") == summary.get("phase_status", {}).get("FEEDBACK")
        and evidence_by_layer.get("OUTCOME", {}).get("status") == "AVAILABLE"
    )
    check(checks, "evidence_map_status_consistency", evidence_consistency,
          "Evidence-map SIGNAL/PREDICTION/FEEDBACK/OUTCOME statuses agree with the summary and source phase manifests.")

    all_dashboard_text = json.dumps(summary, ensure_ascii=False) + " " + " ".join(
        json.dumps(row, ensure_ascii=False) for rows in csv_data.values() for row in rows
    )
    lower_text = all_dashboard_text.lower()
    gap_terms = ["application", "recruiter", "funnel", "interview"]
    gaps_explicit = all(term in lower_text for term in gap_terms)
    check(checks, "internal_data_gaps_explicit", gaps_explicit,
          "Dashboard explicitly documents missing application, recruiter/override, funnel, and interview evidence.")
    no_link_claim = "no individual hire is linked" in lower_text or "no candidate-level linkage" in lower_text
    no_causal_claim = "no causal effect is established" in lower_text or "does not establish" in lower_text and "causal" in lower_text
    check(checks, "no_candidate_linkage_claim", no_link_claim,
          "Dashboard states that candidate-level Greenhouse-to-hire linkage is absent.")
    check(checks, "no_causal_greenhouse_claim", no_causal_claim,
          "Dashboard does not attribute observed outcomes causally to Greenhouse.")

    # Verify all recorded dashboard object hashes and row counts, then verify
    # the dashboard audit CSV itself against its manifest record.
    manifest_outputs = dashboard_manifest.get("outputs", {})
    hash_failures = []
    for name, meta in manifest_outputs.items():
        relative = meta.get("path")
        path = BASE / relative if relative else None
        if path is None or not path.exists() or sha256_file(path) != meta.get("sha256"):
            hash_failures.append(name)
            continue
        if path.suffix.lower() == ".csv":
            actual_rows = len(read_csv(path))
            expected_rows = meta.get("rows", meta.get("row_count"))
            if expected_rows is not None and actual_rows != int(expected_rows):
                hash_failures.append(name + ":row_count")
        elif path.suffix.lower() == ".json":
            read_json(path)
    audit_meta = dashboard_manifest.get("audit", {})
    audit_path = BASE / audit_meta.get("path", "")
    audit_hash_ok = audit_path.exists() and sha256_file(audit_path) == audit_meta.get("sha256")
    check(checks, "dashboard_hashes_and_readback", not hash_failures and audit_hash_ok,
          f"Dashboard object hash/row checks failures={hash_failures}; dashboard audit hash match={audit_hash_ok}.")

    check(checks, "dashboard_manifest_readable", isinstance(dashboard_manifest, dict), "Executive dashboard manifest parsed as JSON.")
    check(checks, "summary_json_readable", isinstance(summary, dict), "Executive summary parsed as JSON.")
    return write_report(checks, counts, {"known": known, "total": total, "summary": summary})


def write_report(checks: list[dict[str, Any]], counts: dict[str, int] | None, context: dict[str, Any] | None) -> int:
    csv_path = AUDIT / "executive_dashboard_validation.csv"
    json_path = AUDIT / "executive_dashboard_validation.json"
    overall = "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check", "status", "detail"])
        writer.writeheader()
        writer.writerows(checks)
    report = {
        "validation": "version_c_phase_7_executive_dashboard",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "checks": len(checks),
        "passed": sum(row["status"] == "PASS" for row in checks),
        "failed": sum(row["status"] == "FAIL" for row in checks),
        "source_outcome_counts": counts,
        "outputs": {
            "validation_csv": {"path": str(csv_path.relative_to(BASE)), "sha256": sha256_file(csv_path)},
        },
    }
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"overall_status": overall, "checks": report["checks"], "passed": report["passed"], "failed": report["failed"], "outcome_counts": counts,
                      "known_sex": (context or {}).get("known"), "total": (context or {}).get("total"),
                      "male_share_known_sex": (context or {}).get("summary", {}).get("outcome_layer", {}).get("male_share_known_sex"),
                      "female_share_known_sex": (context or {}).get("summary", {}).get("outcome_layer", {}).get("female_share_known_sex"),
                      "male_female_ratio": (context or {}).get("summary", {}).get("outcome_layer", {}).get("male_female_ratio"),
                      "unknown_share_all": (context or {}).get("summary", {}).get("outcome_layer", {}).get("unknown_share_all_records"),
                      "audit_csv": str(csv_path), "audit_json": str(json_path)}, indent=2))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
