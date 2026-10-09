"""VERSION C — PHASE 3: auditable descriptive signal diagnostics.

Reads the frozen Phase 2 Parquet files and creates posting-level signal features,
source-text examples, summaries, and cautious aggregate role-month associations.
No posting is assigned a hire or a demographic outcome.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
INPUT_DIR = HERE / "outputs"
OUTPUT_DIR = HERE / "outputs"
AUDIT_DIR = HERE / "audit"

# Auditable, deliberately broad lexical groups. Counts are textual signals,
# not assessments of job quality, bias, or intent.
SIGNALS: dict[str, tuple[str, ...]] = {
    "research": (r"\bresearch(?:er|ers|ing)?\b", r"\bscientist(?:s)?\b", r"\bscientific\b", r"\bempirical\b", r"\bexperiment(?:s|al)?\b", r"\binvestigat(?:e|es|ing|ion)\b"),
    "engineering": (r"\bengineer(?:s|ing)?\b", r"\bsoftware engineering\b", r"\bsystems engineering\b", r"\bproduction engineering\b", r"\binfrastructure\b"),
    "ai_ml": (r"\b(?:artificial intelligence|AI|machine learning|ML)\b", r"\bdeep learning\b", r"\bLLMs?\b", r"\bgenerative AI\b", r"\bmodel training\b"),
    "technical_specialization": (r"\b(?:transformers?|RLHF|reinforcement learning|interpretability|scaling laws?|distributed training|pre[- ]training|pretraining|post[- ]training|fine[- ]tuning|multimodal|computer vision|natural language processing|NLP|model behavior|AI safety|alignment|evaluations?|constitutional AI|agents?|neural networks?)\b",),
    "leadership": (r"\b(?:lead(?:s|ing)?|leader(?:s|ship)?|manage(?:s|d|r|rs|ment|ing)?|manager(?:s)?|director(?:s)?|head of|mentor(?:s|ing)?|mentorship|organizational|team leadership)\b",),
    "seniority": (r"\b(?:senior|staff|principal|distinguished|lead|director|head|manager|executive|years of experience|extensive experience)\b",),
    "collaboration": (r"\b(?:collaborat\w*|cross[- ]functional|partner\w*|work with|working with|stakeholders?|teams?|interdisciplinary)\b",),
    "accomplishment_framing": (r"\b(?:demonstrated|track record|proven|achievement\w*|achieved|impact\w*|shipped|built|led|delivered|scaled|recognized|published|contribution)\b",),
    "candidate_expectations": (r"\b(?:qualifications?|requirements?|what you(?:'ll| will) do|what we(?:'re| are) looking for|ideal candidate|you will|you should|we expect|expected|minimum qualifications?|preferred qualifications?)\b",),
    "publication_emphasis": (r"\b(?:publication\w*|published|paper\w*|preprint\w*|arXiv|author(?:s|ship)?|conference\w*|citation\w*)\b",),
    "paper_reference": (r"\b(?:paper\w*|preprint\w*|arXiv)\b",),
    "research_pedigree": (r"\b(?:Ph\.?D\.?|doctorate|doctoral|academic|academia|university|faculty|postdoctoral|postdoc|first[- ]author|top[- ]tier conference|NeurIPS|ICML|ICLR|ACL|EMNLP|CVPR)\b",),
    "named_expert_reference": (),
}
COMPILED = {name: [re.compile(p, re.I) for p in pats] for name, pats in SIGNALS.items()}
WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Frozen Phase 2 input is missing: {path}")
    return pq.read_table(path).to_pylist()


def text_value(value: Any) -> str:
    return value if isinstance(value, str) else ""


def parse_names(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            raw = [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]
    else:
        raw = []
    names = []
    for item in raw:
        if isinstance(item, str) and item.strip() and item.strip() not in names:
            names.append(item.strip())
    return names


def posting_date(row: dict[str, Any]) -> str | None:
    for field in ("first_published_at", "posting_date_if_known"):
        value = row.get(field)
        if value:
            return str(value)
    return None


def month_of(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) < 7:
        return None
    try:
        year, month = int(value[:4]), int(value[5:7])
        return f"{year:04d}-{month:02d}" if 1 <= month <= 12 else None
    except ValueError:
        return None


def occurrences(patterns: list[re.Pattern[str]], text: str) -> int:
    return sum(len(pattern.findall(text)) for pattern in patterns)


def sentence_for(text: str, start: int, end: int) -> str:
    for sentence in SENTENCE_RE.split(text):
        left = text.find(sentence)
        if left <= start < left + len(sentence):
            return sentence.strip()[:1000]
    return text[max(0, start - 180):min(len(text), end + 180)].strip()


def make_feature_rows(postings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    features, examples = [], []
    for row in postings:
        description = text_value(row.get("description_text"))
        if not description:
            # Some historical rows contain HTML but no cleaned text. Preserve
            # availability and derive a conservative readable fallback.
            html = text_value(row.get("description_html"))
            description = re.sub(r"<[^>]+>", " ", html)
            description = re.sub(r"\s+", " ", description).strip()
        names = parse_names(row.get("language_named_person_names"))
        named_n = row.get("language_named_person_mentions")
        named_n = int(named_n or 0)
        signal_counts = {name: occurrences(patterns, description) for name, patterns in COMPILED.items()}
        signal_counts["named_expert_reference"] = named_n
        feature = {
            **row,
            "description_available": bool(description),
            "description_word_count": len(WORD_RE.findall(description)),
            "named_person_count": named_n,
            "named_person_names": json.dumps(names, ensure_ascii=False),
            "recurring_named_person_count": 0,  # populated after corpus-wide counts
            "research_exemplar_count": named_n if row.get("research_flag") else 0,
            "researcher_reference_count": signal_counts["research"],
            "publication_paper_reference_count": signal_counts["publication_emphasis"],
            "representation_concentration_share": None,
            "signal_counts": json.dumps(signal_counts, sort_keys=True),
            "candidate_level_outcome_linkage": False,
        }
        for name, count in signal_counts.items():
            feature[f"signal_{name}_count"] = count
        features.append(feature)

        for name in names:
            occurrences_for_name = list(re.finditer(re.escape(name), description, re.I))
            if not occurrences_for_name:
                examples.append(example_base(row, "named person reference", "named_person", name, ""))
            for match in occurrences_for_name:
                examples.append(example_base(row, name, "named_person", match.group(0), sentence_for(description, match.start(), match.end())))
        for signal_name, patterns in COMPILED.items():
            # One source example per feature and posting keeps the audit table
            # reviewable; feature counts retain every occurrence.
            signal_match = None
            for pattern in patterns:
                signal_match = pattern.search(description)
                if signal_match:
                    break
            if signal_match:
                examples.append(example_base(row, signal_name, signal_name, signal_match.group(0), sentence_for(description, signal_match.start(), signal_match.end())))

    name_postings: dict[str, set[str]] = defaultdict(set)
    for row in features:
        post_id = str(row.get("version_c_posting_id"))
        for name in parse_names(row["named_person_names"]):
            name_postings[name.casefold()].add(post_id)
    for row in features:
        names = parse_names(row["named_person_names"])
        recurring = sum(1 for name in names if len(name_postings[name.casefold()]) > 1)
        row["recurring_named_person_count"] = recurring
        corpus_frequency = [len(name_postings[name.casefold()]) for name in names]
        total_frequency = sum(corpus_frequency)
        row["representation_concentration_share"] = max(corpus_frequency) / total_frequency if total_frequency else 0.0
        row["representation_concentration_hhi"] = sum((n / total_frequency) ** 2 for n in corpus_frequency) if total_frequency else 0.0
        row["signal_named_expert_reference_count"] = int(row.get("named_person_count") or 0)
    return features, examples


def example_base(row: dict[str, Any], signal: str, signal_type: str, matched: str, context: str) -> dict[str, Any]:
    return {
        "greenhouse_job_id": row.get("greenhouse_job_id"),
        "job_title": row.get("exact_title"),
        "matched_signal": signal,
        "signal_type": signal_type,
        "matched_text": matched,
        "context_sentence": context,
        "source_url": row.get("source_url") or row.get("absolute_url"),
        "posting_date": posting_date(row),
        "date_evidence_class": row.get("date_evidence_class"),
        "version_c_posting_id": row.get("version_c_posting_id"),
    }


def summary_rows(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in features:
        groups["all_postings"].append(row)
        if row.get("research_flag"):
            groups["research_postings"].append(row)
        if row.get("fellowship_flag"):
            groups["fellowship_postings"].append(row)
        if row.get("research_flag") and row.get("fellowship_flag"):
            groups["research_and_fellowship"].append(row)
        groups[f"date_evidence:{row.get('date_evidence_class') or 'MISSING'}"].append(row)
    count_fields = ["description_word_count", "named_person_count", "recurring_named_person_count", "research_exemplar_count", "researcher_reference_count", "publication_paper_reference_count"] + [f"signal_{n}_count" for n in SIGNALS]
    output = []
    for group, rows in sorted(groups.items()):
        result = {"group": group, "posting_count": len(rows), "descriptions_available": sum(bool(r["description_available"]) for r in rows)}
        for field in count_fields:
            result[f"total_{field}"] = sum(int(r.get(field) or 0) for r in rows)
            result[f"mean_{field}"] = round(result[f"total_{field}"] / len(rows), 4) if rows else 0
        result["mean_representation_concentration_share"] = round(sum(float(r.get("representation_concentration_share") or 0) for r in rows) / len(rows), 4) if rows else 0
        result["mean_representation_concentration_hhi"] = round(sum(float(r.get("representation_concentration_hhi") or 0) for r in rows) / len(rows), 4) if rows else 0
        output.append(result)
    return output


def reconcile_bridge_from_frozen_hiring(hiring: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rebuild role-month outcome counts in memory from frozen Phase 2 rows.

    Phase 2 remains read-only. Its bridge omitted hires because the source
    start dates are month strings (YYYY-MM), which the Phase 2 full-date window
    parser rejected. Count each distinct person once per month and role.
    """
    unique: dict[tuple[str, str, str], str] = {}
    for person in hiring:
        person_id = str(person.get("PERSON_ID") or "")
        sex = str(person.get("outcome_sex") or "UNKNOWN").upper()
        raw = person.get("employment_records")
        if isinstance(raw, str):
            records = json.loads(raw)
        elif isinstance(raw, list):
            records = raw
        else:
            records = []
        for source in records:
            month = month_of(source.get("START_DATE"))
            if not month or not "2026-04" <= month <= "2026-09":
                continue
            family = str(source.get("ROLE_CATEGORY") or source.get("TITLE_ROLE") or source.get("TITLE_NAME") or "Unknown role").strip()
            unique[(person_id, month, family)] = sex

    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for (person_id, month, family), sex in unique.items():
        key = (month, family)
        cell = cells.setdefault(key, {
            "month": month, "role_family": family,
            "observed_hire_people": 0,
            "observed_hire_male": 0,
            "observed_hire_female": 0,
            "observed_hire_unknown": 0,
            "bridge_source": "reconciled_in_memory_from_frozen_hiring_outcomes",
            "candidate_level_linkage": False,
        })
        cell["observed_hire_people"] += 1
        category = sex.lower() if sex.lower() in {"male", "female", "unknown"} else "unknown"
        cell[f"observed_hire_{category}"] += 1
    return [cells[key] for key in sorted(cells)]


