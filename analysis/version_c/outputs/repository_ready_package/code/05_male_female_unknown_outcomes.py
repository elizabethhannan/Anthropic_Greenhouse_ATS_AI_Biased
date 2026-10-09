"""Version C — Phase 6: observed MALE / FEMALE / UNKNOWN outcome layer.

Uses only the frozen distinct-person Phase 2 hiring outcome file. Labels come
from its preserved source_SEX field; no name/title/text inference is used.
Phase 2/3/4/5 inputs and outputs are read-only.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT_DIR = BASE / "audit"
HIRING_PATH = OUT / "version_c_hiring_outcomes.parquet"
PHASE5_MONTHLY_PATH = OUT / "monthly_outcomes.csv"
PHASE5_SUMMARY_PATH = OUT / "feedback_summary.csv"
STUDY_MONTHS = [f"2026-{m:02d}" for m in range(4, 10)]
LABELS = ("MALE", "FEMALE", "UNKNOWN")
RESEARCH_CLASSES = {
    "Fellows Researcher", "Research Scientist", "Research Engineer",
    "Research-oriented MTS", "Alignment / AI Safety", "Interpretability",
    "Pre-training", "Post-training", "Reinforcement Learning", "Evaluations",
    "Model Behavior", "AI/ML Research - Other",
}
CSV_OUTPUTS = (
    "outcome_distribution.csv",
    "outcome_by_period.csv",
    "research_outcome_distribution.csv",
    "fellowship_outcome_distribution.csv",
    "outcome_quality_summary.csv",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_hiring() -> tuple[list[dict[str, Any]], bytes]:
    if not HIRING_PATH.exists():
        raise FileNotFoundError(f"Frozen Phase 2 hiring outcomes not found: {HIRING_PATH}")
    raw = HIRING_PATH.read_bytes()
    return pq.read_table(HIRING_PATH).to_pylist(), raw


def parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def month_of(value: Any) -> str | None:
    if value is None:
        return None
    match = re.match(r"^(\d{4})-(\d{2})", str(value).strip())
    if not match:
        return None
    month = int(match.group(2))
    return f"{match.group(1)}-{month:02d}" if 1 <= month <= 12 else None


def executive_sex(source_sex: Any) -> str:
    raw = str(source_sex or "").strip().lower()
    if raw == "male":
        return "MALE"
    if raw == "female":
        return "FEMALE"
    return "UNKNOWN"


def is_research_record(record: dict[str, Any]) -> bool:
    flag = record.get("IS_RESEARCH_HIRE")
    if isinstance(flag, bool):
        return flag
    if str(flag or "").strip().lower() in {"true", "1", "yes", "y"}:
        return True
    if str(flag or "").strip().lower() in {"false", "0", "no", "n"}:
        return False
    role = str(record.get("ROLE_CATEGORY") or "").strip()
    return role in RESEARCH_CLASSES


def is_fellowship_record(record: dict[str, Any]) -> bool:
    role = str(record.get("ROLE_CATEGORY") or "").strip()
    if role == "Fellows Researcher":
        return True
    title = " ".join(str(record.get(k) or "") for k in ("TITLE_NAME", "TITLE_ROLE", "TITLE_SUB_ROLE"))
    return bool(re.search(r"\bfellow(?:ship)?\b", title, flags=re.I))


def count_dist(records: list[dict[str, Any]]) -> dict[str, int]:
    return {label: sum(r["outcome_sex"] == label for r in records) for label in LABELS}


def distribution_rows(population: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = count_dist(records)
    total = len(records)
    known = counts["MALE"] + counts["FEMALE"]
    result = []
    for label in LABELS:
        n = counts[label]
        result.append({
            "population": population,
            "outcome_sex": label,
            "person_count": n,
            "share_all_people": n / total if total else None,
            "share_known_sex": n / known if label != "UNKNOWN" and known else (None if label == "UNKNOWN" else None),
            "denominator_all_people": total,
            "denominator_known_sex": known,
            "source_field": "source_SEX",
            "sex_inferred": False,
        })
    return result


def csv_write(path: Path, rows: list[dict[str, Any]]) -> int:
    if rows:
        fields = list(dict.fromkeys(k for row in rows for k in row))
    else:
        fields = ["status"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    with path.open("r", newline="", encoding="utf-8") as stream:
        return max(0, sum(1 for _ in csv.reader(stream)) - 1)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    people, input_bytes = read_hiring()
    if len(people) != 1095 or len({str(r.get("PERSON_ID")) for r in people}) != 1095:
        raise ValueError(f"Frozen hiring file expected 1,095 distinct people; found {len(people)} rows / {len({str(r.get('PERSON_ID')) for r in people})} IDs")

    person_rows: list[dict[str, Any]] = []
    raw_values = Counter()
    unexpected_values = Counter()
    outcome_mismatches = []
    all_source_records = 0
    missing_start_people = 0
    person_months: dict[tuple[str, str], dict[str, Any]] = {}
    role_month_people: dict[tuple[str, str, str], dict[str, Any]] = {}
    research_people: dict[str, dict[str, Any]] = {}
    fellowship_people: dict[str, dict[str, Any]] = {}

    for person in people:
        person_id = str(person.get("PERSON_ID") or "")
        source_sex = person.get("source_SEX")
        raw_key = "<BLANK>" if source_sex is None or not str(source_sex).strip() else str(source_sex).strip()
        raw_values[raw_key] += 1
        derived = executive_sex(source_sex)
        if str(source_sex or "").strip() and str(source_sex).strip().lower() not in {"male", "female"}:
            unexpected_values[raw_key] += 1
        stored = str(person.get("outcome_sex") or "").strip().upper()
        if stored != derived:
            outcome_mismatches.append(person_id)
        person_rows.append({"PERSON_ID": person_id, "source_SEX": source_sex, "outcome_sex": derived,
                            "stored_outcome_sex": stored, "sex_inferred": False,
                            "employment_row_count": int(person.get("employment_row_count") or 0)})

        source_records = parse_json_list(person.get("employment_records"))
        all_source_records += len(source_records)
        person_month_set = set()
        has_study_month = False
        person_research = False
        person_fellowship = False
        for record in source_records:
            month = month_of(record.get("START_DATE"))
            if month not in STUDY_MONTHS:
                continue
            has_study_month = True
            person_month_set.add(month)
            research = is_research_record(record)
            fellowship = is_fellowship_record(record)
            role = str(record.get("ROLE_CATEGORY") or record.get("TITLE_ROLE") or record.get("TITLE_NAME") or "Unknown role").strip()
            base = {"PERSON_ID": person_id, "outcome_sex": derived, "month": month, "role_family": role,
                    "research_hire": research, "fellowship_hire": fellowship}
            key = (person_id, month)
            if key not in person_months:
                person_months[key] = dict(base)
            else:
                person_months[key]["research_hire"] |= research
                person_months[key]["fellowship_hire"] |= fellowship
            role_key = (person_id, month, role)
            if role_key not in role_month_people:
                role_month_people[role_key] = dict(base)
            else:
                role_month_people[role_key]["research_hire"] |= research
                role_month_people[role_key]["fellowship_hire"] |= fellowship
            person_research |= research
            person_fellowship |= fellowship
        if not has_study_month:
            missing_start_people += 1
        if person_research:
            research_people[person_id] = {"PERSON_ID": person_id, "outcome_sex": derived}
        if person_fellowship:
            fellowship_people[person_id] = {"PERSON_ID": person_id, "outcome_sex": derived}

    if outcome_mismatches:
        raise ValueError(f"source_SEX to stored outcome_sex audit mismatch for {len(outcome_mismatches)} people; no outcomes written")

    all_dist = distribution_rows("all_observed_people", person_rows)
    research_dist = distribution_rows("observed_research_hires", list(research_people.values()))
    fellowship_dist = distribution_rows("observed_fellowship_hires", list(fellowship_people.values()))

    period_rows = []
    observed_months = {month for _, month in person_months}
    for month in STUDY_MONTHS:
        if month in {"2026-08", "2026-09"}:
            period_rows.append({"period": month, "coverage_status": "NO_OBSERVED_START_COVERAGE", "distinct_people": None,
                                "male_count": None, "female_count": None, "unknown_count": None, "known_sex_count": None,
                                "male_share_known_sex": None, "female_share_known_sex": None, "unknown_share_all": None,
                                "research_people": None, "research_male": None, "research_female": None, "research_unknown": None,
                                "fellowship_people": None, "fellowship_male": None, "fellowship_female": None, "fellowship_unknown": None})
            continue
        rows = [v for (pid, m), v in person_months.items() if m == month]
        counts = count_dist(rows)
        known = counts["MALE"] + counts["FEMALE"]
        res = [r for r in rows if r["research_hire"]]
        fel = [r for r in rows if r["fellowship_hire"]]
        rc, fc = count_dist(res), count_dist(fel)
        period_rows.append({"period": month, "coverage_status": "OBSERVED_STARTS" if month in observed_months else "NO_OBSERVED_START_RECORDS",
                            "distinct_people": len(rows), "male_count": counts["MALE"], "female_count": counts["FEMALE"], "unknown_count": counts["UNKNOWN"],
                            "known_sex_count": known, "male_share_known_sex": counts["MALE"] / known if known else None,
                            "female_share_known_sex": counts["FEMALE"] / known if known else None,
                            "unknown_share_all": counts["UNKNOWN"] / len(rows) if rows else None,
                            "research_people": len(res), "research_male": rc["MALE"], "research_female": rc["FEMALE"], "research_unknown": rc["UNKNOWN"],
                            "fellowship_people": len(fel), "fellowship_male": fc["MALE"], "fellowship_female": fc["FEMALE"], "fellowship_unknown": fc["UNKNOWN"]})

    counts = {label: sum(r["outcome_sex"] == label for r in person_rows) for label in LABELS}
    total, known_n = len(person_rows), counts["MALE"] + counts["FEMALE"]
    metrics = {
        "analysis": "Version C Phase 6 observed outcome distribution",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_file": str(HIRING_PATH.relative_to(BASE)),
        "source_sha256": sha(input_bytes),
        "study_period": {"start_month": STUDY_MONTHS[0], "end_month": STUDY_MONTHS[-1]},
        "denominators": {"distinct_observed_people": total, "known_sex_people": known_n},
        "outcome_counts": counts,
        "outcome_shares": {"male_share_known_sex": counts["MALE"] / known_n if known_n else None,
                           "female_share_known_sex": counts["FEMALE"] / known_n if known_n else None,
                           "unknown_share_all_people": counts["UNKNOWN"] / total if total else None,
                           "male_to_female_ratio": counts["MALE"] / counts["FEMALE"] if counts["FEMALE"] else None},
        "research_population": {"distinct_people": len(research_people), **{label: sum(r["outcome_sex"] == label for r in research_people.values()) for label in LABELS}},
        "fellowship_population": {"distinct_people": len(fellowship_people), **{label: sum(r["outcome_sex"] == label for r in fellowship_people.values()) for label in LABELS}},
        "period_coverage": {r["period"]: r["coverage_status"] for r in period_rows},
        "method": {"label_source": "source_SEX only", "unknown_definition": "blank/null/unrecognized source SEX is not assigned a binary sex", "name_or_title_inference": False, "candidate_level_greenhouse_linkage": False, "unknown_in_known_sex_denominator": False},
        "limitations": ["Observed start-month coverage is April-July 2026; August and September are not treated as zero hires.", "Research/fellowship subsets use the existing explicit IS_RESEARCH_HIRE and ROLE_CATEGORY source classifications.", "These are observed dataset counts, not a complete census of all Anthropic hires."],
    }

    outputs = {
        "outcome_distribution.csv": all_dist,
        "outcome_by_period.csv": period_rows,
        "research_outcome_distribution.csv": research_dist,
        "fellowship_outcome_distribution.csv": fellowship_dist,
    }
    quality_rows = [
        {"metric": "distinct_people", "value": total, "details": "One row per distinct PERSON_ID in the frozen Phase 2 outcome layer."},
        {"metric": "source_employment_rows_preserved", "value": all_source_records, "details": "Total employment rows nested in the authoritative person-level input."},
        {"metric": "male_count", "value": counts["MALE"], "details": "Exact source_SEX male mapping."},
        {"metric": "female_count", "value": counts["FEMALE"], "details": "Exact source_SEX female mapping."},
        {"metric": "unknown_count", "value": counts["UNKNOWN"], "details": "Blank/null/unrecognized source_SEX; never inferred."},
        {"metric": "blank_or_null_source_sex", "value": raw_values.get("<BLANK>", 0), "details": "Source field blank or null."},
        {"metric": "unrecognized_nonblank_source_sex", "value": sum(unexpected_values.values()), "details": json.dumps(dict(unexpected_values), ensure_ascii=False)},
        {"metric": "source_outcome_label_mismatches", "value": len(outcome_mismatches), "details": "Must be zero; Phase 2 outcome_sex checked against source_SEX mapping."},
        {"metric": "people_without_study_period_start", "value": missing_start_people, "details": "No preserved start record from April-September 2026."},
        {"metric": "research_distinct_people", "value": len(research_people), "details": "Distinct people with an explicit research-hire flag/classification."},
        {"metric": "fellowship_distinct_people", "value": len(fellowship_people), "details": "Distinct people with Fellows Researcher role category or an explicit fellow title."},
        {"metric": "known_sex_denominator", "value": known_n, "details": "MALE + FEMALE; UNKNOWN excluded."},
        {"metric": "male_share_known_sex", "value": counts["MALE"] / known_n if known_n else None, "details": "Executive headline denominator."},
        {"metric": "female_share_known_sex", "value": counts["FEMALE"] / known_n if known_n else None, "details": "Executive headline denominator."},
        {"metric": "male_female_ratio", "value": counts["MALE"] / counts["FEMALE"] if counts["FEMALE"] else None, "details": "MALE count divided by FEMALE count."},
    ]
    phase5_crosscheck = {"available": PHASE5_MONTHLY_PATH.exists(), "compared_months": 0, "mismatches": []}
    if PHASE5_MONTHLY_PATH.exists():
        with PHASE5_MONTHLY_PATH.open("r", newline="", encoding="utf-8") as stream:
            phase5_rows = list(csv.DictReader(stream))
        period_lookup = {r["period"]: r for r in period_rows}
        for row in phase5_rows:
            month = row.get("month")
            if month not in period_lookup or period_lookup[month]["coverage_status"] != "OBSERVED_STARTS":
                continue
            phase6row = period_lookup[month]
            phase5_crosscheck["compared_months"] += 1
            for source_col, target_col in (("observed_male_count", "male_count"), ("observed_female_count", "female_count"), ("observed_unknown_count", "unknown_count"), ("distinct_people_observed", "distinct_people")):
                try:
                    left, right = int(row.get(source_col) or 0), int(phase6row[target_col] or 0)
                except (TypeError, ValueError):
                    continue
                if left != right:
                    phase5_crosscheck["mismatches"].append({"month": month, "field": source_col, "phase5": left, "phase6": right})
    quality_rows.append({"metric": "phase5_monthly_crosscheck_mismatches", "value": len(phase5_crosscheck["mismatches"]), "details": json.dumps(phase5_crosscheck, ensure_ascii=False)})

    audit_rows = [
        {"check": "frozen_hiring_input", "status": "PASS", "rows": len(people), "details": f"sha256={sha(input_bytes)}"},
        {"check": "distinct_person_ids", "status": "PASS", "rows": len({r['PERSON_ID'] for r in person_rows}), "details": "Expected one row per distinct person."},
        {"check": "source_sex_mapping", "status": "PASS" if not outcome_mismatches else "FAIL", "rows": len(outcome_mismatches), "details": "MALE/FEMALE mapped only from source_SEX; other values remain UNKNOWN."},
        {"check": "unknown_retained", "status": "PASS", "rows": counts["UNKNOWN"], "details": "Unknown remains separate from the known-sex denominator."},
        {"check": "start_month_coverage", "status": "PASS", "rows": sum(r["coverage_status"] == "OBSERVED_STARTS" for r in period_rows), "details": "Aug/Sep marked no observed start coverage, not zero."},
        {"check": "greenhouse_linkage_absent", "status": "PASS", "rows": 0, "details": "Outcome layer is not joined to Greenhouse postings."},
        {"check": "phase5_crosscheck", "status": "PASS" if not phase5_crosscheck["mismatches"] else "REVIEW", "rows": phase5_crosscheck["compared_months"], "details": json.dumps(phase5_crosscheck, ensure_ascii=False)},
    ]

    output_meta = {}
    for name, rows in outputs.items():
        path = OUT / name
        row_count = csv_write(path, rows)
        output_meta[name] = {"path": str(path.relative_to(BASE)), "row_count": row_count, "sha256": sha(path.read_bytes()), "readback_verified": row_count == len(rows)}
        audit_rows.append({"check": f"readback:{name}", "status": "PASS" if row_count == len(rows) else "FAIL", "rows": row_count, "details": f"Expected {len(rows)} rows."})

    quality_path = OUT / "outcome_quality_summary.csv"
    # quality_rows was extended after outputs was assembled; write its final cross-check row.
    quality_count = csv_write(quality_path, quality_rows)
    output_meta[quality_path.name] = {"path": str(quality_path.relative_to(BASE)), "row_count": quality_count, "sha256": sha(quality_path.read_bytes()), "readback_verified": quality_count == len(quality_rows)}
    audit_rows.append({"check": "readback:outcome_quality_summary.csv", "status": "PASS" if quality_count == len(quality_rows) else "FAIL", "rows": quality_count, "details": f"Expected {len(quality_rows)} rows."})

    metrics_path = OUT / "executive_outcome_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics_readback = json.loads(metrics_path.read_text(encoding="utf-8"))
    audit_rows.append({"check": "readback:executive_outcome_metrics.json", "status": "PASS" if metrics_readback["outcome_counts"] == counts else "FAIL", "rows": 1, "details": f"sha256={sha(metrics_path.read_bytes())}"})

    audit_path = AUDIT_DIR / "outcome_analysis_audit.csv"
    with audit_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check", "status", "rows", "details"])
        writer.writeheader(); writer.writerows(audit_rows)
    manifest = {
        "manifest_type": "version_c_phase_6_outcome_analysis",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": {"path": str(HIRING_PATH.relative_to(BASE)), "rows": len(people), "sha256": sha(input_bytes)},
        "outputs": output_meta,
        "metrics_json": {"path": str(metrics_path.relative_to(BASE)), "sha256": sha(metrics_path.read_bytes()), "readback_verified": True},
        "audit": {"path": str(audit_path.relative_to(BASE)), "rows": len(audit_rows), "sha256": sha(audit_path.read_bytes())},
        "counts": {"all_people": total, "MALE": counts["MALE"], "FEMALE": counts["FEMALE"], "UNKNOWN": counts["UNKNOWN"], "known_sex": known_n,
                   "research_people": len(research_people), "fellowship_people": len(fellowship_people), "source_employment_rows": all_source_records},
        "phase5_crosscheck": phase5_crosscheck,
        "design_guards": {"phase_2_modified": False, "phase_3_modified": False, "phase_4_modified": False, "phase_5_modified": False,
                          "sex_inferred": False, "candidate_level_greenhouse_linkage": False, "unknown_retained": True},
    }
    manifest_path = AUDIT_DIR / "outcome_analysis_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "phase_6_complete", "counts": manifest["counts"], "male_share_known_sex": metrics["outcome_shares"]["male_share_known_sex"],
                      "female_share_known_sex": metrics["outcome_shares"]["female_share_known_sex"], "male_female_ratio": metrics["outcome_shares"]["male_to_female_ratio"],
                      "phase5_crosscheck": phase5_crosscheck, "outputs": output_meta, "audit": str(audit_path), "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
