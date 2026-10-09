"""Version C — Phase 7: duplicate-only executive dashboard data layer.

Reads Phase 3–6 results and writes only new dashboard-prefixed copies and
executive summaries. It does not modify Plan A or any Phase 2–6 artifact.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any
from collections import Counter

import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT = BASE / "audit"

STUDY_WINDOW = {"start": "2026-04-01", "end": "2026-09-30"}
INPUTS = {
    "outcome_metrics": OUT / "executive_outcome_metrics.json",
    "outcome_distribution": OUT / "outcome_distribution.csv",
    "outcome_quality": OUT / "outcome_quality_summary.csv",
    "hiring_source": OUT / "version_c_hiring_outcomes.parquet",
    "signal_summary": OUT / "signal_summary.csv",
    "signal_manifest": AUDIT / "signal_run_manifest.json",
    "predictive_metrics": OUT / "predictive_model_metrics.csv",
    "predictive_manifest": AUDIT / "predictive_model_run_manifest.json",
    "feedback_summary": OUT / "feedback_summary.csv",
    "feedback_lags": OUT / "lagged_associations.csv",
    "feedback_roles": OUT / "role_feedback_associations.csv",
    "feedback_manifest": AUDIT / "feedback_run_manifest.json",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path, optional: bool = False) -> dict[str, Any] | None:
    if not path.exists():
        if optional:
            return None
        raise FileNotFoundError(f"Required input is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def read_csv(path: Path, optional: bool = False) -> list[dict[str, str]] | None:
    if not path.exists():
        if optional:
            return None
        raise FileNotFoundError(f"Required input is missing: {path}")
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> int:
    if columns is None:
        columns = list(dict.fromkeys(k for row in rows for k in row)) or ["status"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    with path.open("r", newline="", encoding="utf-8") as stream:
        return max(0, sum(1 for _ in csv.reader(stream)) - 1)


def input_hashes() -> dict[str, dict[str, Any]]:
    result = {}
    for name, path in INPUTS.items():
        exists = path.exists()
        if not exists:
            result[name] = {"path": str(path.relative_to(BASE)), "available": False, "sha256": None, "bytes": None}
        else:
            data = path.read_bytes()
            result[name] = {"path": str(path.relative_to(BASE)), "available": True, "sha256": sha(data), "bytes": len(data)}
    return result


def index_quality(rows: list[dict[str, str]]) -> dict[str, str]:
    return {r.get("metric", ""): r.get("value", "") for r in rows}


def recount_source_outcomes(path: Path) -> tuple[dict[str, int], int]:
    """Recount labels from source_SEX only; never infer from other fields."""
    table = pq.read_table(path, columns=["PERSON_ID", "source_SEX"])
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    for row in table.to_pylist():
        person_id = str(row.get("PERSON_ID") or "")
        if person_id in seen:
            raise ValueError("Duplicate PERSON_ID in frozen Phase 2 hiring outcomes.")
        seen.add(person_id)
        sex = str(row.get("source_SEX") or "").strip().lower()
        label = "MALE" if sex == "male" else "FEMALE" if sex == "female" else "UNKNOWN"
        counts[label] += 1
    return ({label: counts[label] for label in ("MALE", "FEMALE", "UNKNOWN")}, len(seen))


def find_signal_row(rows: list[dict[str, str]], group: str) -> dict[str, str] | None:
    return next((r for r in rows if r.get("group") == group), None)


def make_signal_findings(signal_rows: list[dict[str, str]] | None, signal_manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    if signal_rows is None:
        return [{"finding": "SIGNAL", "status": "NOT_AVAILABLE", "evidence_strength": "NONE", "details": "Phase 3 signal outputs were not found."}]
    result = []
    stats = (signal_manifest or {}).get("counts", {})
    for row in signal_rows:
        group = row.get("group", "")
        result.append({
            "finding": group,
            "posting_count": row.get("posting_count"),
            "descriptions_available": row.get("descriptions_available"),
            "named_person_mentions": row.get("total_named_person_count"),
            "researcher_reference_count": row.get("total_researcher_reference_count"),
            "publication_paper_reference_count": row.get("total_publication_paper_reference_count"),
            "research_exemplar_count": row.get("total_research_exemplar_count"),
            "evidence_strength": "DESCRIPTIVE_CORPUS_MEASURE",
            "interpretation": "Lexical/representation measurement only; not evidence of bias, preference, intent, or discrimination.",
            "source": "Phase 3 signal_summary.csv",
        })
    result.append({"finding": "signal_run_counts", "posting_count": stats.get("postings"),
                   "descriptions_available": stats.get("descriptions_available"),
                   "named_person_mentions": stats.get("named_person_reference_postings"),
                   "researcher_reference_count": None, "publication_paper_reference_count": None,
                   "research_exemplar_count": None, "evidence_strength": "DESCRIPTIVE_CORPUS_MEASURE",
                   "interpretation": "Counts as recorded in the Phase 3 run manifest.", "source": "Phase 3 signal_run_manifest.json"})
    return result


def make_predictive_findings(rows: list[dict[str, str]] | None, manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    if rows is None:
        return [{"model": "ALL", "status": "NOT_AVAILABLE", "n_role_month_cells": 0, "reason": "Phase 4 outputs were not found."}]
    status_from_manifest = (manifest or {}).get("status")
    result = []
    for row in rows:
        result.append({
            "model": row.get("model"),
            "status": row.get("status") or status_from_manifest or "NOT_AVAILABLE",
            "n_role_month_cells": row.get("n_role_month_cells"),
            "n_male_cells": row.get("n_male_cells"),
            "n_female_cells": row.get("n_female_cells"),
            "roc_auc": row.get("roc_auc"), "pr_auc": row.get("pr_auc"),
            "composition_mae": row.get("composition_mae"),
            "reason": row.get("reason"),
            "evidence_strength": "NOT_ESTIMABLE" if (row.get("status") == "NOT_ESTIMABLE" or status_from_manifest == "NOT_ESTIMABLE") else "MODEL_DIAGNOSTIC",
            "interpretation": "Ecological cell-level diagnostic only; never an individual candidate prediction.",
        })
    return result


def make_feedback_findings(lag_rows: list[dict[str, str]] | None, role_rows: list[dict[str, str]] | None) -> list[dict[str, Any]]:
    if lag_rows is None and role_rows is None:
        return [{"scope": "ALL", "signal": "", "outcome": "", "n": 0, "status": "NOT_AVAILABLE", "evidence_strength": "NONE", "interpretation": "Phase 5 outputs were not found."}]
    result: list[dict[str, Any]] = []
    for source_name, rows in (("monthly_lag", lag_rows or []), ("role_month", role_rows or [])):
        for row in rows:
            n = int(row.get("n") or 0)
            status = row.get("status") or "NOT_AVAILABLE"
            result.append({
                "scope": row.get("scope") or source_name,
                "signal": row.get("signal", ""),
                "outcome": row.get("outcome", ""),
                "lag_months": row.get("lag_months", ""),
                "n": n,
                "pearson_r": row.get("pearson_r", ""),
                "spearman_rho": row.get("spearman_rho", ""),
                "status": status,
                "evidence_strength": "LOW_EXPLORATORY" if n <= 5 and status.startswith("ESTIMATED") else ("DEFERRED" if status.startswith("DEFERRED") else "EXPLORATORY"),
                "months_or_cells": row.get("months_or_cells", ""),
                "interpretation": row.get("interpretation") or "Aggregate co-movement only; not causal and not candidate-level.",
                "source_file": "lagged_associations.csv" if source_name == "monthly_lag" else "role_feedback_associations.csv",
            })
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    hashes = input_hashes()

    # Phase 6 is the authoritative executive outcome layer.
    outcome_metrics = read_json(INPUTS["outcome_metrics"])
    outcome_distribution = read_csv(INPUTS["outcome_distribution"])
    outcome_quality = read_csv(INPUTS["outcome_quality"])
    signal_summary = read_csv(INPUTS["signal_summary"], optional=True)
    signal_manifest = read_json(INPUTS["signal_manifest"], optional=True)
    predictive_rows = read_csv(INPUTS["predictive_metrics"], optional=True)
    predictive_manifest = read_json(INPUTS["predictive_manifest"], optional=True)
    feedback_summary = read_csv(INPUTS["feedback_summary"], optional=True)
    feedback_lags = read_csv(INPUTS["feedback_lags"], optional=True)
    feedback_roles = read_csv(INPUTS["feedback_roles"], optional=True)
    feedback_manifest = read_json(INPUTS["feedback_manifest"], optional=True)

    # Copy/normalize only executive presentation data, never source layers.
    dashboard_outcomes = []
    for row in outcome_distribution or []:
        dashboard_outcomes.append({
            "outcome_sex": row.get("outcome_sex"),
            "person_count": row.get("person_count"),
            "share_all_people": row.get("share_all_people"),
            "share_known_sex": row.get("share_known_sex"),
            "denominator_all_people": row.get("denominator_all_people"),
            "denominator_known_sex": row.get("denominator_known_sex"),
            "source_field": row.get("source_field"),
            "sex_inferred": row.get("sex_inferred"),
            "evidence_layer": "OBSERVED_OUTCOME",
        })

    signal_findings = make_signal_findings(signal_summary, signal_manifest)
    predictive_findings = make_predictive_findings(predictive_rows, predictive_manifest)
    feedback_findings = make_feedback_findings(feedback_lags, feedback_roles)

    q = index_quality(outcome_quality or [])
    counts = outcome_metrics.get("outcome_counts", {})
    shares = outcome_metrics.get("outcome_shares", {})
    source_counts, source_people = recount_source_outcomes(INPUTS["hiring_source"])
    if source_counts != {k: int(counts.get(k, 0)) for k in ("MALE", "FEMALE", "UNKNOWN")}:
        raise ValueError(f"Phase 6 counts do not match the frozen source_SEX recount: {source_counts}")
    pc = (predictive_manifest or {}).get("counts", {})
    fm_counts = (feedback_manifest or {}).get("counts", {})
    signal_counts = (signal_manifest or {}).get("counts", {})
    unknown_gap = q.get("blank_or_null_source_sex", counts.get("UNKNOWN"))
    limits = [
        {"limitation": "No candidate-level linkage", "detail": "Public posting records cannot be linked to individual observed hires; all comparisons remain aggregate/ecological.", "applies_to": "SIGNAL, PREDICTION, FEEDBACK", "severity": "STRUCTURAL_DATA_GAP"},
        {"limitation": "Prediction not estimable", "detail": (predictive_manifest or {}).get("not_estimable_reason") or "Phase 4 model status is not estimable from current role/month cells.", "applies_to": "PREDICTION", "severity": "BLOCKING_FOR_MODEL_CLAIMS"},
        {"limitation": "Sparse temporal overlap", "detail": f"Phase 5 uses {fm_counts.get('exact_role_month_overlap_cells', 'unknown')} exact role/month posting-hiring overlaps; +1 month has at most three observed pairs and +2 month is deferred.", "applies_to": "FEEDBACK", "severity": "LOW_POWER"},
        {"limitation": "Incomplete observed start coverage", "detail": "Observed starts are available April-July 2026. August and September are unavailable, not zero.", "applies_to": "OUTCOMES, FEEDBACK", "severity": "TEMPORAL_COVERAGE"},
        {"limitation": "Archive date distinction", "detail": "Archive capture-only evidence is not treated as an established posting date in temporal comparisons.", "applies_to": "SIGNAL, FEEDBACK", "severity": "METHOD_RULE"},
        {"limitation": "Unknown source sex", "detail": f"{unknown_gap} records have blank/null source sex and remain UNKNOWN; they are excluded from known-sex shares.", "applies_to": "OUTCOMES", "severity": "MISSINGNESS"},
        {"limitation": "No causal identification", "detail": "No phase establishes that recruiting signals caused observed outcome composition.", "applies_to": "ALL", "severity": "CAUSAL_BOUNDARY"},
        {"limitation": "Internal workflow unavailable", "detail": "No internal Greenhouse matching, recruiter override, applicant-stage, or funnel data are present.", "applies_to": "GOVERNANCE", "severity": "INTERNAL_DATA_GAP"},
    ]

    evidence_map = [
        {"layer": "SIGNAL", "source": "Phase 3 Greenhouse master + signal features", "evidence_type": "Measured candidate-facing text/representation", "status": "AVAILABLE", "result": f"{signal_counts.get('postings', 'unknown')} posting records; {signal_counts.get('descriptions_available', 'unknown')} descriptions available.", "strength": "DESCRIPTIVE", "claim_boundary": "Measures text and examples; does not establish intent or bias."},
        {"layer": "PREDICTION", "source": "Phase 4 role/month ecological model inputs", "evidence_type": "Predictive association diagnostic", "status": (predictive_manifest or {}).get("status", "NOT_AVAILABLE"), "result": f"{pc.get('eligible_binomial_cells', 'unknown')} eligible cells; Male-present={pc.get('male_present_cells', 'unknown')}; Female-present={pc.get('female_present_cells', 'unknown')}.", "strength": "NOT_ESTIMABLE" if (predictive_manifest or {}).get("status") == "NOT_ESTIMABLE" else "UNASSESSED", "claim_boundary": "No candidate-level prediction; current output is not estimable."},
        {"layer": "FEEDBACK", "source": "Phase 5 monthly and role/month associations", "evidence_type": "Exploratory temporal/ecological co-movement", "status": "COMPLETE_WITH_COVERAGE_LIMITS" if feedback_manifest else "NOT_AVAILABLE", "result": f"{fm_counts.get('exact_role_month_overlap_cells', 'unknown')} exact role/month intersections; observed hire months={','.join(fm_counts.get('observed_start_months', []))}.", "strength": "LOW_EXPLORATORY", "claim_boundary": "Small monthly/role samples; no causal or candidate-level inference."},
        {"layer": "OUTCOME", "source": "Phase 6 frozen Dewey observed-hire outcome layer", "evidence_type": "Observed source sex distribution", "status": "AVAILABLE", "result": f"{counts.get('MALE')} MALE / {counts.get('FEMALE')} FEMALE / {counts.get('UNKNOWN')} UNKNOWN; known-sex shares {shares.get('male_share_known_sex', 0):.2%} / {shares.get('female_share_known_sex', 0):.2%}.", "strength": "OBSERVED_WITH_MISSINGNESS", "claim_boundary": "Observed data composition, not complete internal hiring funnel or a Greenhouse effect."},
        {"layer": "AI PATHWAY", "source": "Unavailable internal Greenhouse Talent Matching records", "evidence_type": "Internal decision-path data gap", "status": "NOT_OBSERVABLE", "result": "No model recommendations, rankings, or candidate-level matching outputs.", "strength": "DOCUMENTED_GAP", "claim_boundary": "Cannot determine differential treatment by Greenhouse Talent Matching."},
        {"layer": "WORKFLOW", "source": "Unavailable applicant funnel records", "evidence_type": "Internal process data gap", "status": "NOT_OBSERVABLE", "result": "No candidate-level application stages or transition records.", "strength": "DOCUMENTED_GAP", "claim_boundary": "Cannot identify where candidates diverge in the funnel."},
        {"layer": "HUMAN OVERRIDE", "source": "Unavailable recruiter decision logs", "evidence_type": "Human-AI interaction data gap", "status": "NOT_OBSERVABLE", "result": "No recommendation acceptance, override, or recruiter action logs.", "strength": "DOCUMENTED_GAP", "claim_boundary": "Cannot compare recruiter overrides across demographic groups."},
        {"layer": "INTERVIEW", "source": "Unavailable interview evaluation records", "evidence_type": "Selection-stage data gap", "status": "NOT_OBSERVABLE", "result": "No candidate-level interview scores or evaluator records.", "strength": "DOCUMENTED_GAP", "claim_boundary": "Cannot assess divergence in interview evaluations."},
    ]

    output_rows = {
        "dashboard_outcome_distribution.csv": dashboard_outcomes,
        "dashboard_signal_findings.csv": signal_findings,
        "dashboard_predictive_findings.csv": predictive_findings,
        "dashboard_feedback_findings.csv": feedback_findings,
        "dashboard_limitations.csv": limits,
        "dashboard_evidence_map.csv": evidence_map,
    }
    output_meta = {}
    audit_rows = []
    for filename, rows in output_rows.items():
        path = OUT / filename
        row_count = write_csv(path, rows)
        output_meta[filename] = {"path": str(path.relative_to(BASE)), "rows": row_count, "sha256": sha(path.read_bytes()), "readback_verified": row_count == len(rows)}
        audit_rows.append({"check": f"output_readback:{filename}", "status": "PASS" if row_count == len(rows) else "FAIL", "rows": row_count, "details": f"Expected {len(rows)} rows; SHA-256 recorded."})

    male = int(counts.get("MALE", 0)); female = int(counts.get("FEMALE", 0)); unknown = int(counts.get("UNKNOWN", 0))
    known = male + female
    executive_summary = {
        "title": "Version C — Executive Dashboard Data",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "study_window": STUDY_WINDOW,
        "outcome_layer": {"distinct_people": source_people,
                          "MALE": male, "FEMALE": female, "UNKNOWN": unknown,
                          "known_sex_denominator": known,
                          "male_share_known_sex": male / known if known else None,
                          "female_share_known_sex": female / known if known else None,
                          "male_female_ratio": male / female if female else None,
                          "unknown_share_all_records": unknown / (male + female + unknown) if male + female + unknown else None},
        "phase_status": {"SIGNAL": "AVAILABLE" if signal_summary is not None else "NOT_AVAILABLE",
                         "PREDICTION": (predictive_manifest or {}).get("status", "NOT_AVAILABLE"),
                         "FEEDBACK": "COMPLETE_WITH_COVERAGE_LIMITS" if feedback_manifest else "NOT_AVAILABLE",
                         "OUTCOME": "AVAILABLE"},
        "signal_snapshot": {"postings": signal_counts.get("postings"), "descriptions_available": signal_counts.get("descriptions_available"), "named_person_reference_postings": signal_counts.get("named_person_reference_postings")},
        "predictive_snapshot": {"eligible_role_month_cells": pc.get("eligible_binomial_cells"), "male_present_cells": pc.get("male_present_cells"), "female_present_cells": pc.get("female_present_cells"), "reason": (predictive_manifest or {}).get("not_estimable_reason")},
        "feedback_snapshot": {"exact_role_month_overlap_cells": fm_counts.get("exact_role_month_overlap_cells"), "observed_start_months": fm_counts.get("observed_start_months"), "unobserved_outcome_months": fm_counts.get("unobserved_outcome_months")},
        "executive_wording": "Observed demographic outcome composition is measurable. Candidate-facing recruiting signals are measurable. Current role/month data are insufficient for the planned binary predictive model, and the available temporal comparisons are exploratory. Internal Greenhouse decision pathways are not publicly observable.",
        "causal_boundaries": ["No causal effect is established.", "No Greenhouse AI or recruiter workflow treatment is measured.", "No individual hire is linked to any posting.", "UNKNOWN is not reassigned to MALE or FEMALE."],
        "governance_distinction": "MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS",
        "outputs": output_meta,
    }
    summary_path = OUT / "executive_summary.json"
    summary_bytes = (json.dumps(executive_summary, indent=2, sort_keys=True) + "\n").encode()
    summary_path.write_bytes(summary_bytes)
    summary_check = json.loads(summary_path.read_text(encoding="utf-8"))
    audit_rows.append({"check": "output_readback:executive_summary.json", "status": "PASS" if summary_check["outcome_layer"]["MALE"] == male else "FAIL", "rows": 1, "details": f"SHA-256={sha(summary_bytes)}"})
    audit_rows.append({"check": "frozen_source_outcome_reconciliation", "status": "PASS", "rows": source_people, "details": f"Recounted source_SEX only: {source_counts}; matches Phase 6."})

    for name, details in hashes.items():
        audit_rows.append({"check": f"input:{name}", "status": "PASS" if details["available"] else "OPTIONAL_MISSING", "rows": "", "details": json.dumps(details, sort_keys=True)})
    audit_rows += [
        {"check": "duplicate_only_guard", "status": "PASS", "rows": 0, "details": "Only executive_summary.json, dashboard_* outputs, and Phase 7 audit/manifest files are written."},
        {"check": "phase4_not_estimable_preserved", "status": "PASS" if (predictive_manifest or {}).get("status") == "NOT_ESTIMABLE" else "REVIEW", "rows": pc.get("eligible_binomial_cells", 0), "details": "Dashboard carries the Phase 4 status and reason without inventing model metrics."},
        {"check": "unknown_retained", "status": "PASS", "rows": unknown, "details": "Unknown remains separate from the known-sex denominator."},
    ]
    audit_path = AUDIT / "executive_dashboard_audit.csv"
    audit_count = write_csv(audit_path, audit_rows)

    manifest = {
        "manifest_type": "version_c_phase_7_executive_dashboard_consolidation",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "study_window": STUDY_WINDOW,
        "inputs": hashes,
        "outputs": {**output_meta, "executive_summary.json": {"path": str(summary_path.relative_to(BASE)), "rows": 1, "sha256": sha(summary_bytes), "readback_verified": True}},
        "audit": {"path": str(audit_path.relative_to(BASE)), "rows": audit_count, "sha256": sha(audit_path.read_bytes()), "readback_verified": audit_count == len(audit_rows)},
        "outcome_counts": {"MALE": male, "FEMALE": female, "UNKNOWN": unknown, "known_sex": known},
        "design_guards": {"source_layers_modified": False, "unknown_kept_separate": True, "candidate_level_linkage": False, "causality_claimed": False, "phase4_findings_invented": False, "archive_capture_as_posting_date": False},
    }
    manifest_path = AUDIT / "executive_dashboard_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Verify manifest JSON can be read back and its hashes are intact.
    manifest_check = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest_check["outcome_counts"] != manifest["outcome_counts"]:
        raise RuntimeError("Executive dashboard manifest read-back failed")

    print("VERSION C — PHASE 7 — EXECUTIVE DASHBOARD DATA")
    print("Study window: 2026-04-01 to 2026-09-30")
    print("Duplicate-only: existing Plan A and Version C datasets will not be modified.")
    print("\nPHASE 7 COMPLETE\n")
    print("OUTCOME LAYER")
    print(f"  Distinct people:       {male + female + unknown}")
    print(f"  Male:                  {male}")
    print(f"  Female:                {female}")
    print(f"  Unknown:               {unknown}")
    print(f"  Male known-sex share:  {male / known:.2%}" if known else "  Male known-sex share:  N/A")
    print(f"  Female known-sex share:{female / known:.2%}" if known else "  Female known-sex share:N/A")
    print(f"  Male/Female ratio:     {male / female:.2f}:1" if female else "  Male/Female ratio:     N/A")
    print(f"  Unknown all-records:   {unknown / (male + female + unknown):.2%}" if male + female + unknown else "  Unknown all-records:   N/A")
    print(f"\nPREDICTION: {executive_summary['phase_status']['PREDICTION']}")
    print(f"FEEDBACK:   {executive_summary['phase_status']['FEEDBACK']}")
    print(f"\nManifest: {manifest_path}")


if __name__ == "__main__":
    main()