def bridge_associations(features: list[dict[str, Any]], bridge: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Only posting rows with established posting dates in the study window enter
    # the feature side. Archive capture month is never substituted for posting month.
    by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in features:
        if row.get("date_evidence_class") != "GREENHOUSE_POSTING_DATE":
            continue
        month = month_of(posting_date(row))
        if month and "2026-04" <= month <= "2026-09":
            by_cell[(month, str(row.get("posting_role_family") or "Review Needed"))].append(row)
    bridge_index = {(str(r["month"]), str(r["role_family"])): r for r in bridge}
    bridge_cells_with_hires = sum(
        int(r.get("observed_hire_male") or 0)
        + int(r.get("observed_hire_female") or 0)
        + int(r.get("observed_hire_unknown") or 0) > 0
        for r in bridge
    )
    if bridge_cells_with_hires == 0:
        return [{
            "signal_feature": "",
            "status": "NOT_ESTIMABLE",
            "reason": (
                "The supplied aggregate bridge contains zero observed hires "
                "in all cells, so no demographic outcome association can be "
                "estimated from it."
            ),
            "bridge_rows": len(bridge),
            "bridge_cells_with_observed_hires": 0,
            "candidate_level_linkage": False,
            "causal_interpretation_allowed": False,
        }]
    result = []
    candidate_features = ["named_person_count", "recurring_named_person_count", "research_exemplar_count", "researcher_reference_count", "publication_paper_reference_count", "signal_research_pedigree_count", "signal_technical_specialization_count", "signal_leadership_count", "signal_seniority_count", "signal_accomplishment_framing_count", "signal_candidate_expectations_count"]
    for key, rows in sorted(by_cell.items()):
        outcome = bridge_index.get(key)
        if not outcome:
            continue
        male, female, unknown = (int(outcome.get(field) or 0) for field in ("observed_hire_male", "observed_hire_female", "observed_hire_unknown"))
        known = male + female
        base = {"month": key[0], "role_family": key[1], "posting_count": len(rows),
                "observed_male_count": male, "observed_female_count": female,
                "observed_unknown_count": unknown,
                "male_share_known_sex": male / known if known else None,
                "female_share_known_sex": female / known if known else None,
                "unknown_share_all": unknown / (known + unknown) if known + unknown else None,
                "archive_capture_only_candidates": outcome.get("archive_capture_only_candidates", 0),
                "bridge_source": outcome.get("bridge_source", "phase_2_role_month_bridge"),
                "association_unit": "role_month_ecological_cell",
                "candidate_level_linkage": False}
        for field in candidate_features:
            vals = [float(r.get(field) or 0) for r in rows]
            base[f"mean_{field}"] = sum(vals) / len(vals)
        result.append(base)
    # Long-form feature association table; descriptive cell pairs only, no p-values
    # or causal interpretation. Keep the matched cell examples in this CSV.
    long = []
    for cell in result:
        for field in candidate_features:
            long.append({"signal_feature": field, "signal_mean": cell[f"mean_{field}"],
                         "month": cell["month"], "role_family": cell["role_family"],
                         "posting_count": cell["posting_count"],
                         "observed_male_count": cell["observed_male_count"],
                         "observed_female_count": cell["observed_female_count"],
                         "observed_unknown_count": cell["observed_unknown_count"],
                         "male_share_known_sex": cell["male_share_known_sex"],
                         "female_share_known_sex": cell["female_share_known_sex"],
                         "unknown_share_all": cell["unknown_share_all"],
                         "archive_capture_only_candidates": cell["archive_capture_only_candidates"],
                         "association_unit": cell["association_unit"],
                         "candidate_level_linkage": False})
    return long


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as parquet
    path.parent.mkdir(parents=True, exist_ok=True)
    parquet.write_table(pa.Table.from_pylist(rows), path, compression="zstd", version="2.6")
    if parquet.read_table(path).num_rows != len(rows):
        raise RuntimeError(f"Local row count failed for {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--r2", action="store_true", help="Upload outputs under the immutable Phase 3 R2 run prefix and verify read-back")
    args = parser.parse_args()

    master_path = INPUT_DIR / "version_c_master.parquet"
    hiring_path = INPUT_DIR / "version_c_hiring_outcomes.parquet"
    bridge_path = INPUT_DIR / "version_c_role_month_bridge.parquet"
    master, hiring, phase2_bridge = read_rows(master_path), read_rows(hiring_path), read_rows(bridge_path)
    bridge = phase2_bridge
    if (len(master), len(hiring), len(phase2_bridge)) != (1246, 1095, 41):
        raise ValueError(f"Frozen Phase 2 row counts changed: master={len(master)}, hiring={len(hiring)}, bridge={len(phase2_bridge)}")
    if any(row.get("candidate_level_hire_linkage") is not False for row in master) or any(row.get("candidate_level_linkage") is not False for row in bridge):
        raise ValueError("Phase 2 linkage guard failed")

    features, examples = make_feature_rows(master)
    recurring_counts = Counter()
    for row in features:
        recurring_counts.update(name.casefold() for name in parse_names(row["named_person_names"]))
    for row in features:
        row["corpus_named_person_mentions"] = sum(recurring_counts[n.casefold()] for n in parse_names(row["named_person_names"]))
    summaries = summary_rows(features)
    phase2_bridge_hire_cells = sum(
        int(row.get("observed_hire_male") or 0)
        + int(row.get("observed_hire_female") or 0)
        + int(row.get("observed_hire_unknown") or 0) > 0
        for row in phase2_bridge
    )
    if phase2_bridge_hire_cells:
        bridge = phase2_bridge
        bridge_reconciliation = "frozen_phase_2_bridge_used_unchanged"
    else:
        bridge = reconcile_bridge_from_frozen_hiring(hiring)
        bridge_reconciliation = "derived_in_memory_from_frozen_hiring_source_rows"
    associations = bridge_associations(features, bridge)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    feature_path = OUTPUT_DIR / "signal_features.parquet"
    write_parquet(feature_path, features)
    summary_path = OUTPUT_DIR / "signal_summary.csv"
    assoc_path = OUTPUT_DIR / "proxy_associations.csv"
    examples_path = OUTPUT_DIR / "signal_examples.csv"
    write_csv(summary_path, summaries)
    write_csv(assoc_path, associations)
    write_csv(examples_path, examples)

    audit_rows = []
    for label, path, count in (("signal_features", feature_path, len(features)), ("signal_summary", summary_path, len(summaries)), ("proxy_associations", assoc_path, len(associations)), ("signal_examples", examples_path, len(examples))):
        blob = path.read_bytes()
        audit_rows.append({"asset": path.name, "row_count": count, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "local_readback_verified": True})
    audit_path = AUDIT_DIR / "signal_audit.csv"
    write_csv(audit_path, audit_rows)
    ecological_cells = len({(r.get("month"), r.get("role_family")) for r in associations if r.get("association_unit")})
    bridge_cells_with_hires = sum(
        int(r.get("observed_hire_male") or 0)
        + int(r.get("observed_hire_female") or 0)
        + int(r.get("observed_hire_unknown") or 0) > 0
        for r in bridge
    )
    manifest = {
        "manifest_type": "version_c_phase_3_signal_diagnostic",
        "run_id": args.run_id,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase_2_inputs": {p.name: {"path": str(p.relative_to(HERE)), "rows": n, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p, n in ((master_path, len(master)), (hiring_path, len(hiring)), (bridge_path, len(phase2_bridge)))},
        "outputs": audit_rows,
        "counts": {"postings": len(features), "descriptions_available": sum(r["description_available"] for r in features), "named_person_reference_postings": sum(r["named_person_count"] > 0 for r in features), "signal_examples": len(examples), "ecological_role_month_feature_cells": ecological_cells, "phase_2_bridge_rows": len(phase2_bridge), "phase_2_bridge_cells_with_observed_hires": phase2_bridge_hire_cells, "phase_3_bridge_rows_used_for_associations": len(bridge), "phase_3_bridge_cells_with_observed_hires": bridge_cells_with_hires},
        "feature_method": {"lexicons": {key: list(value) for key, value in SIGNALS.items()}, "counts_are_lexical_descriptors_not_bias_labels": True, "raw_description_html_and_text_preserved_from_master": True, "named_person_gender_inference": False},
        "association_method": {"unit": "role-month ecological cell", "posting_date_basis": "established Greenhouse posting dates only", "archive_capture_dates_used_as_posting_dates": False, "candidate_level_linkage": False, "causal_claim": False, "bridge_reconciliation": bridge_reconciliation, "phase_2_files_modified": False, "note": "Exact month and role-family intersections are included. If the frozen Phase 2 bridge has no hire counts, Phase 3 derives aggregate counts in memory from employment rows preserved in the frozen hiring outcome file. Cell associations remain descriptive and are not candidate-level predictions.", "estimable": bridge_cells_with_hires > 0, "limitation": "Coverage is limited by observed start-month availability (April-July 2026) and exact role-family matching."},
        "r2_upload_requested": bool(args.r2),
        "audit_csv": str(audit_path.relative_to(HERE)),
    }
    manifest_path = AUDIT_DIR / "signal_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.r2:
        # Reuse Phase 2's signed client implementation so credentials stay in
        # the existing r2.env file and all writes use a unique run prefix.
        from importlib.util import module_from_spec, spec_from_file_location
        phase2_path = HERE / "01_prepare_version_c.py"
        spec = spec_from_file_location("version_c_phase2", phase2_path)
        if not spec or not spec.loader:
            raise RuntimeError("Could not load the Phase 2 R2 client")
        phase2 = module_from_spec(spec)
        import sys
        sys.modules[spec.name] = phase2
        spec.loader.exec_module(phase2)
        phase2.load_env()
        store = phase2.R2()
        try:
            prefix = phase2.os.getenv("R2_PREFIX", "experience-anthropic-2026-04-to-09").strip("/")
            base = f"{prefix}/outputs/version-c/signal/{args.run_id}"
            upload_files = [feature_path, summary_path, assoc_path, examples_path, audit_path, manifest_path]
            for path in upload_files:
                key = f"{base}/{path.name}"
                body = path.read_bytes()
                store.put_immutable(key, body)
                back = store.get(key)
                if hashlib.sha256(back).hexdigest() != hashlib.sha256(body).hexdigest():
                    raise RuntimeError(f"R2 read-back hash mismatch for {key}")
                if path.suffix == ".parquet":
                    import pyarrow.parquet as parquet
                    tmp = OUTPUT_DIR / f".{path.name}.r2check"
                    tmp.write_bytes(back)
                    nread = parquet.read_table(tmp).num_rows
                    tmp.unlink()
                    if nread != len(features):
                        raise RuntimeError(f"R2 row count mismatch for {key}: {nread}")
            manifest["r2_prefix"] = base
            manifest["r2_readback_verified"] = True
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        finally:
            store.client.close()
    print(json.dumps({"status": "signal_diagnostic_complete", "run_id": args.run_id, "counts": manifest["counts"], "outputs": [str(p) for p in (feature_path, summary_path, assoc_path, examples_path, audit_path, manifest_path)], "r2_upload_requested": args.r2}, indent=2))


if __name__ == "__main__":
    main()
