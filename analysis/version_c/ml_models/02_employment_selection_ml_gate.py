"""Employment-selection ML readiness gate for Version C.

This pre-model gate audits aggregate role/month evidence only. It never
constructs applicant denominators, candidate-level outcomes, or person rows.
The GitHub URL is recorded as destination metadata; no network action occurs.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

VERSION_C = Path(__file__).resolve().parents[1]
WORK = VERSION_C / "ml_models"
INPUT_MANIFEST = WORK / "audit" / "predictive_model_run_manifest.json"
LEGACY_PHASE4 = VERSION_C / "audit" / "predictive_model_run_manifest.json"
OUTPUTS = WORK / "outputs"
AUDIT = WORK / "audit"
GATE_JSON = OUTPUTS / "02_employment_selection_ml_gate.json"
GATE_AUDIT = AUDIT / "02_employment_selection_ml_gate_checks.csv"
GATE_MANIFEST = AUDIT / "02_employment_selection_ml_gate_manifest.json"
GITHUB_DESTINATION = "https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"
MIN_ROLE_MONTH_CELLS = 20
MIN_CLASS_CELLS = 5
EXPECTED_COUNTS = {"bridge": 41, "hiring": 1095, "master": 1246, "signals": 1246}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def record(checks: list[dict], check_id: str, passed: bool, detail: str) -> None:
    checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})


def record_gate(checks: list[dict], check_id: str, passed: bool, detail: str) -> None:
    # An unmet estimability criterion is the result of the gate, not an audit
    # implementation failure. Keep it distinct from broken provenance/checks.
    checks.append({"check_id": check_id, "status": "PASS" if passed else "NOT_MET", "detail": detail})


def main() -> int:
    if not INPUT_MANIFEST.is_file():
        raise SystemExit(f"Run 01_predictive_models_v1.py first; missing {INPUT_MANIFEST}")
    model_manifest = read_json(INPUT_MANIFEST)
    legacy = read_json(LEGACY_PHASE4) if LEGACY_PHASE4.is_file() else {}
    counts = model_manifest.get("counts", {})
    inputs = model_manifest.get("inputs", {})
    outputs = model_manifest.get("outputs", {})
    guards = model_manifest.get("design_guards", {})

    matched = int(counts.get("matched_known_sex_cells", 0))
    male_cells = int(counts.get("male_present_cells", 0))
    female_cells = int(counts.get("female_present_cells", 0))
    raw_bridge_rows = int(inputs.get("bridge", {}).get("rows", 0))
    gate_cell_count = matched >= MIN_ROLE_MONTH_CELLS
    gate_male_variation = male_cells >= MIN_CLASS_CELLS
    gate_female_variation = female_cells >= MIN_CLASS_CELLS
    gate_passed = gate_cell_count and gate_male_variation and gate_female_variation

    checks: list[dict] = []
    expected_input_names = set(EXPECTED_COUNTS)
    record(checks, "aggregate_input_inventory", expected_input_names <= set(inputs),
           f"Inputs recorded={sorted(inputs)}; expected at least={sorted(expected_input_names)}")
    legacy_counts = legacy.get("counts", {})
    legacy_ok = (legacy.get("status") == "NOT_ESTIMABLE"
                 and legacy_counts.get("matched_known_sex_cells") == matched
                 and legacy_counts.get("male_present_cells") == male_cells
                 and legacy_counts.get("female_present_cells") == female_cells)
    record(checks, "phase4_reconciliation", legacy_ok,
           f"Phase 4={legacy.get('status')}; matched/male/female={legacy_counts.get('matched_known_sex_cells')}/{legacy_counts.get('male_present_cells')}/{legacy_counts.get('female_present_cells')}; workstream={matched}/{male_cells}/{female_cells}")
    input_hash_issues = []
    for name, item in inputs.items():
        path = VERSION_C / item.get("path", "")
        if not path.is_file():
            input_hash_issues.append(f"{name}: missing {item.get('path')}")
            continue
        if sha256(path) != item.get("sha256"):
            input_hash_issues.append(f"{name}: hash mismatch")
        if name in EXPECTED_COUNTS and int(item.get("rows", -1)) != EXPECTED_COUNTS[name]:
            input_hash_issues.append(f"{name}: unexpected row count {item.get('rows')}")
    record(checks, "frozen_phase2_phase3_inputs", not input_hash_issues,
           "; ".join(input_hash_issues) if input_hash_issues else "Recorded source hashes and frozen row counts reconcile.")

    outputs_ok = True
    output_issues = []
    for name, item in outputs.items():
        path = VERSION_C / item.get("path", "")
        if not path.is_file() or sha256(path) != item.get("sha256"):
            outputs_ok = False
            output_issues.append(f"{name}: missing or hash mismatch")
    record(checks, "step01_output_hashes", outputs_ok,
           "; ".join(output_issues) if output_issues else f"Verified {len(outputs)} ML workstream output hashes.")

    no_linkage = guards.get("candidate_level_linkage") is False
    no_sex_target = guards.get("unknown_in_binary_target") is False
    no_archive_date = guards.get("archive_capture_as_posting_date") is False
    no_causal = guards.get("causal_claim") is False
    record(checks, "design_guards", no_linkage and no_sex_target and no_archive_date and no_causal,
           f"candidate_linkage={guards.get('candidate_level_linkage')}; unknown_target={guards.get('unknown_in_binary_target')}; archive_date={guards.get('archive_capture_as_posting_date')}; causal_claim={guards.get('causal_claim')}")
    record(checks, "independent_aggregate_unit", raw_bridge_rows == 41 and matched <= raw_bridge_rows,
           f"Phase 2 aggregate bridge rows={raw_bridge_rows}; eligible matched role/month cells={matched}; no row expansion used.")
    record_gate(checks, "role_month_cell_minimum", gate_cell_count,
           f"Eligible cells={matched}; minimum={MIN_ROLE_MONTH_CELLS}")
    record_gate(checks, "male_class_variation_minimum", gate_male_variation,
           f"Cells with Male outcomes={male_cells}; minimum={MIN_CLASS_CELLS}")
    record_gate(checks, "female_class_variation_minimum", gate_female_variation,
           f"Cells with Female outcomes={female_cells}; minimum={MIN_CLASS_CELLS}")

    metrics_path = OUTPUTS / "predictive_model_metrics.csv"
    metrics = list(csv.DictReader(metrics_path.open(newline="", encoding="utf-8"))) if metrics_path.is_file() else []
    if not gate_passed:
        outputs_stopped_at_gate = bool(metrics) and all(r.get("status") == "NOT_ESTIMABLE" for r in metrics)
    else:
        outputs_stopped_at_gate = True  # models may now proceed in the next workstream step
    record(checks, "model_execution_follows_gate", outputs_stopped_at_gate,
           "All recorded model rows are NOT_ESTIMABLE; no fitted result is present." if not gate_passed else "Estimability gate passes; model execution may proceed as a separate step.")
    record(checks, "github_destination_preserved", GITHUB_DESTINATION.endswith("Anthropic_Greenhouse_ATS_AI_Biased"),
           f"Destination metadata={GITHUB_DESTINATION}; no network/publish action performed.")

    gate_status = "ESTIMABLE" if gate_passed else "NOT_ESTIMABLE_FROM_PUBLIC_DATA"
    failures = [row for row in checks if row["status"] == "FAIL"]
    audit_status = "PASS" if not failures else "FAIL"
    reason = None if gate_passed else (
        f"Eligible aggregate role/month cells={matched} (minimum {MIN_ROLE_MONTH_CELLS}); "
        f"cells with Male outcomes={male_cells} and Female outcomes={female_cells} "
        f"(minimum {MIN_CLASS_CELLS} each). The model gate does not pass."
    )
    result = {
        "workstream": "Version C 3.0 — Employment Selection ML",
        "gate": gate_status,
        "audit_status": audit_status,
        "executive_question": "Do observable recruiting signals contain measurable predictive information about aggregate observed Male/Female hiring composition?",
        "primary_model": "Logistic regression",
        "secondary_model": "Gradient boosting",
        "public_data_adverse_impact_status": "NOT_ESTIMABLE_FROM_PUBLIC_DATA; applicant/stage denominators are absent",
        "estimability": {"raw_role_month_bridge_rows": raw_bridge_rows,
                         "eligible_dated_posting_and_known_sex_cells": matched,
                         "minimum_cells": MIN_ROLE_MONTH_CELLS,
                         "male_outcome_cells": male_cells,
                         "female_outcome_cells": female_cells,
                         "minimum_cells_per_class": MIN_CLASS_CELLS,
                         "gate_passed": gate_passed},
        "reason": reason,
        "model_fit_performed_by_this_gate": False,
        "github_repository_destination": GITHUB_DESTINATION,
        "github_destination_verified_or_published": False,
        "guardrails": {"sex_inference": False, "sex_as_feature": False,
                       "unknown_collapsed": False, "synthetic_candidates": False,
                       "applicant_denominators_manufactured": False,
                       "candidate_level_linkage": False, "future_information": False,
                       "post_hire_leakage": False, "greenhouse_causal_claim": False},
        "checks": checks,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    GATE_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with GATE_AUDIT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check_id", "status", "detail"])
        writer.writeheader(); writer.writerows(checks)
    manifest = {"step": 2, "gate": gate_status, "audit_status": audit_status,
                "input_manifest": str(INPUT_MANIFEST.relative_to(VERSION_C)),
                "input_manifest_sha256": sha256(INPUT_MANIFEST),
                "outputs": {"gate": {"path": str(GATE_JSON.relative_to(VERSION_C)), "sha256": sha256(GATE_JSON)},
                            "audit": {"path": str(GATE_AUDIT.relative_to(VERSION_C)), "sha256": sha256(GATE_AUDIT)}},
                "checks": len(checks), "failures": len(failures),
                "github_repository_destination": GITHUB_DESTINATION,
                "github_publish_performed": False}
    GATE_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("VERSION C — 02 EMPLOYMENT SELECTION ML GATE")
    print("=" * 68)
    print(f"AUDIT STATUS: {audit_status}")
    print(f"ML READINESS: {gate_status}")
    print("PUBLIC-DATA ADVERSE IMPACT: NOT ESTIMABLE FROM PUBLIC DATA")
    print(f"ROLE/MONTH BRIDGE UNITS: {raw_bridge_rows}")
    print(f"ELIGIBLE MATCHED CELLS: {matched} (minimum {MIN_ROLE_MONTH_CELLS})")
    print(f"MALE OUTCOME CELLS: {male_cells} (minimum {MIN_CLASS_CELLS})")
    print(f"FEMALE OUTCOME CELLS: {female_cells} (minimum {MIN_CLASS_CELLS})")
    print(f"MODEL FIT PERFORMED: NO")
    if reason: print(f"GATE REASON: {reason}")
    print("MODELS IF GATE PASSES: Logistic Regression (primary); Gradient Boosting (secondary)")
    print("CANDIDATE-LEVEL RECORDS OR APPLICANT DENOMINATORS CREATED: NO")
    print("GITHUB DESTINATION (metadata only): " + GITHUB_DESTINATION)
    print("GITHUB PUBLISH PERFORMED: NO")
    print(f"CHECKS: {len(checks)}; FAILURES: {len(failures)}")
    print(f"GATE RESULT: {GATE_JSON}")
    print(f"AUDIT: {GATE_AUDIT}")
    print(f"MANIFEST: {GATE_MANIFEST}")
    return 0 if audit_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
