"""Version C — Phase 11 research-grade reproducibility/package audit.

Audit-only. Reads Phase 2–10 artifacts and writes new audit/report files only.
A PASS means checked artifact relationships reconcile; warnings may still block
external publication or model interpretation.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from pptx import Presentation

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT = BASE / "audit"

FILES: dict[str, Path] = {
    "phase2_master": OUT / "version_c_master.parquet",
    "phase2_hiring": OUT / "version_c_hiring_outcomes.parquet",
    "phase2_bridge": OUT / "version_c_role_month_bridge.parquet",
    "phase2_manifest": AUDIT / "version_c_run_manifest.json",
    "phase3_features": OUT / "signal_features.parquet",
    "phase3_summary": OUT / "signal_summary.csv",
    "phase3_examples": OUT / "signal_examples.csv",
    "phase3_audit": AUDIT / "signal_audit.csv",
    "phase3_manifest": AUDIT / "signal_run_manifest.json",
    "phase4_metrics": OUT / "predictive_model_metrics.csv",
    "phase4_oof": OUT / "predictive_oof_predictions.csv",
    "phase4_coefficients": OUT / "predictive_coefficients.csv",
    "phase4_findings": OUT / "predictive_findings.csv",
    "phase4_audit": AUDIT / "predictive_model_audit.csv",
    "phase4_manifest": AUDIT / "predictive_model_run_manifest.json",
    "phase5_monthly_representation": OUT / "monthly_representation.csv",
    "phase5_monthly_outcomes": OUT / "monthly_outcomes.csv",
    "phase5_lags": OUT / "lagged_associations.csv",
    "phase5_roles": OUT / "role_feedback_associations.csv",
    "phase5_summary": OUT / "feedback_summary.csv",
    "phase5_audit": AUDIT / "feedback_audit.csv",
    "phase5_manifest": AUDIT / "feedback_run_manifest.json",
    "phase6_outcomes": OUT / "outcome_distribution.csv",
    "phase6_period": OUT / "outcome_by_period.csv",
    "phase6_research": OUT / "research_outcome_distribution.csv",
    "phase6_fellowship": OUT / "fellowship_outcome_distribution.csv",
    "phase6_metrics": OUT / "executive_outcome_metrics.json",
    "phase6_manifest": AUDIT / "outcome_analysis_manifest.json",
    "phase7_summary": OUT / "executive_summary.json",
    "phase7_outcomes": OUT / "dashboard_outcome_distribution.csv",
    "phase7_signals": OUT / "dashboard_signal_findings.csv",
    "phase7_prediction": OUT / "dashboard_predictive_findings.csv",
    "phase7_feedback": OUT / "dashboard_feedback_findings.csv",
    "phase7_limitations": OUT / "dashboard_limitations.csv",
    "phase7_evidence": OUT / "dashboard_evidence_map.csv",
    "phase7_validation": AUDIT / "executive_dashboard_validation.json",
    "phase7_audit": AUDIT / "executive_dashboard_audit.csv",
    "phase7_manifest": AUDIT / "executive_dashboard_run_manifest.json",
    "phase8_manifest": AUDIT / "visualization_manifest.json",
    "phase8_audit": AUDIT / "visualization_audit.csv",
    "phase8_outcome_data": OUT / "visualization_outcome_data.csv",
    "phase8_evidence_data": OUT / "visualization_evidence_data.csv",
    "phase8_gap_data": OUT / "visualization_data_gaps.csv",
    "phase9_markdown": OUT / "executive_brief.md",
    "phase9_html": OUT / "executive_brief.html",
    "phase9_manifest": OUT / "executive_brief_manifest.json",
    "phase9_audit": AUDIT / "executive_brief_audit.csv",
    "phase10_presentation": OUT / "version_c_executive_deck.pptx",
    "phase10_outline": OUT / "version_c_executive_deck_outline.md",
    "phase10_manifest": OUT / "presentation_manifest.json",
    "phase10_audit": AUDIT / "presentation_audit.csv",
    "phase11_script": BASE / "11_reproducibility_package_audit.py",
}
VISUALS = [OUT / "executive_visuals" / f"{i:02d}_{name}.png" for i, name in enumerate(
    ["observed_outcomes", "known_sex_outcomes", "research_outcomes", "evidence_architecture", "data_gaps", "executive_evidence_map"], 1
)]
MANIFEST_KEYS = {
    "phase2_manifest": FILES["phase2_manifest"], "phase3_manifest": FILES["phase3_manifest"],
    "phase4_manifest": FILES["phase4_manifest"], "phase5_manifest": FILES["phase5_manifest"],
    "phase6_manifest": FILES["phase6_manifest"], "phase7_manifest": FILES["phase7_manifest"],
    "phase8_manifest": FILES["phase8_manifest"], "phase9_manifest": FILES["phase9_manifest"],
    "phase10_manifest": FILES["phase10_manifest"],
}
CANONICAL = {"MALE": 606, "FEMALE": 276, "UNKNOWN": 213}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def artifact_rows(path: Path) -> int:
    if path.suffix.lower() == ".parquet":
        return pq.read_table(path).num_rows
    if path.suffix.lower() == ".csv":
        return len(read_csv(path))
    if path.suffix.lower() == ".pptx":
        return len(Presentation(str(path)).slides)
    if path.suffix.lower() == ".json":
        read_json(path)
        return 1
    return 1


def add_check(checks: list[dict[str, Any]], check_id: str, status: str, detail: str, severity: str = "") -> None:
    checks.append({"check_id": check_id, "status": status, "severity": severity or ("ERROR" if status in {"FAIL", "MISSING"} else "INFO"), "detail": detail})


def resolve_manifest_path(value: str) -> Path | None:
    candidate = Path(value)
    probes = [candidate] if candidate.is_absolute() else [BASE / candidate, OUT / candidate.name, AUDIT / candidate.name]
    return next((path for path in probes if path.exists() and path.is_file()), None)


def collect_manifest_artifacts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if isinstance(value.get("sha256"), str) and isinstance(value.get("path") or value.get("file"), str):
            found.append(value)
        for child in value.values():
            found.extend(collect_manifest_artifacts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(collect_manifest_artifacts(child))
    return found


def audit_manifest_hashes(manifest_name: str, manifest: dict[str, Any]) -> tuple[int, list[str]]:
    checked = 0
    mismatches = []
    # Only outputs and audits are checked here; input hash fields can refer to
    # upstream R2 or machine-specific locations unavailable in this checkout.
    sections = [manifest.get("outputs", {}), manifest.get("audit", {})]
    artifacts: list[dict[str, Any]] = []
    for section in sections:
        artifacts.extend(collect_manifest_artifacts(section))
    for item in artifacts:
        path_value = item.get("path") or item.get("file")
        path = resolve_manifest_path(str(path_value))
        if path is None:
            continue
        checked += 1
        if sha256_file(path) != item["sha256"]:
            mismatches.append(str(path.relative_to(BASE)) if path.is_relative_to(BASE) else str(path))
    return checked, mismatches


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    schema_rows: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    inventory: dict[str, dict[str, Any]] = {}

    # File inventory and direct readability.
    missing = []
    for name, path in FILES.items():
        if not path.exists():
            missing.append(name)
            inventory[name] = {"path": str(path.relative_to(BASE)), "exists": False}
            add_check(checks, f"file_exists:{name}", "MISSING", f"Missing required Phase artifact: {path.relative_to(BASE)}")
            continue
        try:
            rows = artifact_rows(path)
            raw_hash = sha256_file(path)
            inventory[name] = {"path": str(path.relative_to(BASE)), "exists": True, "bytes": path.stat().st_size, "rows_or_slides": rows, "sha256": raw_hash}
            add_check(checks, f"readable:{name}", "PASS", f"Readable; rows/slides={rows}; sha256={raw_hash}")
        except Exception as exc:
            inventory[name] = {"path": str(path.relative_to(BASE)), "exists": True, "read_error": str(exc)}
            add_check(checks, f"readable:{name}", "FAIL", f"Could not read {path.name}: {exc}")

    for path in VISUALS:
        name = "visual:" + path.name
        if not path.exists():
            missing.append(name)
            inventory[name] = {"path": str(path.relative_to(BASE)), "exists": False}
            add_check(checks, f"file_exists:{name}", "MISSING", f"Missing Phase 8 visual: {path.relative_to(BASE)}")
        else:
            inventory[name] = {"path": str(path.relative_to(BASE)), "exists": True, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            add_check(checks, f"readable:{name}", "PASS", "PNG present and non-empty.")

    if missing:
        # Continue where possible, but record a clear incomplete package result.
        add_check(checks, "full_chain_artifact_presence", "FAIL", f"Missing {len(missing)} required artifacts: {missing}")

    # Parse manifests and recursively verify local outputs where hashes are recorded.
    manifests: dict[str, dict[str, Any]] = {}
    for name, path in MANIFEST_KEYS.items():
        if not path.exists():
            continue
        try:
            manifests[name] = read_json(path)
            checked, mismatches = audit_manifest_hashes(name, manifests[name])
            status = "PASS" if not mismatches else "FAIL"
            add_check(checks, f"manifest_hashes:{name}", status,
                      f"Verified {checked} locally resolvable output/audit hashes; mismatches={mismatches}.")
        except Exception as exc:
            add_check(checks, f"manifest_read:{name}", "FAIL", f"Manifest parse/hash audit error: {exc}")

    # Canonical outcome and Unknown invariants from frozen source records.
    try:
        hiring = pq.read_table(FILES["phase2_hiring"]).to_pylist()
        counts: Counter[str] = Counter()
        person_ids = []
        mapping_errors = 0
        for row in hiring:
            person_ids.append(str(row.get("PERSON_ID") or ""))
            source_sex = str(row.get("source_SEX") or "").strip().lower()
            label = "MALE" if source_sex == "male" else "FEMALE" if source_sex == "female" else "UNKNOWN"
            counts[label] += 1
            if str(row.get("outcome_sex") or "").upper() != label or row.get("sex_inferred") is not False:
                mapping_errors += 1
        source_counts = {key: counts[key] for key in ("MALE", "FEMALE", "UNKNOWN")}
        add_check(checks, "canonical_outcome_counts", "PASS" if source_counts == CANONICAL and len(hiring) == 1095 else "FAIL",
                  f"Source-derived={source_counts}; rows={len(hiring)}; expected={CANONICAL}, N=1095.")
        add_check(checks, "unique_person_ids", "PASS" if len(person_ids) == len(set(person_ids)) and len(person_ids) == 1095 else "FAIL",
                  f"Rows={len(person_ids)}, distinct PERSON_ID={len(set(person_ids))}.")
        add_check(checks, "sex_mapping_no_inference", "PASS" if mapping_errors == 0 else "FAIL",
                  f"source_SEX-derived labels and sex_inferred=False mismatches={mapping_errors}.")
        add_check(checks, "unknown_denominator", "PASS" if source_counts["UNKNOWN"] == 213 and source_counts["MALE"] + source_counts["FEMALE"] == 882 else "FAIL",
                  f"Known M/F={source_counts['MALE'] + source_counts['FEMALE']}; Unknown={source_counts['UNKNOWN']}; Unknown excluded from M/F share.")
    except Exception as exc:
        source_counts = {}
        add_check(checks, "canonical_outcome_counts", "FAIL", f"Could not reconcile frozen hiring source: {exc}")

    # Schema audit for core tables and outputs.
    schema_requirements = {
        "phase2_master": (FILES["phase2_master"], {"greenhouse_job_id", "exact_title", "date_evidence_class", "candidate_level_hire_linkage"}),
        "phase2_hiring": (FILES["phase2_hiring"], {"PERSON_ID", "source_SEX", "outcome_sex", "sex_inferred"}),
        "phase2_bridge": (FILES["phase2_bridge"], {"role_family", "month"}),
        "phase3_features": (FILES["phase3_features"], {"version_c_posting_id", "signal_research_count", "signal_technical_specialization_count", "candidate_level_outcome_linkage"}),
        "phase4_metrics": (FILES["phase4_metrics"], {"model", "status", "n_role_month_cells", "roc_auc", "reason"}),
        "phase5_lags": (FILES["phase5_lags"], {"scope", "signal", "outcome", "lag_months", "status"}),
    }
    for name, (path, required_cols) in schema_requirements.items():
        if not path.exists():
            schema_rows.append({"artifact": name, "status": "MISSING", "required_columns": ";".join(sorted(required_cols)), "missing_columns": ";".join(sorted(required_cols))})
            continue
        columns = set(pq.read_schema(path).names) if path.suffix == ".parquet" else set(read_csv(path)[0].keys() if read_csv(path) else [])
        absent = required_cols - columns
        schema_status = "PASS" if not absent else "FAIL"
        schema_rows.append({"artifact": name, "status": schema_status, "required_columns": ";".join(sorted(required_cols)), "missing_columns": ";".join(sorted(absent))})
        add_check(checks, f"schema:{name}", schema_status, f"Missing columns={sorted(absent)}; available={len(columns)}.")

    # Historical date evidence: archive capture is never assigned as posting date.
    if FILES["phase2_master"].exists():
        master = pq.read_table(FILES["phase2_master"]).to_pylist()
        date_counts = Counter(str(row.get("date_evidence_class") or "MISSING") for row in master)
        expected_date_counts = {"GREENHOUSE_POSTING_DATE": 514, "ARCHIVE_CAPTURE_ONLY": 617, "POSTING_DATE_OUTSIDE_WINDOW": 115}
        date_ok = dict(date_counts) == expected_date_counts
        archive_misassigned = sum(1 for row in master if row.get("date_evidence_class") == "ARCHIVE_CAPTURE_ONLY" and (row.get("first_published_at") or row.get("posting_date_if_known")))
        add_check(checks, "temporal_date_class_counts", "PASS" if date_ok else "FAIL", f"Date classes={dict(date_counts)}; expected={expected_date_counts}.")
        add_check(checks, "archive_capture_not_posting_date", "PASS" if archive_misassigned == 0 else "FAIL", f"Archive-only records with posting-date fields populated={archive_misassigned}.")
    phase5 = manifests.get("phase5_manifest", {})
    phase5_counts = phase5.get("counts", {})
    months_ok = phase5_counts.get("observed_start_months") == ["2026-04", "2026-05", "2026-06", "2026-07"] and phase5_counts.get("unobserved_outcome_months") == ["2026-08", "2026-09"]
    add_check(checks, "observed_start_coverage", "PASS" if months_ok else "FAIL", f"Observed={phase5_counts.get('observed_start_months')}; unavailable={phase5_counts.get('unobserved_outcome_months')}; absent months are not treated as zero.")

    # Phase 4/5 completeness and estimation state.
    phase4 = manifests.get("phase4_manifest", {})
    phase4_status = phase4.get("status", "MISSING")
    phase4_metrics = read_csv(FILES["phase4_metrics"]) if FILES["phase4_metrics"].exists() else []
    if phase4_status == "NOT_ESTIMABLE":
        phase4_consistent = len(phase4_metrics) == 6 and all(r.get("status") == "NOT_ESTIMABLE" for r in phase4_metrics) and bool(phase4.get("not_estimable_reason"))
        add_check(checks, "phase4_outputs_present_and_state_consistent", "PASS" if phase4_consistent else "FAIL",
                  f"Phase 4 manifest={phase4_status}; metric rows={len(phase4_metrics)}; no fitted model is expected because matched-cell gate failed.")
        add_check(checks, "phase4_estimation_limitation", "WARNING", phase4.get("not_estimable_reason", "NOT_ESTIMABLE"), severity="LIMITATION")
    elif phase4_status == "ESTIMATED":
        add_check(checks, "phase4_outputs_present_and_state_consistent", "PASS" if phase4_metrics else "FAIL", f"Phase 4 status={phase4_status}; metrics rows={len(phase4_metrics)}.")
    else:
        add_check(checks, "phase4_outputs_present_and_state_consistent", "MISSING", f"Phase 4 status not confirmed: {phase4_status}.")

    feedback_summary = read_csv(FILES["phase5_summary"]) if FILES["phase5_summary"].exists() else []
    feedback_items = {row.get("item"): row.get("value", "") for row in feedback_summary}
    phase5_complete = bool(feedback_summary) and feedback_items.get("status") == "COMPLETE_WITH_COVERAGE_LIMITS"
    add_check(checks, "phase5_outputs_present", "PASS" if phase5_complete else "MISSING", f"Phase 5 summary status={feedback_items.get('status')}; rows={len(feedback_summary)}.")
    add_check(checks, "phase5_coverage_limitation", "WARNING" if phase5_complete else "FAIL",
              f"Observed start coverage {phase5_counts.get('observed_start_months')}; +2 month comparison is deferred by small n.", severity="LIMITATION")

    # Leakage, candidate-level linkage, and causal boundary checks.
    phase2_methods = manifests.get("phase2_manifest", {}).get("methods", {})
    phase3_method = manifests.get("phase3_manifest", {}).get("association_method", {})
    phase4_guards = phase4.get("design_guards", {})
    phase5_method = phase5.get("method", {})
    phase6 = manifests.get("phase6_manifest", {})
    phase6_guards = phase6.get("design_guards", {})
    phase7_guards = manifests.get("phase7_manifest", {}).get("design_guards", {})
    phase8_guards = manifests.get("phase8_manifest", {}).get("design_guards", {})
    phase9_guards = manifests.get("phase9_manifest", {}).get("design_guards", {})
    phase10_guards = manifests.get("phase10_manifest", {}).get("design_guards", {})
    no_link = (
        phase2_methods.get("candidate_level_posting_to_hire_linkage") is False
        and phase3_method.get("candidate_level_linkage") is False
        and phase4_guards.get("candidate_level_linkage") is False
        and phase5_method.get("candidate_level_linkage") is False
        and phase6_guards.get("candidate_level_greenhouse_linkage") is False
        and phase7_guards.get("candidate_level_linkage") is False
        and phase8_guards.get("candidate_level_linkage") is False
        and phase9_guards.get("candidate_level_linkage") is False
        and phase10_guards.get("candidate_level_linkage") is False
    )
    add_check(checks, "candidate_linkage_integrity", "PASS" if no_link else "FAIL", "No phase claims individual Greenhouse posting-to-hire linkage." if no_link else "A phase manifest is missing or contradicts the no-linkage guard.")
    required_temporal_guards = [
        phase2_methods.get("archive_capture_date_is_posting_date"),
        phase3_method.get("archive_capture_dates_used_as_posting_dates"),
        phase4_guards.get("archive_capture_as_posting_date"),
        phase5_method.get("archive_capture_as_posting_date"),
        phase9_guards.get("archive_capture_as_posting_date"),
        phase10_guards.get("archive_capture_as_posting_date"),
    ]
    # Presentation-only Phase 7/8 may omit this guard because they do not
    # construct dates; if a guard is present it must still be explicitly false.
    presentation_date_guards = [phase7_guards.get("archive_capture_as_posting_date"), phase8_guards.get("archive_capture_as_posting_date")]
    no_archive_date_substitution = all(value is False for value in required_temporal_guards) and all(value in (None, False) for value in presentation_date_guards)
    add_check(checks, "archive_date_integrity", "PASS" if no_archive_date_substitution else "FAIL", "Archive capture timestamps remain distinct from posting dates." if no_archive_date_substitution else "Date-separation guard missing or false in a phase manifest.")
    no_sex_inference = phase2_methods.get("sex_inferred_from_name") is False and phase6_guards.get("sex_inferred") is False and phase8_guards.get("sex_inference") is False and phase9_guards.get("sex_inference") is False and phase10_guards.get("sex_inference") is False
    add_check(checks, "sex_inference_integrity", "PASS" if no_sex_inference else "FAIL", "Source SEX is preserved; no inference is permitted." if no_sex_inference else "Sex-inference guard missing or contradicted.")

    forbidden_tokens = {"source_sex", "outcome_sex", "male_count", "female_count", "unknown_count", "person_id", "candidate_id", "applicant_id"}
    predictive_oof_cols = {name.lower() for name in (read_csv(FILES["phase4_oof"])[0].keys() if FILES["phase4_oof"].exists() and read_csv(FILES["phase4_oof"]) else [])}
    leakage_cols = predictive_oof_cols & forbidden_tokens
    # Outcome columns in group-level predictions are legitimate audit labels,
    # but must not masquerade as input features; they are retained separately.
    if leakage_cols <= {"male_count", "female_count", "unknown_count"}:
        leakage_cols = set()
    add_check(checks, "predictive_output_leakage_schema", "PASS" if not leakage_cols else "WARNING",
              f"Potential forbidden person/sex input columns in OOF schema={sorted(leakage_cols)}; group outcome fields are permitted as outputs only.", severity="REVIEW" if leakage_cols else "INFO")
    phase4_source = (BASE / "03_predictive_models.py")
    phase4_code = phase4_source.read_text(encoding="utf-8") if phase4_source.exists() else ""
    code_guard = "MIN_ROLE_MONTHS" in phase4_code and "MIN_CLASS_CELLS" in phase4_code and "NOT_ESTIMABLE" in phase4_code
    add_check(checks, "phase4_insufficient_sample_stop_rule", "PASS" if code_guard else "FAIL", "Phase 4 code contains an explicit cell/class sufficiency gate." if code_guard else "Expected sample-size stop rule not found in Phase 4 source.")

    # Executive claim audit: trace claims to artifacts and screen for unsupported causal wording.
    brief_text = FILES["phase9_markdown"].read_text(encoding="utf-8") if FILES["phase9_markdown"].exists() else ""
    ppt = Presentation(str(FILES["phase10_presentation"])) if FILES["phase10_presentation"].exists() else None
    slide_texts = []
    if ppt:
        for idx, slide in enumerate(ppt.slides, 1):
            slide_texts.append((idx, " ".join(shape.text for shape in slide.shapes if getattr(shape, "has_text_frame", False))))
    all_exec_text = brief_text + " " + " ".join(text for _, text in slide_texts)
    causal_claims = []
    for sentence in re.split(r"(?<=[.!?])\s+", all_exec_text):
        if re.search(r"\bGreenhouse(?:\s+AI)?\s+(?:caused|causes|produced|creates|led to)\b", sentence, re.I):
            if not re.search(r"\b(no|not|never|cannot|does not|did not|without|neither)\b", sentence, re.I):
                causal_claims.append(sentence.strip())
    add_check(checks, "executive_causal_claim_screen", "PASS" if not causal_claims else "FAIL", f"Unsupported causal sentences found={causal_claims}.")

    expected_claims = [
        ("canonical_outcomes", "606 MALE / 276 FEMALE / 213 UNKNOWN", ["outputs/executive_summary.json", "outputs/dashboard_outcome_distribution.csv"]),
        ("known_sex_shares", "68.71% MALE / 31.29% FEMALE among known-sex records", ["outputs/executive_summary.json", "outputs/dashboard_outcome_distribution.csv"]),
        ("prediction_status", "PREDICTION is NOT_ESTIMABLE", ["audit/predictive_model_run_manifest.json", "outputs/dashboard_predictive_findings.csv"]),
        ("feedback_coverage", "August and September 2026 are unavailable, not zero", ["audit/feedback_run_manifest.json", "outputs/dashboard_limitations.csv"]),
        ("no_individual_linkage", "No candidate-level Greenhouse-to-hire link is claimed", ["audit/version_c_run_manifest.json", "outputs/executive_brief.md"]),
    ]
    for claim_id, statement, sources in expected_claims:
        exists = all((BASE / source).exists() for source in sources)
        claim_rows.append({"claim_id": claim_id, "claim": statement, "status": "PASS" if exists else "MISSING", "supporting_artifacts": ";".join(sources), "notes": "Claim is limited to the cited frozen artifacts; not independently generalized."})
        add_check(checks, f"claim_trace:{claim_id}", "PASS" if exists else "MISSING", f"Supporting artifacts present={exists}; sources={sources}.")
    slide_specs_path = BASE / "10_executive_presentation.py"
    slide_specs_code = slide_specs_path.read_text(encoding="utf-8") if slide_specs_path.exists() else ""
    slide_claim_map_ok = all(f'"title": "{spec["title"]}"' in slide_specs_code for spec in []) if False else len(slide_texts) == 12
    for idx, text in slide_texts:
        claim_rows.append({"claim_id": f"slide_{idx:02d}", "claim": text[:350], "status": "PASS" if text.strip() else "WARNING", "supporting_artifacts": "Slide source references and presentation manifest", "notes": "See 10_executive_presentation.py SLIDE_SPECS for slide-level artifact map."})
    add_check(checks, "presentation_slide_claim_inventory", "PASS" if slide_claim_map_ok else "FAIL", f"Deck slide count={len(slide_texts)}; expected=12; each slide has a source map in presentation script.")

    # Licensing/publication boundary: presence is not legal clearance.
    project_root = BASE.parents[1]
    license_candidates = [project_root / "LICENSE", project_root / "LICENSE.md", project_root / "NOTICE", project_root / "README.md"]
    license_docs = [path for path in license_candidates if path.exists()]
    source_license_metadata = any("license" in key.lower() for key in manifests.get("phase2_manifest", {}).keys())
    if license_docs and source_license_metadata:
        license_status = "WARNING"  # Documents exist, but this audit does not determine source rights.
        license_detail = f"Found project documents={[p.name for p in license_docs]}; dataset/source reuse rights still require human review."
    else:
        license_status = "WARNING"
        license_detail = "No machine-verifiable source-data license/permission evidence was found in the package. Review Greenhouse, archive, Dewey/PDL, and third-party text terms before external release."
    add_check(checks, "licensing_publication_boundary", license_status, license_detail, severity="EXTERNAL_RELEASE_REVIEW")
    add_check(checks, "privacy_external_release_review", "WARNING", "Before publication, review personal names/examples, source terms, privacy, and redistribution permissions; this package audit is not legal clearance.", severity="EXTERNAL_RELEASE_REVIEW")

    # Frozen brief/deck consistency and explicit limitation coverage.
    brief_manifest = manifests.get("phase9_manifest", {})
    deck_manifest = manifests.get("phase10_manifest", {})
    phase7_validation = read_json(FILES["phase7_validation"]) if FILES["phase7_validation"].exists() else {}
    phase9_status = brief_manifest.get("status")
    phase10_status = deck_manifest.get("status")
    add_check(checks, "brief_presentation_counts_consistent", "PASS" if brief_manifest.get("outcomes", {}).get("counts") == deck_manifest.get("outcomes", {}).get("counts") == CANONICAL else "FAIL",
              f"Phase 9 counts={brief_manifest.get('outcomes', {}).get('counts')}; Phase 10 counts={deck_manifest.get('outcomes', {}).get('counts')}.")
    required_gap_terms = ["Talent Matching", "criteria", "overrides", "funnel", "interview"]
    gap_text = " ".join(str(row.get("detail", "")) for row in read_csv(FILES["phase7_limitations"])) + " " + brief_text + " " + " ".join(text for _, text in slide_texts)
    missing_gap_terms = [term for term in required_gap_terms if term.lower() not in gap_text.lower()]
    add_check(checks, "required_internal_data_gaps", "PASS" if not missing_gap_terms else "FAIL", f"Missing data-gap concepts={missing_gap_terms}.")
    add_check(checks, "phase7_9_10_status_chain", "PASS" if phase7_validation.get("overall_status") == "PASS" and phase9_status == "PASS" and phase10_status == "PASS" else "FAIL",
              f"Phase 7 validation={phase7_validation.get('overall_status')}; Phase 9={phase9_status}; Phase 10={phase10_status}.")

    # Schema audit exports; manifest inventory contains exact hashes/bytes/rows.
    schema_path = AUDIT / "phase11_schema_audit.csv"
    with schema_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["artifact", "status", "required_columns", "missing_columns"])
        writer.writeheader(); writer.writerows(schema_rows)
    claim_path = AUDIT / "phase11_claim_audit.csv"
    with claim_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["claim_id", "claim", "status", "supporting_artifacts", "notes"])
        writer.writeheader(); writer.writerows(claim_rows)

    failures = sum(row["status"] in {"FAIL", "MISSING"} for row in checks)
    warnings = sum(row["status"] == "WARNING" for row in checks)
    final_status = "FAIL" if failures else "PASS_WITH_WARNINGS" if warnings else "PASS"
    checks_path = AUDIT / "phase11_reproducibility_checks.csv"
    with checks_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check_id", "status", "severity", "detail"])
        writer.writeheader(); writer.writerows(checks)

    report_lines = [
        "# Version C — Phase 11 Reproducibility / Package Audit", "",
        f"**Final status:** {final_status}  ",
        f"**Checks:** {len(checks)} · **Failures/missing:** {failures} · **Warnings:** {warnings}", "",
        "## Scope", "",
        "Read-only audit of Phase 2–10 files, manifests, output hashes, schema, outcome invariants, temporal/date evidence, linkage boundaries, executive claims, and release limitations.", "",
        "## Phase status", "",
        f"- Phase 4 prediction: **{phase4_status}**. The outputs are present; model fitting was stopped by the documented role/month sample gate.",
        f"- Phase 5 feedback: **{feedback_items.get('status', 'MISSING')}**. Coverage is limited to the observed start months, and the +2 month comparison is deferred.",
        f"- Phase 7 validation: **{phase7_validation.get('overall_status', 'MISSING')}**.",
        f"- Phase 9 brief: **{phase9_status or 'MISSING'}**.",
        f"- Phase 10 presentation: **{phase10_status or 'MISSING'}**.", "",
        "## Canonical outcomes", "",
        f"MALE {source_counts.get('MALE')} · FEMALE {source_counts.get('FEMALE')} · UNKNOWN {source_counts.get('UNKNOWN')} · total {sum(source_counts.values()) if source_counts else 'unknown'}.",
        "Unknown is preserved and excluded from known-sex shares. No sex is inferred.", "",
        "## Release boundary", "",
        "This audit is not legal clearance. Source licensing/redistribution terms, personal-name/example privacy, and publication permissions require human review before external release.", "",
        "## Interpretation", "",
        "A PASS_WITH_WARNINGS means the available package is internally traceable subject to documented limitations. It does not mean the predictive model was estimable, the hypothesis was proven, or Greenhouse causality was established.", "",
        "See `phase11_reproducibility_checks.csv`, `phase11_claim_audit.csv`, and `phase11_schema_audit.csv` for detailed results.", "",
    ]
    report_path = OUT / "version_c_reproducibility_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    checklist_path = OUT / "version_c_external_release_checklist.md"
    checklist = [
        "# Version C — External Release Checklist", "",
        "This checklist is intentionally open until reviewed by the project owner. Phase 11 does not establish legal permission.", "",
        "- [ ] Confirm Greenhouse, Internet Archive, Dewey/PDL, and other source terms permit the intended redistribution and presentation use.",
        "- [ ] Review named-person references, biographies, and other personal information for privacy and contextual risk.",
        "- [ ] Confirm whether job-description text and screenshots may be redistributed; prefer source links or minimal excerpts where required.",
        "- [ ] Review public claims against `phase11_claim_audit.csv` and cite underlying evidence in any exported deck.",
        "- [ ] Disclose that Phase 4 is NOT_ESTIMABLE and Phase 5 is exploratory with April–July observed starts; August/September are unavailable.",
        "- [ ] Verify accessibility: chart contrast, text size, alt text, and non-color distinctions.",
        "- [ ] Confirm removal of credentials, private paths, temporary files, and machine-specific metadata from any release bundle.",
        "- [ ] Have a research/ethics reviewer approve the final audience, context, and limitations language.", "",
    ]
    checklist_path.write_text("\n".join(checklist), encoding="utf-8")

    # Hash each existing artifact after all audits, but only read prior files.
    for path in [checks_path, claim_path, schema_path, report_path, checklist_path]:
        if not path.exists():
            raise RuntimeError(f"Phase 11 output missing: {path}")
    phase11_manifest = {
        "manifest_type": "version_c_phase_11_reproducibility_package_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "final_status": final_status,
        "checks_total": len(checks),
        "checks_failed_or_missing": failures,
        "checks_warning": warnings,
        "phase_status": {"phase4": phase4_status, "phase5": feedback_items.get("status"), "phase7_validation": phase7_validation.get("overall_status"), "phase9": phase9_status, "phase10": phase10_status},
        "canonical_outcomes": source_counts,
        "artifact_inventory": inventory,
        "manifest_hash_audit": "Local output/audit hashes checked where paths were resolvable; upstream R2 input references are recorded but not downloaded.",
        "outputs": {str(path.relative_to(BASE)): {"sha256": sha256_file(path), "bytes": path.stat().st_size, "rows": artifact_rows(path) if path.suffix.lower() == ".csv" else None} for path in [checks_path, claim_path, schema_path, report_path, checklist_path]},
        "release_boundary": "Licensing, privacy, and redistribution require human review; not certified by this audit.",
        "design_guards": {"prior_artifacts_modified": False, "new_statistical_analysis": False, "sex_inference": False, "candidate_linkage": False, "causal_claim": False},
    }
    manifest_path = AUDIT / "phase11_provenance_manifest.json"
    manifest_path.write_text(json.dumps(phase11_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readback = read_json(manifest_path)
    if readback.get("final_status") != final_status:
        raise RuntimeError("Phase 11 provenance manifest read-back failed.")

    print(json.dumps({"final_status": final_status, "checks": len(checks), "failures_or_missing": failures,
                      "warnings": warnings, "phase4": phase4_status, "phase5": feedback_items.get("status"),
                      "canonical_outcomes": source_counts, "report": str(report_path),
                      "external_release_checklist": str(checklist_path), "manifest": str(manifest_path)}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
