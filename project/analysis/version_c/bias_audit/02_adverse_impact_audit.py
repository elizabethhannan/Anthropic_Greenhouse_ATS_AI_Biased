"""Step 02 — audit adverse-impact readiness from Step 01 outputs.

This is an audit/readiness layer. It consumes Step 01 artifacts, never creates
applicant denominators, and does not make a legal finding. If a later Step 01
run contains internal aggregate stage counts, this script verifies which
stage-level comparisons are calculable and audits their indicators.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEP1_OUT = HERE / "outputs"
STEP1_AUDIT = HERE / "audit"
OUT = STEP1_OUT / "step02_adverse_impact_audit"
AUDIT = STEP1_AUDIT / "step02_adverse_impact_audit"

STATUS_FILE = STEP1_OUT / "selection_audit_status.json"
SUMMARY_FILE = STEP1_OUT / "adverse_impact_summary.csv"
PUBLIC_DATA_FILE = STEP1_OUT / "public_data_selection_requirements.csv"
INTERNAL_REQ_FILE = STEP1_OUT / "future_internal_data_requirements.csv"
STEP1_AUDIT_FILE = STEP1_AUDIT / "selection_audit_audit.csv"
RATES_FILE = STEP1_OUT / "stage_selection_rates.csv"
STEP1_MANIFEST_FILE = STEP1_AUDIT / "selection_audit_manifest.json"

EXPECTED = {"Male": 606, "Female": 276, "Unknown": 213}
EXPECTED_TOTAL = 1095
STAGES = ["applicant_pool", "screened", "interviewed", "offered", "hired"]
REQUIRED_RATE_FIELDS = {"stage", "demographic_group", "entered_count", "selected_count",
                        "selection_rate", "impact_ratio_vs_highest_group", "four_fifths_indicator"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def check(checks: list[dict], name: str, ok: bool, detail: str) -> None:
    checks.append({"check_id": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def number(value: str) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def build_readiness(rates: list[dict[str, str]] | None) -> list[dict]:
    rows = []
    by_stage: dict[str, list[dict[str, str]]] = {stage: [] for stage in STAGES}
    for row in rates or []:
        stage = row.get("stage", "")
        if stage in by_stage:
            by_stage[stage].append(row)
    for stage in STAGES:
        stage_rows = by_stage[stage]
        groups = {r.get("demographic_group", "") for r in stage_rows}
        male = "Male" in groups
        female = "Female" in groups
        if not stage_rows:
            state = "NOT_CALCULABLE_NO_INTERNAL_STAGE_COUNTS"
        elif male and female:
            state = "COMPARISON_CALCULABLE_FROM_STEP01_AGGREGATES"
        else:
            state = "PARTIAL_DATA_MISSING_MALE_OR_FEMALE_GROUP"
        rows.append({
            "stage": stage,
            "step01_rates_present": bool(stage_rows),
            "male_group_present": male,
            "female_group_present": female,
            "selection_rates_calculable": bool(stage_rows),
            "male_female_impact_ratio_calculable": male and female,
            "readiness_status": state,
            "data_requirement": "entered_count and selected_count by reported demographic group; retain Unknown separately",
            "interpretation_limit": "A 4/5ths indicator is a screening signal, not a legal finding.",
        })
    return rows


def main() -> int:
    required = [STATUS_FILE, SUMMARY_FILE, PUBLIC_DATA_FILE, INTERNAL_REQ_FILE, STEP1_AUDIT_FILE, STEP1_MANIFEST_FILE]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise SystemExit("Step 01 artifacts missing: " + "; ".join(missing))
    step1_status = read_json(STATUS_FILE)
    step1_summary = read_csv(SUMMARY_FILE)
    public_rows = read_csv(PUBLIC_DATA_FILE)
    requirement_rows = read_csv(INTERNAL_REQ_FILE)
    step1_checks = read_csv(STEP1_AUDIT_FILE)
    step1_manifest = read_json(STEP1_MANIFEST_FILE)
    rates = read_csv(RATES_FILE) if RATES_FILE.is_file() else None

    checks: list[dict] = []
    outcome_ok = step1_status.get("current_public_outcome") == EXPECTED and step1_status.get("current_public_total") == EXPECTED_TOTAL
    check(checks, "step01_canonical_outcomes", outcome_ok,
          f"outcomes={step1_status.get('current_public_outcome')}; total={step1_status.get('current_public_total')}")
    public_status_only = (step1_status.get("status") == "NOT_ESTIMABLE_FROM_CURRENT_PUBLIC_DATA"
                          and step1_status.get("selection_rate_test_performed") is False
                          and step1_status.get("adverse_impact_test_performed") is False)
    internal_status = (step1_status.get("status") == "COMPUTED_WITH_INTERNAL_SELECTION_DATA"
                       and step1_status.get("selection_rate_test_performed") is True)
    no_public_rate = public_status_only or internal_status
    check(checks, "public_data_gate_not_estimable", no_public_rate,
          f"Public-only data remain non-estimable; Step 01 status={step1_status.get('status')}; internal selection-rate test={step1_status.get('selection_rate_test_performed')}")
    available_missing = [r.get("data_element") for r in public_rows
                         if r.get("required_for_adverse_impact", "").lower() == "true"
                         and r.get("available", "").lower() != "true"]
    check(checks, "required_public_denominators_missing", bool(available_missing),
          "Missing required denominators: " + "; ".join(available_missing))
    summary_status = step1_summary[0].get("status") if step1_summary else ""
    check(checks, "step01_summary_status_consistent",
          (public_status_only and summary_status == "NOT_ESTIMABLE_FROM_CURRENT_PUBLIC_DATA")
          or (internal_status and summary_status != "NOT_ESTIMABLE_FROM_CURRENT_PUBLIC_DATA"),
          f"Step 01 summary status={summary_status}")
    step1_failures = [r for r in step1_checks if r.get("status") == "FAIL"]
    check(checks, "step01_audit_has_no_failures", not step1_failures,
          f"Step 01 failed audit checks={len(step1_failures)}")
    check(checks, "future_requirements_documented", len(requirement_rows) >= len(STAGES),
          f"Future internal data requirement rows={len(requirement_rows)}")
    check(checks, "unknown_retained_separately", EXPECTED["Unknown"] == 213 and
          any(r.get("data_element") == "Unknown outcomes" and r.get("available", "").lower() == "true" for r in public_rows),
          "UNKNOWN=213; it remains a separate reported category.")

    rate_schema_ok = rates is not None and bool(rates) and REQUIRED_RATE_FIELDS <= set(rates[0])
    check(checks, "internal_rate_table_schema", rates is None or not rates or rate_schema_ok,
          "No Step 01 internal stage-rate table exists yet." if rates is None else f"Required fields present={rate_schema_ok}")
    rate_errors = []
    if rates and rate_schema_ok:
        for idx, row in enumerate(rates, start=2):
            entered, selected, rate, impact = [number(row.get(k)) for k in
                ("entered_count", "selected_count", "selection_rate", "impact_ratio_vs_highest_group")]
            if None in (entered, selected, rate) or entered <= 0 or selected < 0 or selected > entered:
                rate_errors.append(f"row {idx}: invalid counts/rate")
                continue
            if not math.isclose(rate, selected / entered, rel_tol=1e-8, abs_tol=1e-8):
                rate_errors.append(f"row {idx}: selection_rate does not reconcile")
            if impact is not None and not 0 <= impact <= 1 + 1e-8:
                rate_errors.append(f"row {idx}: impact ratio outside [0,1]")
            expected_flag = "POTENTIAL_FLAG" if impact is not None and impact < .80 else "NO_80_PERCENT_INDICATOR"
            if row.get("four_fifths_indicator") != expected_flag:
                rate_errors.append(f"row {idx}: indicator does not match ratio")
    check(checks, "step01_rates_reconcile", not rate_errors,
          "No rates supplied; nothing to reconcile." if rates is None else "; ".join(rate_errors) if rate_errors else f"Validated {len(rates)} stage/group rate rows.")

    readiness = build_readiness(rates)
    readiness_path = OUT / "adverse_impact_readiness_by_stage.csv"
    write_csv(readiness_path, readiness, list(readiness[0]))
    present = bool(rates)
    future_calc = any(r["male_female_impact_ratio_calculable"] for r in readiness)
    result_state = "PUBLIC_DATA_NOT_ESTIMABLE_INTERNAL_DATA_NOT_PROVIDED"
    if present:
        result_state = "INTERNAL_STAGE_DATA_AUDITED" if not rate_errors else "INTERNAL_RATE_AUDIT_FAILED"
    public_outcome = {
        "status": result_state,
        "public_adverse_impact_calculable": False,
        "future_internal_rates_present": present,
        "future_male_female_impact_ratio_calculable_at_any_stage": future_calc,
        "current_public_outcomes": EXPECTED,
        "current_public_total": EXPECTED_TOTAL,
        "required_denominators_missing": available_missing,
        "four_fifths_threshold": 0.80,
        "four_fifths_interpretation": "Screening indicator only; not a legal finding.",
        "no_fabricated_denominators": True,
        "sex_inference": False,
        "unknown_collapsed": False,
        "candidate_level_linkage_created": False,
        "greenhouse_causal_claim": False,
        "plan_a_modified": False,
        "next_instrumentation": ["stage", "demographic_group", "entered_count", "selected_count"],
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    status_path = OUT / "adverse_impact_audit_status.json"
    status_path.write_text(json.dumps(public_outcome, indent=2) + "\n", encoding="utf-8")

    # The audit checks whether Step 01 did what it claimed and whether its
    # future aggregate rates reconcile. A missing internal file is expected.
    checks_path = AUDIT / "adverse_impact_audit_checks.csv"
    write_csv(checks_path, checks, ["check_id", "status", "detail"])
    failures = [r for r in checks if r["status"] == "FAIL"]
    overall = "PASS" if not failures else "FAIL"
    manifest_path = AUDIT / "adverse_impact_audit_manifest.json"
    manifest = {
        "step": 2, "name": "Adverse Impact Audit Gate", "status": overall,
        "audit_result": result_state, "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "step01_manifest_status": step1_manifest.get("status"),
        "inputs": {str(p.relative_to(HERE)): sha256(p) for p in required if p.is_file()},
        "internal_stage_rate_file_present": RATES_FILE.is_file(),
        "outputs": {"readiness_by_stage": {"path": str(readiness_path.relative_to(HERE)), "sha256": sha256(readiness_path)},
                    "status": {"path": str(status_path.relative_to(HERE)), "sha256": sha256(status_path)},
                    "checks": {"path": str(checks_path.relative_to(HERE)), "sha256": sha256(checks_path)}},
        "check_count": len(checks), "failures": len(failures),
        "legal_finding": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("VERSION C — STEP 02 ADVERSE IMPACT AUDIT")
    print("=" * 64)
    print(f"AUDIT STATUS: {overall}")
    print("PUBLIC-DATA ADVERSE IMPACT: NOT ESTIMABLE")
    print(f"STEP 01 STATUS: {step1_status.get('status')}")
    print(f"CANONICAL OUTCOMES: Male {EXPECTED['Male']} / Female {EXPECTED['Female']} / Unknown {EXPECTED['Unknown']} / N={EXPECTED_TOTAL}")
    print(f"MISSING REQUIRED DENOMINATORS: {len(available_missing)}")
    for item in available_missing:
        print(f"  - {item}")
    print(f"INTERNAL STAGE-RATE TABLE PRESENT: {'YES' if present else 'NO'}")
    if present:
        print("FUTURE STAGE READINESS:")
        for row in readiness:
            print(f"  {row['stage']}: {row['readiness_status']}")
    print("NO APPLICANT COUNTS OR ADVERSE-IMPACT RATES WERE FABRICATED.")
    print("4/5THS INDICATOR: SCREENING TOOL ONLY; NOT A LEGAL FINDING.")
    print(f"READINESS: {readiness_path}")
    print(f"STATUS: {status_path}")
    print(f"CHECKS: {checks_path}")
    print(f"MANIFEST: {manifest_path}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
