"""Build Version C Phase 0 freeze artifacts from already verified reports.

This reads aggregate audit artifacts only; it never rewrites Plan A files,
person-level data, or the raw source SEX field.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
DEMOGRAPHICS = PROJECT / "final_demographics_report.json"
CROSSTABS = PROJECT / "final_sex_role_crosstabs_report.json"
CURRENT_AUDIT = PROJECT / "job_postings/snapshots/20260929T061625Z_greenhouse_anthropic_current_audit.json"
HISTORICAL_AUDIT = PROJECT / "job_postings/historical_outputs/20260929T074631Z_historical_greenhouse_audit.json"
PHASE0_FILES = [
    PROJECT / "finalize_hire_demographics.py",
    PROJECT / "final_demographics_report.json",
    PROJECT / "final_sex_role_crosstabs_report.json",
    PROJECT / "dewey_person_catalog_metadata.json",
    PROJECT / "dewey_person_documentation.json",
    PROJECT / "dewey-anthropic-output/r2_exact_day_verification.json",
    PROJECT / "job_postings/pull_greenhouse_anthropic.py",
    PROJECT / "job_postings/recover_historical_greenhouse.py",
    PROJECT / "job_postings/analyze_historical_greenhouse.py",
    PROJECT / "job_postings/analyze_job_posting_language.py",
    CURRENT_AUDIT,
    HISTORICAL_AUDIT,
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pct(n: int, d: int) -> float | None:
    return round(100 * n / d, 6) if d else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = json.loads(DEMOGRAPHICS.read_text(encoding="utf-8"))
    crosstabs = json.loads(CROSSTABS.read_text(encoding="utf-8"))
    current = json.loads(CURRENT_AUDIT.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL_AUDIT.read_text(encoding="utf-8"))

    if report.get("distinct_people") != 1095:
        raise ValueError("The verified demographics report no longer has 1,095 distinct people.")
    raw_sex = {str(item["value"] or ""): int(item["people"]) for item in report["raw_sex_counts"]}
    if raw_sex != {"": 213, "female": 276, "male": 606}:
        raise ValueError(f"Unexpected raw SEX counts; stop for review: {raw_sex}")
    if sum(raw_sex.values()) != report["distinct_people"]:
        raise ValueError("Raw source sex counts do not sum to distinct people.")
    if report.get("employment_rows") != 1097 or report.get("unmatched_people") != 0:
        raise ValueError("Hiring source row or match counts changed; stop for review.")
    if not current.get("verified") or current.get("job_count") != 629:
        raise ValueError("Current Greenhouse source audit is not verified at 629 jobs.")
    if historical.get("counts", {}).get("unique_reconciled_candidates_including_current_or_unresolved") != 1246:
        raise ValueError("Historical analytical source audit no longer corroborates 1,246 records.")
    all_hires = next(item for item in report["summaries"] if item["dimension"] == "all_hires")
    research = next(item for item in report["summaries"] if item["group_name"] == "Confirmed Research")
    if (all_hires["male"], all_hires["female"], all_hires["unknown"], all_hires["total"]) != (606, 276, 213, 1095):
        raise ValueError("All-hire headline no longer matches the verified source report.")
    if (research["male"], research["female"], research["unknown"], research["total"]) != (19, 8, 13, 40):
        raise ValueError("Research subgroup counts changed; stop for review.")

    known = 606 + 276
    overall_unknown_pct = 100 * 213 / 1095
    manifest_time = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest = {
        "version": "C",
        "phase": 0,
        "status": "frozen_baseline",
        "created_at_utc": manifest_time,
        "rule": "This is an immutable analytical baseline. Any refreshed source, changed classification, or revised extraction starts a new manifest version and does not overwrite these inputs.",
        "hiring_outcomes": {
            "provider": "People Data Labs Person dataset accessed through Dewey Data",
            "dataset": "Person",
            "dataset_version": "1.1",
            "doi": "10.82551/wzkb-ts67",
            "doi_as_of": "2026-08-28T07:57:35.532057Z",
            "catalog_version_timestamp": "2026-08-20T16:27:42.145000+00:00",
            "source_data_version_field": "DATASET_VERSION (source field retained in the Dewey person record)",
            "r2_person_source": "filtered/person/anthropic_person_profiles_current_snapshot.parquet",
            "r2_enriched_snapshot": "filtered/analysis/anthropic_hires_enriched_current_snapshot.parquet",
            "r2_demographics_audit": "audit/person-enrichment/final-demographics-report.json",
            "demographics_report_local": "final_demographics_report.json",
            "employment_rows": 1097,
            "distinct_people": 1095,
            "sex_field": "SEX",
            "sex_mapping": {"male": "MALE", "female": "FEMALE", "null_or_blank": "UNKNOWN"},
            "sex_mapping_rule": "Preserve raw SEX unchanged; derive only the separate analysis category. Never infer sex from a person's name or any other proxy.",
            "source_sex_counts": {"MALE": 606, "FEMALE": 276, "UNKNOWN_SOURCE_BLANK": 213},
            "date_coverage": {
                "observed_start_months": ["2026-04", "2026-05", "2026-06", "2026-07"],
                "august_september_observed_starts": 0,
                "limitation": "The current Dewey snapshot does not establish complete August/September start coverage; zero observed starts is not evidence of zero hiring.",
                "verification_r2_key": "dewey-anthropic-output/r2_exact_day_verification.json",
                "verified_at": "2026-09-26T11:14:19.071127+00:00",
            },
        },
        "current_greenhouse": {
            "source_url": "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true",
            "board_url": "https://job-boards.greenhouse.io/anthropic",
            "retrieved_at": current["retrieved_at"],
            "job_count": current["job_count"],
            "verified": current["verified"],
            "r2_raw_key": current["raw_snapshot"]["key"],
            "r2_normalized_key": current["normalized_snapshot"]["key"],
            "r2_audit_key": "experience-anthropic-2026-04-to-09/greenhouse/current-snapshots/20260929T061625Z/greenhouse_anthropic_current_audit.json",
            "normalized_sha256": current["normalized_snapshot"]["sha256"],
        },
        "historical_greenhouse": {
            "retrieved_at": "2026-09-29T07:46:31Z",
            "r2_raw_key": "raw/job-postings/historical-greenhouse/20260929T074631Z/historical_greenhouse_raw.json",
            "r2_deduplicated_key": "filtered/job-postings/20260929T074631Z/historical_greenhouse_deduplicated.json",
            "r2_recovery_audit_key": "audit/job-postings/20260929T074631Z/historical_greenhouse_audit.json",
            "r2_analytical_master_key": "experience-anthropic-2026-04-to-09/filtered/job-postings/analysis/20260929T091413Z/historical_greenhouse_analytical_master.json",
            "candidate_records": 1246,
            "historically_supported": 1237,
            "greenhouse_posting_dates_in_window": 514,
            "archive_capture_only_candidates": 617,
            "research_flag_true": 92,
            "fellowship_flag_true": 4,
            "review_needed": 541,
            "research_classification_code": "job_postings/analyze_historical_greenhouse.py",
            "date_policy": "Archive capture date is kept distinct from posting date. updated_at is not treated as posting date.",
        },
        "posting_language_analysis": {
            "script": "job_postings/analyze_job_posting_language.py",
            "r2_prefix": "experience-anthropic-2026-04-to-09/outputs/job-postings/language-analysis/20260929T092904Z/",
            "r2_metrics": "experience-anthropic-2026-04-to-09/outputs/job-postings/language-analysis/20260929T092904Z/posting_language_metrics.json",
            "r2_person_review": "experience-anthropic-2026-04-to-09/outputs/job-postings/language-analysis/20260929T092904Z/person_example_mentions_review.json",
            "r2_gender_audit": "experience-anthropic-2026-04-to-09/outputs/job-postings/language-analysis/20260929T092904Z/explicit_gender_evidence_audit.json",
            "r2_summary": "experience-anthropic-2026-04-to-09/outputs/job-postings/language-analysis/20260929T092904Z/language_analysis_summary.json",
            "status_note": "First-pass text matching; named-person candidates require manual verification. Zero detected explicit gender references does not establish their absence outside the recovered descriptions or matcher scope.",
        },
        "canonical_headline": {
            "population": "Distinct observed Anthropic people with a source SEX field in the current Dewey/PDL snapshot",
            "total_people": 1095,
            "male": 606,
            "female": 276,
            "unknown_source_blank": 213,
            "known_sex_denominator": known,
            "male_percent_known_sex": round(100 * 606 / known, 2),
            "female_percent_known_sex": round(100 * 276 / known, 2),
            "male_to_female_ratio": round(606 / 276, 2),
            "unknown_percent_all_people": round(overall_unknown_pct, 2),
            "unknown_percent_one_decimal_standard_rounding": round(overall_unknown_pct, 1),
            "rounding_note": "213/1,095 = 19.4521%; report 19.45% or 19.5% to one decimal. 19.4% truncates rather than rounds.",
            "research_subgroup": {"total": 40, "male": 19, "female": 8, "unknown": 13,
                "known_sex_denominator": 27, "male_percent_known_sex": round(100 * 19 / 27, 2),
                "female_percent_known_sex": round(100 * 8 / 27, 2)},
            "scope_warning": report["snapshot_scope"],
        },
        "research_questions": [
            {"id": "RQ1_SIGNAL", "status": "TESTABLE_NOW", "scope": "Describe observable recruiting, representation, language, and role signals."},
            {"id": "RQ2_PREDICTION", "status": "TESTABLE_NOW", "models": ["Logistic Regression", "Gradient Boosting"], "scope": "Test predictive association with observed Male/Female outcomes; not a causal or workflow fairness test."},
            {"id": "RQ3_FEEDBACK", "status": "EXPLORATORY", "scope": "Temporal association between candidate-facing representation and later observed composition; no causal language."},
            {"id": "RQ4_INTERNAL_AI_DECISION_PATH", "status": "PAUSED", "requirement": "Internal candidate-level Greenhouse Talent Matching data."},
            {"id": "RQ5_FUNNEL_ATTRITION", "status": "PAUSED", "requirement": "Candidate-level funnel stage data."},
            {"id": "RQ6_HUMAN_AI_OVERRIDE", "status": "PAUSED", "requirement": "AI recommendations and recruiter override logs."},
        ],
        "source_urls": [
            "https://docs.deweydata.io/docs/people-and-resume-app",
            "https://doi.org/10.82551/WZKB-TS67",
            "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true",
            "https://job-boards.greenhouse.io/anthropic",
            "https://web.archive.org/cdx/search/cdx",
        ],
        "files_hashed": {str(path.relative_to(PROJECT)): sha(path) for path in PHASE0_FILES if path.exists()},
        "build_script_sha256": sha(Path(__file__)),
    }

    taxonomy = {
        "version": "C",
        "field": "outcome_sex_category",
        "values": ["MALE", "FEMALE", "UNKNOWN"],
        "mapping": {"raw SEX == male": "MALE", "raw SEX == female": "FEMALE", "raw SEX null or blank": "UNKNOWN"},
        "inference_prohibited": True,
        "original_sex_field_mutated": False,
    }

    rows = [
        ("all_observed_people", "MALE", 606, 1095, known),
        ("all_observed_people", "FEMALE", 276, 1095, known),
        ("all_observed_people", "UNKNOWN_SOURCE_BLANK", 213, 1095, known),
        ("all_observed_people", "TOTAL", 1095, 1095, known),
        ("confirmed_research_people", "MALE", 19, 40, 27),
        ("confirmed_research_people", "FEMALE", 8, 40, 27),
        ("confirmed_research_people", "UNKNOWN_SOURCE_BLANK", 13, 40, 27),
        ("confirmed_research_people", "TOTAL", 40, 40, 27),
    ]
    csv_path = OUT / "canonical_outcome_denominator.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["population", "outcome_sex_category", "people", "population_denominator", "known_sex_denominator", "percent_of_population", "percent_of_known_sex"])
        for population, category, count, denominator, known_denominator in rows:
            writer.writerow([population, category, count, denominator, known_denominator,
                             "" if category == "TOTAL" else pct(count, denominator),
                             "" if category in ("UNKNOWN_SOURCE_BLANK", "TOTAL") else pct(count, known_denominator)])

    write_json(OUT / "outcome_taxonomy.json", taxonomy)
    write_json(OUT / "phase0_manifest.json", manifest)
    audit = {
        "audit_type": "version_c_phase0_headline_denominator",
        "manifest_version": "C",
        "distinct_people": 1095,
        "employment_rows": 1097,
        "raw_source_sex_counts": raw_sex,
        "known_sex_denominator": known,
        "male_percent_known_sex": round(100 * 606 / known, 2),
        "female_percent_known_sex": round(100 * 276 / known, 2),
        "male_female_ratio": round(606 / 276, 2),
        "unknown_percent_all": round(overall_unknown_pct, 2),
        "research_counts": {"total": 40, "male": 19, "female": 8, "unknown": 13,
                            "known_sex_denominator": 27, "male_percent_known_sex": round(100 * 19 / 27, 2),
                            "female_percent_known_sex": round(100 * 8 / 27, 2)},
        "checks": {"sex_counts_sum_to_distinct_people": True, "person_profile_rows_match_distinct_people": True,
                   "employment_rows_exceed_people_due_to_multiple_jobs": True,
                   "original_sex_preserved": True, "name_based_inference_used": False,
                   "research_counts_match_demographics_report": True},
        "supporting_report_sha256": sha(DEMOGRAPHICS),
        "denominator_csv_sha256": sha(csv_path),
    }
    write_json(OUT / "headline_denominator_audit.json", audit)
    print(json.dumps({"status": "phase0_frozen", "output_directory": str(OUT),
                      "distinct_people": 1095, "known_sex_denominator": known,
                      "male_known_pct": 68.71, "female_known_pct": 31.29,
                      "male_female_ratio": "2.20:1", "unknown_pct_exact": round(overall_unknown_pct, 4),
                      "files": [p.name for p in OUT.glob("*") if p.is_file()]}, indent=2))


if __name__ == "__main__":
    main()
