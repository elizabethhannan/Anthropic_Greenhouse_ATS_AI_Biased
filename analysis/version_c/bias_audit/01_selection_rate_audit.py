"""Version C — future internal employment selection-rate audit.

The public-data path documents missing applicant/stage denominators and does
not fabricate rates. If an authorized aggregate Greenhouse export is supplied,
the script validates it and computes stage-level 4/5ths-rule indicators.
These are screening indicators, not legal findings.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_PATH = Path(__file__).resolve()
VERSION_C_DIR = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[3]
WORK_DIR = SCRIPT_PATH.parent
INPUT_DIR = WORK_DIR / "inputs"
OUTPUT_DIR = WORK_DIR / "outputs"
AUDIT_DIR = WORK_DIR / "audit"
INPUT_FILE = INPUT_DIR / "internal_greenhouse_selection_data.parquet"
for directory in (INPUT_DIR, OUTPUT_DIR, AUDIT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

OUTCOMES = {"Male": 606, "Female": 276, "Unknown": 213}
TOTAL = 1095
KNOWN_MALE, KNOWN_FEMALE = 606, 276
KNOWN_TOTAL = KNOWN_MALE + KNOWN_FEMALE
MALE_SHARE = KNOWN_MALE / KNOWN_TOTAL
FEMALE_SHARE = KNOWN_FEMALE / KNOWN_TOTAL
MALE_FEMALE_RATIO = KNOWN_MALE / KNOWN_FEMALE
REQUIRED = ["stage", "demographic_group", "entered_count", "selected_count"]
STAGES = ["applicant_pool", "screened", "interviewed", "offered", "hired"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def canonical_group(value) -> str:
    value = normalize_text(value)
    if not value or value.lower() in {"unknown", "unspecified", "not specified", "not reported", "blank", "missing", "null"}:
        return "Unknown"
    normalized = {"m": "Male", "man": "Male", "male": "Male",
                  "f": "Female", "woman": "Female", "female": "Female"}
    return normalized.get(value.lower(), value)


def canonical_stage(value) -> str:
    value = normalize_text(value).lower()
    aliases = {
        "applicant": "applicant_pool", "applicants": "applicant_pool",
        "application": "applicant_pool", "applications": "applicant_pool",
        "applicant_pool": "applicant_pool", "screen": "screened", "screened": "screened",
        "interview": "interviewed", "interviewed": "interviewed",
        "offer": "offered", "offered": "offered", "hire": "hired", "hired": "hired",
    }
    return aliases.get(value, value)


def build_public_data_status() -> pd.DataFrame:
    available = [
        ("Male hires", True, 606, True, "Available"),
        ("Female hires", True, 276, True, "Available"),
        ("Unknown outcomes", True, 213, False, "Available; retained separately"),
        ("Distinct people", True, 1095, False, "Available"),
    ]
    unavailable = [
        (f"{group} {stage}", False, None, True, "Missing")
        for stage in ("applicants", "screened", "interviewed", "offered")
        for group in ("Male", "Female")
    ] + [("Candidate-stage demographic history", False, None, True, "Missing")]
    rows = available + unavailable
    return pd.DataFrame(rows, columns=["data_element", "available", "value", "required_for_adverse_impact", "current_status"])


def build_internal_data_requirements() -> pd.DataFrame:
    data = [
        (1, "Applicant demographic counts", "Applicant-pool denominator"),
        (2, "Screening-stage demographic counts", "Screening selection rate"),
        (3, "Interview-stage demographic counts", "Interview selection rate"),
        (4, "Offer-stage demographic counts", "Offer selection rate"),
        (5, "Hire-stage demographic counts", "Final selection rate"),
        (6, "Stage transition timestamps", "Temporal/funnel analysis"),
        (7, "Job/requisition identifier", "Role/requisition stratification"),
        (8, "Recruiting workflow / AI-assistance indicators", "Human-AI workflow audit"),
        (9, "Recruiter / hiring-manager decision events", "Human decision-path analysis"),
        (10, "AI recommendation and override logs", "AI-vs-human contribution analysis"),
    ]
    rows = [{"priority": i, "required_data": name,
             "male": "Required" if i <= 5 else "Preferred",
             "female": "Required" if i <= 5 else "Preferred",
             "unknown": "Retain separately", "purpose": purpose}
            for i, name, purpose in data]
    return pd.DataFrame(rows)


def load_internal_data():
    if not INPUT_FILE.exists():
        return None, {"status": "NOT_RUN_PUBLIC_DATA_MISSING_DENOMINATORS",
                      "reason": "No internal Greenhouse selection-stage dataset was provided. Public outcomes include hires only, not demographic applicant or stage denominators."}
    try:
        return pd.read_parquet(INPUT_FILE), {"status": "INPUT_FOUND", "reason": "Internal aggregate selection-stage dataset loaded."}
    except Exception as exc:
        return None, {"status": "INPUT_READ_ERROR", "reason": str(exc)}


def normalize_internal_data(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    aliases = {"group": "demographic_group", "sex": "demographic_group", "gender": "demographic_group",
               "entered": "entered_count", "entered_stage": "entered_count", "eligible_count": "entered_count",
               "population_count": "entered_count", "selected": "selected_count", "selection_count": "selected_count",
               "advance_count": "selected_count", "passed_count": "selected_count"}
    rename = {col: aliases[normalize_text(col).lower()] for col in working.columns if normalize_text(col).lower() in aliases}
    working = working.rename(columns=rename)
    missing = [col for col in REQUIRED if col not in working]
    if missing:
        raise ValueError("Missing required conceptual columns: " + ", ".join(missing))
    working["stage"] = working["stage"].map(canonical_stage)
    working["demographic_group"] = working["demographic_group"].map(canonical_group)
    for col in ("entered_count", "selected_count"):
        working[col] = pd.to_numeric(working[col], errors="coerce")
    return working


def validate_internal_data(frame: pd.DataFrame) -> pd.DataFrame:
    checks = []
    for col in REQUIRED:
        checks.append({"check": f"required_column:{col}", "status": "PASS" if col in frame else "FAIL",
                       "detail": "Column present." if col in frame else "Column missing."})
    entered_bad = frame["entered_count"].isna() | (frame["entered_count"] < 0)
    selected_bad = frame["selected_count"].isna() | (frame["selected_count"] < 0)
    exceeds = frame["selected_count"] > frame["entered_count"]
    checks += [
        {"check": "entered_count_valid", "status": "FAIL" if entered_bad.any() else "PASS", "detail": f"Invalid rows={int(entered_bad.sum())}"},
        {"check": "selected_count_valid", "status": "FAIL" if selected_bad.any() else "PASS", "detail": f"Invalid rows={int(selected_bad.sum())}"},
        {"check": "selected_not_greater_than_entered", "status": "FAIL" if exceeds.any() else "PASS", "detail": f"Invalid rows={int(exceeds.sum())}"},
    ]
    return pd.DataFrame(checks)


def calculate_selection_rates(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stage, group in frame.groupby("stage", dropna=False):
        comparisons = group[(group.demographic_group != "Unknown") & (group.entered_count > 0)].copy()
        if comparisons.empty:
            continue
        comparisons["selection_rate"] = comparisons.selected_count / comparisons.entered_count
        highest = comparisons.selection_rate.max()
        for _, row in comparisons.iterrows():
            ratio = float(row.selection_rate / highest) if highest > 0 else np.nan
            flag = pd.notna(ratio) and ratio < .80
            rows.append({"stage": stage, "demographic_group": row.demographic_group,
                         "entered_count": int(row.entered_count), "selected_count": int(row.selected_count),
                         "selection_rate": float(row.selection_rate), "highest_group_selection_rate": float(highest),
                         "impact_ratio_vs_highest_group": ratio,
                         "four_fifths_indicator": "POTENTIAL_FLAG" if flag else "NO_80_PERCENT_INDICATOR",
                         "interpretation": "Initial adverse-impact indicator only; not a legal finding." if flag else "No 4/5ths indicator at this stage."})
    return pd.DataFrame(rows)


def build_adverse_impact_summary(selection_rates: pd.DataFrame) -> pd.DataFrame:
    if selection_rates.empty:
        return pd.DataFrame([{"status": "NOT_ESTIMABLE_FROM_CURRENT_PUBLIC_DATA",
            "reason": "Selection-rate analysis requires demographic denominators at each employment-selection stage.",
            "male_hires_current_public_data": KNOWN_MALE, "female_hires_current_public_data": KNOWN_FEMALE,
            "unknown_current_public_data": OUTCOMES["Unknown"], "known_sex_male_share": MALE_SHARE,
            "known_sex_female_share": FEMALE_SHARE, "male_female_ratio": MALE_FEMALE_RATIO}])
    rows = []
    for stage, group in selection_rates.groupby("stage"):
        rates = {r.demographic_group: r.selection_rate for _, r in group.iterrows()}
        if "Male" in rates and "Female" in rates:
            ref = max(rates["Male"], rates["Female"])
            ref_group = "Male" if rates["Male"] >= rates["Female"] else "Female"
            cmp_group = "Female" if ref_group == "Male" else "Male"
            impact = rates[cmp_group] / ref if ref > 0 else np.nan
            flag = pd.notna(impact) and impact < .8
        else:
            ref_group = cmp_group = None
            ref = impact = np.nan
            flag = False
        rows.append({"stage": stage, "reference_group": ref_group, "reference_selection_rate": ref,
                     "comparison_group": cmp_group, "comparison_selection_rate": rates.get(cmp_group, np.nan),
                     "impact_ratio": impact, "four_fifths_indicator": "POTENTIAL_FLAG" if flag else ("NO_80_PERCENT_INDICATOR" if cmp_group else "INSUFFICIENT_GROUP_DATA"),
                     "legal_interpretation": "Not a legal determination; requires contextual analysis under applicable law and selection-procedure guidance."})
    return pd.DataFrame(rows)


def main() -> int:
    started = utc_now()
    print("\n" + "=" * 68)
    print("VERSION C — EMPLOYMENT SELECTION / ADVERSE-IMPACT AUDIT")
    print("=" * 68)
    print("\nCURRENT PUBLIC OUTCOME")
    print("----------------------")
    print(f"MALE:             {KNOWN_MALE}\nFEMALE:           {KNOWN_FEMALE}\nUNKNOWN:          {OUTCOMES['Unknown']}\nDISTINCT PEOPLE:  {TOTAL}")
    print(f"KNOWN SEX:        {MALE_SHARE*100:.1f}% / {FEMALE_SHARE*100:.1f}%\nMALE/FEMALE:      {MALE_FEMALE_RATIO:.2f}:1\n")

    public_status_path = OUTPUT_DIR / "public_data_selection_requirements.csv"
    requirements_path = OUTPUT_DIR / "future_internal_data_requirements.csv"
    build_public_data_status().to_csv(public_status_path, index=False)
    build_internal_data_requirements().to_csv(requirements_path, index=False)
    frame, load = load_internal_data()
    outputs = [str(public_status_path), str(requirements_path)]

    if frame is None:
        status_value = "NOT_ESTIMABLE_FROM_CURRENT_PUBLIC_DATA" if load["status"] == "NOT_RUN_PUBLIC_DATA_MISSING_DENOMINATORS" else load["status"]
        summary = pd.DataFrame([{"status": status_value, "adverse_impact_test_performed": False,
            "selection_rate_test_performed": False, "male_hires": KNOWN_MALE, "female_hires": KNOWN_FEMALE,
            "unknown": OUTCOMES["Unknown"], "distinct_people": TOTAL, "male_share_known": MALE_SHARE,
            "female_share_known": FEMALE_SHARE, "male_female_ratio": MALE_FEMALE_RATIO, "reason": load["reason"]}])
        summary_path = OUTPUT_DIR / "adverse_impact_summary.csv"
        summary.to_csv(summary_path, index=False); outputs.append(str(summary_path))
        status = {"status": status_value, "run_timestamp_utc": started, "reason": load["reason"],
                  "current_public_outcome": OUTCOMES, "current_public_total": TOTAL,
                  "known_sex_male_share": MALE_SHARE, "known_sex_female_share": FEMALE_SHARE,
                  "male_female_ratio": MALE_FEMALE_RATIO, "adverse_impact_test_performed": False,
                  "selection_rate_test_performed": False, "sex_inference": False,
                  "candidate_level_greenhouse_linkage": False, "synthetic_candidates": False,
                  "greenhouse_causal_claim": False, "plan_a_modified": False,
                  "future_tests_retained": ["03_statistical_significance.py", "08_human_ai_workflow_audit.py"],
                  "executive_interpretation": "Observed Male/Female hiring composition identifies representation disparity but does not establish adverse impact without demographic applicant and stage denominators."}
        status_path = OUTPUT_DIR / "selection_audit_status.json"
        write_json(status_path, status); outputs.append(str(status_path))
        audit_rows = [
            ("public_data_adverse_impact_gate", "Correctly refused to calculate adverse impact without applicant/stage denominators."),
            ("sex_inference", "No sex inference performed."),
            ("unknown_handling", "Unknown remains Unknown; no reassignment."),
            ("candidate_linkage", "No candidate-level Greenhouse-to-hire linkage created."),
            ("synthetic_candidates", "No synthetic candidate records created."),
            ("greenhouse_causality", "No causal claim about Greenhouse."),
            ("plan_a_integrity", "Plan A datasets were not modified."),
        ]
        audit_df = pd.DataFrame([{"check": k, "status": "PASS", "detail": v} for k, v in audit_rows])
        audit_path = AUDIT_DIR / "selection_audit_audit.csv"
        audit_df.to_csv(audit_path, index=False); outputs.append(str(audit_path))
        manifest = {"run_timestamp_utc": started, "script": str(SCRIPT_PATH), "workstream": "bias_audit",
                    "audit_type": "employment_selection_rate_adverse_impact", "status": status_value,
                    "input_file": str(INPUT_FILE), "input_exists": False, "outputs": outputs,
                    "current_public_outcomes": OUTCOMES,
                    "controls": {"sex_inference": False, "candidate_level_greenhouse_linkage": False,
                        "synthetic_candidates": False, "greenhouse_causal_claim": False, "plan_a_modified": False},
                    "future_tests": ["03_statistical_significance.py", "08_human_ai_workflow_audit.py"]}
        manifest_path = AUDIT_DIR / "selection_audit_manifest.json"
        write_json(manifest_path, manifest)
        print("EMPLOYMENT SELECTION TEST\n-------------------------")
        print("STATUS: NOT ESTIMABLE FROM CURRENT PUBLIC DATA\n")
        print("Reason: applicant and candidate-stage demographic denominators are not available.\n")
        print("NO ADVERSE-IMPACT RATE WAS FABRICATED.\nNO 4/5THS RESULT WAS FABRICATED.\n")
        print(f"FUTURE INTERNAL DATA REQUIREMENTS SAVED:\n{requirements_path}\n")
        print(f"STATUS:\n{status_path}\n\nAUDIT:\n{audit_path}\n\nMANIFEST:\n{manifest_path}\n")
        print("=" * 68)
        return 0

    try:
        normalized = normalize_internal_data(frame)
    except Exception as exc:
        status_path = OUTPUT_DIR / "selection_audit_status.json"
        write_json(status_path, {"status": "INPUT_SCHEMA_ERROR", "run_timestamp_utc": started,
                                 "input_file": str(INPUT_FILE), "error": str(exc)})
        print(f"STATUS: INPUT SCHEMA ERROR\n{exc}\nSTATUS FILE: {status_path}")
        return 1
    validation = validate_internal_data(normalized)
    validation_path = AUDIT_DIR / "internal_selection_data_validation.csv"
    validation.to_csv(validation_path, index=False)
    if (validation.status == "FAIL").any():
        status_path = OUTPUT_DIR / "selection_audit_status.json"
        failures = validation[validation.status == "FAIL"].to_dict(orient="records")
        write_json(status_path, {"status": "INPUT_VALIDATION_FAILED", "run_timestamp_utc": started,
                                 "input_file": str(INPUT_FILE), "validation_failures": failures})
        print("STATUS: INPUT VALIDATION FAILED\n" + validation.to_string(index=False))
        return 1

    rates = calculate_selection_rates(normalized)
    rates_path = OUTPUT_DIR / "stage_selection_rates.csv"
    rates.to_csv(rates_path, index=False)
    summary = build_adverse_impact_summary(rates)
    summary_path = OUTPUT_DIR / "adverse_impact_summary.csv"
    summary.to_csv(summary_path, index=False)
    potential = int((rates.get("four_fifths_indicator", pd.Series(dtype=str)) == "POTENTIAL_FLAG").sum())
    status = {"status": "COMPUTED_WITH_INTERNAL_SELECTION_DATA", "run_timestamp_utc": started,
              "input_file": str(INPUT_FILE), "input_sha256": sha256_file(INPUT_FILE),
              "selection_rate_test_performed": True, "adverse_impact_indicator_calculated": True,
              "potential_four_fifths_indicators": potential, "current_public_outcomes": OUTCOMES,
              "sex_inference": False, "candidate_level_greenhouse_linkage": False,
              "synthetic_candidates": False, "greenhouse_causal_claim": False, "plan_a_modified": False,
              "interpretation_control": "The 4/5ths calculation is an initial adverse-impact indicator, not a legal determination."}
    status_path = OUTPUT_DIR / "selection_audit_status.json"
    write_json(status_path, status)
    audit_path = AUDIT_DIR / "selection_audit_audit.csv"
    pd.DataFrame([{"check": k, "status": "PASS", "detail": d} for k, d in [
        ("internal_data_loaded", "Aggregate selection-stage dataset loaded."),
        ("schema_validation", "Required conceptual fields validated."),
        ("selection_rates_calculated", f"{len(rates)} stage/group rates calculated."),
        ("unknown_handling", "Unknown remains separate."),
        ("no_inference_or_linkage", "No inference, synthetic records, or posting-to-person link created."),
        ("four_fifths_interpretation", "Indicator only, not a legal finding."),
        ("plan_a_integrity", "Plan A datasets were not modified.")]]).to_csv(audit_path, index=False)
    manifest_path = AUDIT_DIR / "selection_audit_manifest.json"
    write_json(manifest_path, {"run_timestamp_utc": started, "status": status["status"],
        "input_file": str(INPUT_FILE), "input_sha256": sha256_file(INPUT_FILE),
        "outputs": [str(rates_path), str(summary_path), str(status_path), str(validation_path), str(audit_path)],
        "controls": {"sex_inference": False, "candidate_level_greenhouse_linkage": False,
                     "synthetic_candidates": False, "greenhouse_causal_claim": False, "plan_a_modified": False}})
    print("SELECTION-RATE ANALYSIS\n-----------------------")
    print(f"Records: {len(rates)}\n")
    if not rates.empty:
        cols = ["stage", "demographic_group", "entered_count", "selected_count", "selection_rate", "impact_ratio_vs_highest_group", "four_fifths_indicator"]
        print(rates[cols].to_string(index=False))
    print("\nADVERSE-IMPACT SUMMARY\n----------------------")
    print(summary.to_string(index=False))
    print("\nOUTPUTS\n-------")
    for label, path in [("Selection rates", rates_path), ("Summary", summary_path), ("Status", status_path),
                        ("Validation", validation_path), ("Audit", audit_path), ("Manifest", manifest_path)]:
        print(f"{label}: {path}")
    print("\n4/5THS INDICATORS ARE SCREENING FLAGS, NOT LEGAL FINDINGS.\n" + "=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
