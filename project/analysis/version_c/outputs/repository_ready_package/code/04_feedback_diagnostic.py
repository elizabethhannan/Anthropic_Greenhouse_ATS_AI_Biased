"""Version C — Phase 5: ecological feedback diagnostic.

Question A: do established-date Greenhouse research signals at month t move
with observed overall/research hire composition at t, t+1, or t+2?
Question B: within exact role-month intersections, do posting signal levels
co-vary with observed known-sex hiring composition?

This is descriptive ecological analysis. It never links an applicant or hire
to a specific Greenhouse posting and never infers sex. Archive captures do not
provide posting dates. Aug/Sep 2026 hiring outcomes are marked unavailable,
not zero, because observed-start coverage in the frozen Dewey snapshot ends in
July 2026. Phase 2/3/4 inputs are read-only.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT_DIR = BASE / "audit"
INPUTS = {
    "master": OUT / "version_c_master.parquet",
    "hiring": OUT / "version_c_hiring_outcomes.parquet",
    "bridge": OUT / "version_c_role_month_bridge.parquet",
    "signals": OUT / "signal_features.parquet",
}
MONTHS = [f"2026-{m:02d}" for m in range(4, 10)]
MIN_CORRELATION_N = 3
SIGNAL_FEATURES = {
    "research_signal": ["researcher_reference_count", "research_exemplar_count", "signal_research_count"],
    "representation_signal": ["named_person_count", "recurring_named_person_count", "research_exemplar_count"],
    "publication_signal": ["publication_paper_reference_count", "signal_publication_emphasis_count", "signal_paper_reference_count"],
    "technical_signal": ["signal_ai_ml_count", "signal_technical_specialization_count"],
    "leadership_signal": ["signal_leadership_count", "signal_seniority_count"],
    "collaboration_signal": ["signal_collaboration_count"],
    "accomplishment_signal": ["signal_accomplishment_framing_count"],
    "candidate_expectation_signal": ["signal_candidate_expectations_count"],
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_parquet(path: Path) -> tuple[list[dict[str, Any]], bytes]:
    if not path.exists():
        raise FileNotFoundError(f"Required frozen input is missing: {path}")
    blob = path.read_bytes()
    return pq.read_table(path).to_pylist(), blob


def month_of(value: Any) -> str | None:
    if value is None:
        return None
    match = re.match(r"^(\d{4})-(\d{2})", str(value).strip())
    if not match:
        return None
    month = int(match.group(2))
    return f"{match.group(1)}-{month:02d}" if 1 <= month <= 12 else None


def posting_date(row: dict[str, Any]) -> Any:
    return row.get("first_published_at") or row.get("posting_date_if_known")


def correlations(xvals: list[float], yvals: list[float]) -> tuple[int, float | None, float | None]:
    pairs = [(float(x), float(y)) for x, y in zip(xvals, yvals) if math.isfinite(float(x)) and math.isfinite(float(y))]
    n = len(pairs)
    if n < MIN_CORRELATION_N:
        return n, None, None
    x = np.asarray([p[0] for p in pairs], dtype=float)
    y = np.asarray([p[1] for p in pairs], dtype=float)
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return n, None, None
    pearson = float(np.corrcoef(x, y)[0, 1])

    def average_ranks(values: np.ndarray) -> np.ndarray:
        order = np.argsort(values, kind="mergesort")
        ranks = np.empty(len(values), dtype=float)
        i = 0
        while i < len(values):
            j = i + 1
            while j < len(values) and values[order[j]] == values[order[i]]:
                j += 1
            ranks[order[i:j]] = (i + 1 + j) / 2.0
            i = j
        return ranks

    xr, yr = average_ranks(x), average_ranks(y)
    spearman = float(np.corrcoef(xr, yr)[0, 1]) if np.ptp(xr) and np.ptp(yr) else None
    return n, pearson, spearman


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def resolve_feature(row: dict[str, Any], aliases: list[str]) -> float:
    for name in aliases:
        if name in row:
            try:
                return float(row[name] or 0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def monthly_postings(master: list[dict[str, Any]], signals: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Join only posting-level Phase 3 features to their source post IDs. This
    # merge has no employee or candidate data.
    signal_by_id = {str(r.get("version_c_posting_id")): r for r in signals}
    eligible = []
    for post in master:
        if post.get("date_evidence_class") != "GREENHOUSE_POSTING_DATE":
            continue
        month = month_of(posting_date(post))
        if month not in MONTHS:
            continue
        feature = signal_by_id.get(str(post.get("version_c_posting_id")), {})
        research = bool_value(post.get("research_flag"))
        fellowship = bool_value(post.get("fellowship_flag"))
        eligible.append({"post": post, "feature": feature, "month": month, "research": research, "fellowship": fellowship})

    output = []
    for month in MONTHS:
        group = [r for r in eligible if r["month"] == month]
        item = {
            "month": month,
            "posting_count": len(group),
            "research_posting_count": sum(r["research"] for r in group),
            "fellowship_posting_count": sum(r["fellowship"] for r in group),
            "research_fellowship_posting_count": sum(r["research"] and r["fellowship"] for r in group),
            "research_posting_share": sum(r["research"] for r in group) / len(group) if group else None,
            "fellowship_posting_share": sum(r["fellowship"] for r in group) / len(group) if group else None,
            "research_fellowship_posting_share": sum(r["research"] and r["fellowship"] for r in group) / len(group) if group else None,
            "named_person_count_total": sum(resolve_feature(r["feature"], ["named_person_count"]) for r in group),
            "research_exemplar_count_total": sum(resolve_feature(r["feature"], ["research_exemplar_count"]) for r in group),
            "publication_reference_count_total": sum(resolve_feature(r["feature"], ["publication_paper_reference_count"]) for r in group),
            "date_basis": "GREENHOUSE_POSTING_DATE only",
            "archive_capture_used_as_posting_date": False,
        }
        for family, aliases in SIGNAL_FEATURES.items():
            values = [resolve_feature(r["feature"], aliases) for r in group]
            item[f"mean_{family}"] = float(np.mean(values)) if values else None
        output.append(item)
    return output, eligible


def hiring_outcomes(hiring: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Monthly outcome populations deduplicate at person x month. The role
    # version is person x month x source role category. Unknown remains a class.
    people_month: dict[tuple[str, str], dict[str, Any]] = {}
    people_role_month: dict[tuple[str, str, str], dict[str, Any]] = {}
    source_rows = 0
    for person in hiring:
        person_id = str(person.get("PERSON_ID") or "")
        sex = str(person.get("outcome_sex") or "UNKNOWN").upper()
        raw = person.get("employment_records")
        records = json.loads(raw) if isinstance(raw, str) else (raw or [])
        for record in records:
            source_rows += 1
            month = month_of(record.get("START_DATE"))
            if month not in MONTHS:
                continue
            role = str(record.get("ROLE_CATEGORY") or record.get("TITLE_ROLE") or record.get("TITLE_NAME") or "Unknown role").strip()
            research = record.get("IS_RESEARCH_HIRE")
            if research is None:
                research = role in {"Fellows Researcher", "Research Scientist", "Research Engineer", "AI/ML Research - Other", "Interpretability", "Evaluations", "Pre-training", "Post-training", "Reinforcement Learning"}
            base = {"PERSON_ID": person_id, "month": month, "outcome_sex": sex, "role_family": role, "research_hire": bool_value(research)}
            person_month_key = (person_id, month)
            if person_month_key in people_month:
                people_month[person_month_key]["research_hire"] = people_month[person_month_key]["research_hire"] or base["research_hire"]
            else:
                people_month[person_month_key] = dict(base)
            people_role_month[(person_id, month, role)] = base

    def count_rows(month: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        male = sum(r["outcome_sex"] == "MALE" for r in rows)
        female = sum(r["outcome_sex"] == "FEMALE" for r in rows)
        unknown = sum(r["outcome_sex"] == "UNKNOWN" for r in rows)
        research_rows = [r for r in rows if r["research_hire"]]
        rm = sum(r["outcome_sex"] == "MALE" for r in research_rows)
        rf = sum(r["outcome_sex"] == "FEMALE" for r in research_rows)
        ru = sum(r["outcome_sex"] == "UNKNOWN" for r in research_rows)
        known = male + female
        research_known = rm + rf
        return {
            "month": month,
            "outcome_coverage": "OBSERVED_STARTS" if rows else "NO_OBSERVED_START_RECORDS",
            "distinct_people_observed": len(rows),
            "observed_male_count": male,
            "observed_female_count": female,
            "observed_unknown_count": unknown,
            "male_share_known_sex": male / known if known else None,
            "female_share_known_sex": female / known if known else None,
            "unknown_share_all": unknown / len(rows) if rows else None,
            "known_sex_count": known,
            "research_hire_people": len(research_rows),
            "research_male_count": rm,
            "research_female_count": rf,
            "research_unknown_count": ru,
            "research_male_share_known_sex": rm / research_known if research_known else None,
            "research_female_share_known_sex": rf / research_known if research_known else None,
            "research_unknown_share_all": ru / len(research_rows) if research_rows else None,
        }

    monthly = []
    for month in MONTHS:
        rows = [r for (pid, m), r in people_month.items() if m == month]
        result = count_rows(month, rows)
        if month in {"2026-08", "2026-09"}:
            result.update({"outcome_coverage": "NO_OBSERVED_START_COVERAGE", "distinct_people_observed": None,
                           "observed_male_count": None, "observed_female_count": None, "observed_unknown_count": None,
                           "male_share_known_sex": None, "female_share_known_sex": None, "unknown_share_all": None,
                           "known_sex_count": None, "research_hire_people": None, "research_male_count": None,
                           "research_female_count": None, "research_unknown_count": None,
                           "research_male_share_known_sex": None, "research_female_share_known_sex": None,
                           "research_unknown_share_all": None})
        monthly.append(result)

    role_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for (pid, month, role), row in people_role_month.items():
        role_groups[(month, role)].append(row)
    role_month = []
    for (month, role), rows in sorted(role_groups.items()):
        summary = count_rows(month, rows)
        summary["role_family"] = role
        role_month.append(summary)
    return monthly, role_month


def merge_role_month(posting_records: list[dict[str, Any]], role_outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    post_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in posting_records:
        role = str(item["post"].get("posting_role_family") or "Review Needed")
        post_groups[(item["month"], role)].append(item)
    outcomes = {(r["month"], r["role_family"]): r for r in role_outcomes}
    rows = []
    for (month, role), posts in sorted(post_groups.items()):
        outcome = outcomes.get((month, role))
        if not outcome:
            continue
        row = {"month": month, "role_family": role, "posting_count": len(posts), "observed_male_count": outcome["observed_male_count"],
               "observed_female_count": outcome["observed_female_count"], "observed_unknown_count": outcome["observed_unknown_count"],
               "male_share_known_sex": outcome["male_share_known_sex"], "female_share_known_sex": outcome["female_share_known_sex"],
               "unknown_share_all": outcome["unknown_share_all"], "research_hire_people": outcome["research_hire_people"],
               "research_male_share_known_sex": outcome["research_male_share_known_sex"], "research_unknown_count": outcome["research_unknown_count"],
               "association_unit": "role_month_ecological_cell", "candidate_level_linkage": False}
        for family, aliases in SIGNAL_FEATURES.items():
            values = [resolve_feature(p["feature"], aliases) for p in posts]
            row[f"mean_{family}"] = float(np.mean(values)) if values else None
        rows.append(row)
    return rows


def association_row(scope: str, signal_name: str, target_name: str, xs: list[float], ys: list[float], months: list[str]) -> dict[str, Any]:
    n, pearson, spearman = correlations(xs, ys)
    return {"scope": scope, "signal": signal_name, "outcome": target_name, "n": n,
            "pearson_r": pearson, "spearman_rho": spearman,
            "status": "ESTIMATED_EXPLORATORY" if n >= MIN_CORRELATION_N and pearson is not None else "DEFERRED_INSUFFICIENT_OR_CONSTANT_DATA",
            "months_or_cells": json.dumps(months), "causal_claim": False,
            "interpretation": "Aggregate co-movement only; not candidate-level prediction or causation."}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    loaded = {name: read_parquet(path) for name, path in INPUTS.items()}
    data = {name: values[0] for name, values in loaded.items()}
    input_bytes = {name: values[1] for name, values in loaded.items()}
    expected = {"master": 1246, "hiring": 1095, "bridge": 41, "signals": 1246}
    actual = {name: len(rows) for name, rows in data.items()}
    if actual != expected:
        raise ValueError(f"Frozen input row counts changed: expected {expected}, got {actual}")

    representation, eligible_posts = monthly_postings(data["master"], data["signals"])
    outcomes, role_outcomes = hiring_outcomes(data["hiring"])
    monthly_join = []
    outcome_index = {r["month"]: r for r in outcomes}
    for rep in representation:
        out = outcome_index[rep["month"]]
        monthly_join.append({**rep, **{f"outcome_{k}": v for k, v in out.items() if k != "month"}})

    lag_rows = []
    target_series = ["outcome_research_male_share_known_sex", "outcome_research_female_share_known_sex", "outcome_research_unknown_share_all", "outcome_male_share_known_sex", "outcome_female_share_known_sex", "outcome_unknown_share_all"]
    rep_series = ["research_posting_count", "research_posting_share", "fellowship_posting_count", "research_fellowship_posting_count", "research_exemplar_count_total", "publication_reference_count_total"] + [f"mean_{name}" for name in SIGNAL_FEATURES]
    month_index = {r["month"]: i for i, r in enumerate(monthly_join)}
    for lag in (0, 1, 2):
        for signal in rep_series:
            for target in target_series:
                xvals, yvals, labels = [], [], []
                for row in monthly_join:
                    i = month_index[row["month"]]
                    target_i = i + lag
                    if target_i >= len(monthly_join):
                        continue
                    source_row, outcome_row = monthly_join[i], monthly_join[target_i]
                    y = outcome_row.get(target)
                    x = source_row.get(signal)
                    if x is None or y is None:
                        continue
                    xvals.append(float(x)); yvals.append(float(y))
                    labels.append(f"{source_row['month']}->{outcome_row['month']}")
                result = association_row(f"lag_{lag}", signal, target, xvals, yvals, labels)
                result["lag_months"] = lag
                result["direction"] = "posting month t to outcome month t+lag"
                lag_rows.append(result)

    role_cells = merge_role_month(eligible_posts, role_outcomes)
    role_rows = []
    role_metrics = ["male_share_known_sex", "female_share_known_sex", "unknown_share_all", "research_male_share_known_sex", "research_hire_people"]
    role_signals = [f"mean_{name}" for name in SIGNAL_FEATURES]
    for signal in role_signals:
        for target in role_metrics:
            valid = [r for r in role_cells if r.get(signal) is not None and r.get(target) is not None]
            role_rows.append(association_row("role_month", signal, target,
                [float(r[signal]) for r in valid], [float(r[target]) for r in valid],
                [f"{r['role_family']}|{r['month']}" for r in valid]))

    # Output tables include coverage and sample size, so missing months cannot
    # be mistaken for zero outcomes.
    paths = {
        "monthly_representation.csv": representation,
        "monthly_outcomes.csv": outcomes,
        "lagged_associations.csv": lag_rows,
        "role_feedback_associations.csv": role_rows,
    }
    for name, rows in paths.items():
        columns = list(dict.fromkeys(k for row in rows for k in row))
        if not columns:
            columns = ["status"]
        with (OUT / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader(); writer.writerows(rows)

    valid_forward1 = [r for r in lag_rows if r["lag_months"] == 1 and r["outcome"] == "outcome_research_male_share_known_sex"]
    forward_n_values = sorted({r["n"] for r in valid_forward1})
    summary = [
        {"item": "status", "value": "COMPLETE_WITH_COVERAGE_LIMITS", "interpretation": "Descriptive ecological diagnostic only."},
        {"item": "posting_records_with_established_dates", "value": len(eligible_posts), "interpretation": "Only GREENHOUSE_POSTING_DATE records in April-September 2026 were included."},
        {"item": "hiring_observed_coverage", "value": "2026-04 through 2026-07", "interpretation": "August/September are unavailable in this observed-start snapshot, not zero hires."},
        {"item": "question_A_forward_1_sample_months", "value": max(forward_n_values, default=0), "interpretation": "At most three posting-to-next-month pairs are observable; interpret correlations as exploratory."},
        {"item": "question_A_forward_2_sample_months", "value": "2; deferred by minimum n=3", "interpretation": "Two-month-forward comparisons have fewer than three observed pairs."},
        {"item": "question_B_exact_role_month_cells", "value": len(role_cells), "interpretation": "Exact posting-role/month and hiring-role/month overlaps; aggregate only."},
        {"item": "candidate_level_linkage", "value": False, "interpretation": "No individual applicant/hire-to-posting linkage."},
        {"item": "sex_inference", "value": False, "interpretation": "Sex labels come only from preserved source outcome labels."},
        {"item": "causality", "value": False, "interpretation": "No causal effect is estimated."},
    ]
    with (OUT / "feedback_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["item", "value", "interpretation"])
        writer.writeheader(); writer.writerows(summary)

    output_names = list(paths) + ["feedback_summary.csv"]
    output_meta = {}
    audit_rows = []
    for name in output_names:
        path = OUT / name
        with path.open("r", encoding="utf-8", newline="") as stream:
            count = max(0, sum(1 for _ in csv.reader(stream)) - 1)
        output_meta[name] = {"path": str(path.relative_to(BASE)), "row_count": count, "sha256": sha(path.read_bytes()), "readback_verified": True}
        audit_rows.append({"check": f"readback:{name}", "status": "PASS", "rows": count, "details": "CSV reopened and row count recorded."})
    for name, path in INPUTS.items():
        audit_rows.append({"check": f"input:{path.name}", "status": "PASS", "rows": actual[name], "details": f"SHA-256={sha(input_bytes[name])}; read-only frozen input."})
    audit_rows += [
        {"check": "archive_capture_date_exclusion", "status": "PASS", "rows": len(eligible_posts), "details": "Temporal representation uses established Greenhouse posting dates only."},
        {"check": "hiring_snapshot_missingness", "status": "PASS", "rows": 2, "details": "August and September marked NO_OBSERVED_START_COVERAGE, not zero."},
        {"check": "candidate_linkage_and_sex_inference", "status": "PASS", "rows": 0, "details": "No person-posting link and no sex inference."},
    ]
    audit_path = AUDIT_DIR / "feedback_audit.csv"
    with audit_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check", "status", "rows", "details"])
        writer.writeheader(); writer.writerows(audit_rows)

    manifest = {
        "manifest_type": "version_c_phase_5_feedback_diagnostic",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inputs": {name: {"path": str(path.relative_to(BASE)), "rows": actual[name], "sha256": sha(input_bytes[name])} for name, path in INPUTS.items()},
        "outputs": output_meta,
        "audit": {"path": str(audit_path.relative_to(BASE)), "rows": len(audit_rows), "sha256": sha(audit_path.read_bytes())},
        "counts": {"established_date_postings": len(eligible_posts), "monthly_representation_rows": len(representation), "monthly_outcome_rows": len(outcomes), "observed_start_months": sorted(r["month"] for r in outcomes if r["outcome_coverage"] == "OBSERVED_STARTS"), "unobserved_outcome_months": [r["month"] for r in outcomes if r["outcome_coverage"] == "NO_OBSERVED_START_COVERAGE"], "exact_role_month_overlap_cells": len(role_cells)},
        "method": {"lags_months": [0, 1, 2], "correlations": ["Pearson", "Spearman"], "minimum_pair_count": MIN_CORRELATION_N, "p_values": False, "role_family_matching": "exact label match", "unknown_sex": "reported separately, excluded from known-sex denominators", "phase_2_phase_3_phase_4_modified": False, "candidate_level_linkage": False, "archive_capture_as_posting_date": False, "causality": False},
        "limitations": ["Observed hire start-month coverage is April-July 2026; August and September are unavailable, not zero.", "Six study months yield at most three observed +1-month pairs and two +2-month pairs.", "Role-month overlap is sparse and exact family matching may omit nonmatching labels.", "Temporal co-movement does not identify a posting-to-hire pathway or causal effect."],
    }
    manifest_path = AUDIT_DIR / "feedback_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "feedback_diagnostic_complete", "counts": manifest["counts"], "outputs": output_meta, "audit": str(audit_path), "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
