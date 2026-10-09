"""VERSION C — PHASE 2: build auditable, non-linked analysis layers.

This duplicate-only script creates three separate datasets from frozen inputs:
1) Greenhouse posting environment, with posting-language metrics;
2) observed hire outcomes at distinct-person level; and
3) an ecological role-month bridge of aggregate posting and hire counts.

It does not modify any Plan A input, infer sex, or link a person to a posting.
Archive capture dates remain separate from established posting dates.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "outputs"
AUDIT_DIR = HERE / "audit"
ENV_FILE = PROJECT / "r2.env"

GREENHOUSE_R2_KEY = (
    "experience-anthropic-2026-04-to-09/filtered/job-postings/analysis/"
    "20260929T091413Z/historical_greenhouse_analytical_master.json"
)
LANGUAGE_R2_KEY = (
    "experience-anthropic-2026-04-to-09/outputs/job-postings/language-analysis/"
    "20260929T092904Z/posting_language_metrics.json"
)
HIRING_R2_KEY = "filtered/analysis/anthropic_hires_enriched_current_snapshot.parquet"
STUDY_START = dt.date(2026, 4, 1)
STUDY_END = dt.date(2026, 9, 30)
SEX_MAP = {"male": "MALE", "female": "FEMALE"}


def load_env() -> None:
    if not ENV_FILE.exists():
        raise FileNotFoundError(f"R2 settings file not found: {ENV_FILE}")
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def stamp() -> str:
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return now_utc().isoformat().replace("+00:00", "Z")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=json_default) + "\n").encode()


def json_default(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if hasattr(value, "as_py"):
        return value.as_py()
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


class R2:
    """Minimal S3-compatible R2 client for immutable inputs and output read-back."""

    def __init__(self) -> None:
        endpoint = os.environ["R2_ENDPOINT"].rstrip("/")
        parsed = urlparse(endpoint)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("R2_ENDPOINT must be an absolute URL")
        self.endpoint, self.host = endpoint, parsed.netloc
        self.access = os.environ["R2_ACCESS_KEY_ID"]
        self.secret = os.environ["R2_SECRET_ACCESS_KEY"]
        self.bucket = os.environ["R2_BUCKET"]
        self.client = httpx.Client(timeout=300, follow_redirects=False)

    def request(self, method: str, key: str, body: bytes = b"") -> httpx.Response:
        current = now_utc()
        amz_date, day = current.strftime("%Y%m%dT%H%M%SZ"), current.strftime("%Y%m%d")
        payload = sha(body)
        uri = f"/{quote(self.bucket, safe='')}/{quote(key, safe='/')}"
        headers = {"host": self.host, "x-amz-content-sha256": payload, "x-amz-date": amz_date}
        if method == "PUT":
            headers.update({"if-none-match": "*", "content-type": "application/octet-stream"})
        signed_names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name].strip()}\n" for name in sorted(headers))
        canonical = "\n".join((method, uri, "", canonical_headers, signed_names, payload))
        scope = f"{day}/auto/s3/aws4_request"
        to_sign = "\n".join(("AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()))
        date_key = hmac.new(("AWS4" + self.secret).encode(), day.encode(), hashlib.sha256).digest()
        region_key = hmac.new(date_key, b"auto", hashlib.sha256).digest()
        service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
        signing_key = hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).hexdigest()
        headers["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={self.access}/{scope}, "
                                    f"SignedHeaders={signed_names}, Signature={signature}")
        response = self.client.request(method, self.endpoint + uri,
            headers={key: value for key, value in headers.items() if key != "host"}, content=body)
        response.raise_for_status()
        return response

    def get(self, key: str) -> bytes:
        for attempt in range(4):
            try:
                return self.request("GET", key).content
            except httpx.HTTPError:
                if attempt == 3:
                    raise
                self.client.close()
                self.client = httpx.Client(timeout=300, follow_redirects=False)
                time.sleep(2 ** attempt)
        raise RuntimeError("R2 GET retry exhausted")

    def put_immutable(self, key: str, body: bytes) -> None:
        for attempt in range(4):
            try:
                self.request("PUT", key, body)
                return
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 412 and sha(self.get(key)) == sha(body):
                    return
                raise
            except httpx.HTTPError:
                if attempt == 3:
                    raise
                self.client.close()
                self.client = httpx.Client(timeout=300, follow_redirects=False)
                time.sleep(2 ** attempt)


def save_parquet(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to create an empty analytical table: {path.name}")
    # JSON-encode nested source payloads so the full source evidence is retained
    # while each output has a stable flat Parquet schema.
    flat = []
    for row in rows:
        flat_row = {}
        for key, value in row.items():
            if isinstance(value, (dict, list, tuple, set)):
                flat_row[key] = json.dumps(value, ensure_ascii=False, sort_keys=True, default=json_default)
            elif isinstance(value, (dt.datetime, dt.date)):
                flat_row[key] = value.isoformat()
            else:
                flat_row[key] = value
        flat.append(flat_row)
    table = pa.Table.from_pylist(flat)
    pq.write_table(table, path, compression="zstd", version="2.6")
    check = pq.read_table(path)
    if check.num_rows != len(rows):
        raise RuntimeError(f"Parquet row count mismatch for {path.name}")


def read_parquet(path: Path) -> list[dict[str, Any]]:
    return pq.read_table(path).to_pylist()


def month_of(value: Any) -> str | None:
    if isinstance(value, dt.datetime):
        return value.strftime("%Y-%m")
    if isinstance(value, dt.date):
        return value.strftime("%Y-%m")
    if not isinstance(value, str) or len(value.strip()) < 7:
        return None
    text = value.strip()
    try:
        year, month = int(text[:4]), int(text[5:7])
        return f"{year:04d}-{month:02d}" if 1 <= month <= 12 else None
    except (ValueError, TypeError):
        return None


def as_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return dt.date.fromisoformat(value[:10])
        except ValueError:
            return None


def within_study(value: Any) -> bool:
    date_value = as_date(value)
    return bool(date_value and STUDY_START <= date_value <= STUDY_END)


def posting_key(record: dict[str, Any]) -> str:
    for field in ("greenhouse_job_id", "dedup_key", "absolute_url"):
        value = record.get(field)
        if value:
            return f"{field}:{value}"
    raise ValueError("Greenhouse row has no stable posting identifier")


def source_inputs(args: argparse.Namespace, store: R2) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    input_meta: dict[str, str] = {}
    if args.greenhouse:
        gh_path = Path(args.greenhouse).expanduser().resolve()
        gh_data = gh_path.read_bytes()
        gh_label = str(gh_path)
    else:
        gh_data = store.get(GREENHOUSE_R2_KEY)
        gh_label = GREENHOUSE_R2_KEY
    gh_payload = json.loads(gh_data)
    gh_records = gh_payload.get("records")
    if not isinstance(gh_records, list):
        raise ValueError("Greenhouse input does not contain a records array")
    input_meta["greenhouse_source"] = gh_label
    input_meta["greenhouse_sha256"] = sha(gh_data)

    if args.language:
        language_path = Path(args.language).expanduser().resolve()
        language_data = language_path.read_bytes()
        language_label = str(language_path)
    else:
        language_data = store.get(LANGUAGE_R2_KEY)
        language_label = LANGUAGE_R2_KEY
    language_payload = json.loads(language_data)
    language_records = language_payload.get("records")
    if not isinstance(language_records, list):
        raise ValueError("Language metrics input does not contain a records array")
    input_meta["language_metrics_source"] = language_label
    input_meta["language_metrics_sha256"] = sha(language_data)

    if args.hiring:
        hire_path = Path(args.hiring).expanduser().resolve()
        hire_data = hire_path.read_bytes()
        hire_local = hire_path
        hire_label = str(hire_path)
    else:
        hire_data = store.get(HIRING_R2_KEY)
        hire_local = OUTPUT_DIR / ".source_anthropic_hires_enriched.parquet"
        hire_local.parent.mkdir(parents=True, exist_ok=True)
        hire_local.write_bytes(hire_data)
        hire_label = HIRING_R2_KEY
    hire_rows = read_parquet(hire_local)
    input_meta["hiring_source"] = hire_label
    input_meta["hiring_sha256"] = sha(hire_data)
    input_meta["hiring_rows"] = str(len(hire_rows))

    if len(gh_records) != 1246 or len(language_records) != len(gh_records):
        raise ValueError(f"Unexpected posting row counts: greenhouse={len(gh_records)}, language={len(language_records)}")
    if len(hire_rows) != 1097 or len({str(row.get("PERSON_ID")) for row in hire_rows}) != 1095:
        raise ValueError(f"Unexpected hiring snapshot shape: employment_rows={len(hire_rows)}, distinct_people={len({str(row.get('PERSON_ID')) for row in hire_rows})}")

    for index, (posting, language) in enumerate(zip(gh_records, language_records)):
        if posting_key(posting) != posting_key(language):
            raise ValueError(f"Posting/language record alignment failed at row {index}; refusing an ambiguous join")
    return gh_payload, language_payload, hire_rows, input_meta


def make_master(gh_payload: dict[str, Any], language_payload: dict[str, Any]) -> list[dict[str, Any]]:
    postings = gh_payload["records"]
    language = language_payload["records"]
    rows: list[dict[str, Any]] = []
    for posting, lang in zip(postings, language):
        # Both source layers are posting-level datasets and are aligned on a
        # stable posting key; this is not a person-to-posting linkage.
        row = dict(posting)
        lang_fields = (
            "description_available", "description_word_count", "named_person_mentions",
            "named_person_names", "masculine_pronoun_count", "feminine_pronoun_count",
            "explicit_male_reference_count", "explicit_female_reference_count",
            "gendered_reference_flag", "testimonial_or_biography_flag", "example_person_flag",
            "manual_review_required", "language_analysis_retrieved_at",
        )
        for field in lang_fields:
            row[f"language_{field}"] = lang.get(field)
        row["version_c_posting_id"] = posting_key(posting)
        row["candidate_level_hire_linkage"] = False
        row["posting_role_family"] = posting.get("research_subclass") or posting.get("posting_classification")
        rows.append(row)
    return rows


def normalize_sex(value: Any) -> str:
    if value is None or not str(value).strip():
        return "UNKNOWN"
    normalized = str(value).strip().lower()
    if normalized not in SEX_MAP:
        raise ValueError(f"Unexpected raw source SEX value {value!r}; no implicit mapping permitted")
    return SEX_MAP[normalized]


def make_hiring(hire_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in hire_rows:
        person_id = row.get("PERSON_ID")
        if person_id is None:
            raise ValueError("Hiring source has a row without PERSON_ID")
        by_person[str(person_id)].append(row)
    if len(by_person) != 1095:
        raise ValueError(f"Expected 1,095 distinct people; got {len(by_person)}")

    outcomes: list[dict[str, Any]] = []
    employment_rows: list[dict[str, Any]] = []
    for person_id, records in sorted(by_person.items()):
        source_sexes = {str(row.get("SEX")).strip().lower() for row in records
                        if row.get("SEX") is not None and str(row.get("SEX")).strip()}
        if len(source_sexes) > 1:
            raise ValueError(f"Conflicting source SEX values for person key {person_id}; preserve and resolve explicitly")
        source_sex = next(iter(source_sexes), None)
        outcome_sex = normalize_sex(source_sex)
        families = sorted({str(row.get("ROLE_CATEGORY") or row.get("TITLE_ROLE") or row.get("TITLE_NAME") or "Unknown role").strip()
                           for row in records})
        months = sorted({month_of(row.get("START_DATE")) for row in records if month_of(row.get("START_DATE"))})
        research_states = sorted({str(row.get("research_status") or "") for row in records if row.get("research_status")})
        # Preserve the source employment rows in a JSON column. Outcome remains
        # one row per distinct observed person; no role row is discarded.
        outcomes.append({
            "PERSON_ID": person_id,
            "source_SEX": source_sex,
            "outcome_sex": outcome_sex,
            "employment_row_count": len(records),
            "role_families": families,
            "observed_start_months": months,
            "research_status_values": research_states,
            "employment_records": records,
            "sex_inferred": False,
        })
        for row in records:
            month = month_of(row.get("START_DATE"))
            if not month or not within_study(row.get("START_DATE")):
                continue
            family = str(row.get("ROLE_CATEGORY") or row.get("TITLE_ROLE") or row.get("TITLE_NAME") or "Unknown role").strip()
            employment_rows.append({"PERSON_ID": person_id, "month": month, "role_family": family,
                                    "outcome_sex": outcome_sex, "source_SEX": source_sex,
                                    "research_status": row.get("research_status")})
    return outcomes, employment_rows


def make_bridge(master: list[dict[str, Any]], hire_employment: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agg: dict[tuple[str, str], dict[str, Any]] = {}

    def cell(month: str, family: str) -> dict[str, Any]:
        key = (month, family)
        if key not in agg:
            agg[key] = {
                "month": month, "role_family": family,
                "greenhouse_postings_with_established_in_window_date": 0,
                "archive_capture_only_candidates": 0,
                "observed_hire_people": 0, "observed_hire_male": 0,
                "observed_hire_female": 0, "observed_hire_unknown": 0,
                "bridge_type": "aggregate_role_month_ecological_only",
                "candidate_level_linkage": False,
            }
        return agg[key]

    for row in master:
        family = str(row.get("posting_role_family") or "Review Needed")
        evidence_class = row.get("date_evidence_class")
        if evidence_class == "GREENHOUSE_POSTING_DATE":
            month = month_of(row.get("first_published_at") or row.get("posting_date_if_known"))
            if month and "2026-04" <= month <= "2026-09":
                cell(month, family)["greenhouse_postings_with_established_in_window_date"] += 1
        elif evidence_class == "ARCHIVE_CAPTURE_ONLY":
            month = month_of(row.get("archive_capture_date"))
            if month and "2026-04" <= month <= "2026-09":
                cell(month, family)["archive_capture_only_candidates"] += 1

    # A person contributes at most once to a role-family/month cell even where
    # the source has multiple employment rows for that same combination.
    unique_hires = {(row["PERSON_ID"], row["month"], row["role_family"]): row for row in hire_employment}
    for row in unique_hires.values():
        target = cell(row["month"], row["role_family"])
        target["observed_hire_people"] += 1
        target[f"observed_hire_{row['outcome_sex'].lower()}"] += 1
    return [agg[key] for key in sorted(agg)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--greenhouse", help="Local verified historical_greenhouse_analytical_master.json; defaults to its frozen R2 key")
    parser.add_argument("--hiring", help="Local observed-hire Parquet; defaults to the verified R2 enriched snapshot")
    parser.add_argument("--language", help="Local posting_language_metrics.json; defaults to its frozen R2 key")
    parser.add_argument("--run-id", help="Optional unique run ID; defaults to current UTC timestamp")
    args = parser.parse_args()

    load_env()
    store = R2()
    run_id = args.run_id or stamp()
    retrieved_at = iso_now()
    try:
        gh_payload, language_payload, hire_rows, input_meta = source_inputs(args, store)
        posting_rows = make_master(gh_payload, language_payload)
        person_rows, hire_employment_rows = make_hiring(hire_rows)
        bridge_rows = make_bridge(posting_rows, hire_employment_rows)
        if len(posting_rows) != 1246 or len(person_rows) != 1095:
            raise RuntimeError("Version C output row counts do not match frozen source expectations")
        if not all(row["candidate_level_hire_linkage"] is False for row in posting_rows):
            raise RuntimeError("A candidate-level link was unexpectedly created")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        local_outputs = {
            "version_c_master.parquet": posting_rows,
            "version_c_hiring_outcomes.parquet": person_rows,
            "version_c_role_month_bridge.parquet": bridge_rows,
        }
        output_details = []
        prefix = os.getenv("R2_PREFIX", "experience-anthropic-2026-04-to-09").strip("/")
        r2_base = f"{prefix}/outputs/version-c/{run_id}" if prefix else f"outputs/version-c/{run_id}"
        for filename, rows in local_outputs.items():
            path = OUTPUT_DIR / filename
            save_parquet(rows, path)
            body = path.read_bytes()
            key = f"{r2_base}/{filename}"
            store.put_immutable(key, body)
            readback = store.get(key)
            if sha(readback) != sha(body):
                raise RuntimeError(f"R2 output read-back SHA-256 mismatch: {key}")
            readback_path = OUTPUT_DIR / f".{filename}.readback"
            readback_path.write_bytes(readback)
            check_rows = pq.read_table(readback_path).num_rows
            readback_path.unlink()
            if check_rows != len(rows):
                raise RuntimeError(f"R2 output row count mismatch for {key}: {check_rows} != {len(rows)}")
            output_details.append({"file": filename, "r2_key": key, "row_count": len(rows),
                                   "bytes": len(body), "sha256": sha(body), "readback_verified": True})

        master_dates: dict[str, int] = defaultdict(int)
        for row in posting_rows:
            master_dates[str(row.get("date_evidence_class") or "MISSING")] += 1
        sex_counts: dict[str, int] = defaultdict(int)
        for row in person_rows:
            sex_counts[row["outcome_sex"]] += 1
        audit_rows = [
            {"dataset": "version_c_master", "row_count": len(posting_rows), "distinct_ids": len({row["version_c_posting_id"] for row in posting_rows}), "r2_key": output_details[0]["r2_key"], "sha256": output_details[0]["sha256"], "readback_verified": True},
            {"dataset": "version_c_hiring_outcomes", "row_count": len(person_rows), "distinct_ids": len({row["PERSON_ID"] for row in person_rows}), "r2_key": output_details[1]["r2_key"], "sha256": output_details[1]["sha256"], "readback_verified": True},
            {"dataset": "version_c_role_month_bridge", "row_count": len(bridge_rows), "distinct_ids": len({(row["month"], row["role_family"]) for row in bridge_rows}), "r2_key": output_details[2]["r2_key"], "sha256": output_details[2]["sha256"], "readback_verified": True},
        ]
        audit_csv = AUDIT_DIR / "version_c_master_audit.csv"
        with audit_csv.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(audit_rows[0]))
            writer.writeheader()
            writer.writerows(audit_rows)
        manifest = {
            "manifest_type": "version_c_phase_2_master_build",
            "version": "C",
            "run_id": run_id,
            "created_at_utc": retrieved_at,
            "input_sources": input_meta,
            "frozen_source_keys": {"greenhouse_analytical_master": GREENHOUSE_R2_KEY,
                                   "posting_language_metrics": LANGUAGE_R2_KEY,
                                   "hiring_enriched_snapshot": HIRING_R2_KEY},
            "study_window": {"start": STUDY_START.isoformat(), "end": STUDY_END.isoformat()},
            "outputs": output_details,
            "counts": {"greenhouse_posting_rows": len(posting_rows), "distinct_hiring_people": len(person_rows),
                       "role_month_bridge_rows": len(bridge_rows), "hiring_outcome_sex": dict(sex_counts),
                       "posting_date_evidence": dict(master_dates)},
            "methods": {
                "sex_mapping": {"male": "MALE", "female": "FEMALE", "blank_or_null": "UNKNOWN"},
                "source_SEX_preserved": True,
                "sex_inferred_from_name": False,
                "candidate_level_posting_to_hire_linkage": False,
                "bridge_is_aggregate_ecological_role_month_only": True,
                "archive_capture_date_is_posting_date": False,
                "archive_capture_only_counts_kept_separate": True,
                "multiple_employment_rows": "Hiring output has one row per person and retains all source employment rows in employment_records; bridge counts distinct people per month-role cell.",
            },
            "coverage_limitations": [
                "Hiring input represents the current Dewey/PDL observed snapshot, with observed starts in April-July 2026; absent August/September starts do not imply zero hiring.",
                "The role-month bridge is ecological and does not identify which posting, if any, led to a particular hire.",
                "Archive capture-only records provide archive availability evidence, not established posting dates.",
            ],
            "row_audit_csv": str(audit_csv.relative_to(HERE)),
            "row_audit_csv_sha256": sha(audit_csv.read_bytes()),
        }
        manifest_path = AUDIT_DIR / "version_c_run_manifest.json"
        manifest_bytes = json_bytes(manifest)
        manifest_path.write_bytes(manifest_bytes)
        manifest_key = f"{r2_base}/version_c_run_manifest.json"
        store.put_immutable(manifest_key, manifest_bytes)
        if sha(store.get(manifest_key)) != sha(manifest_bytes):
            raise RuntimeError("R2 manifest read-back verification failed")
        print(json.dumps({"status": "version_c_phase_2_complete", "run_id": run_id,
                          "outputs": output_details, "manifest_r2_key": manifest_key,
                          "audit_csv": str(audit_csv), "manifest": str(manifest_path),
                          "sex_counts": dict(sex_counts), "date_evidence_counts": dict(master_dates)}, indent=2))
    finally:
        store.client.close()


if __name__ == "__main__":
    main()
