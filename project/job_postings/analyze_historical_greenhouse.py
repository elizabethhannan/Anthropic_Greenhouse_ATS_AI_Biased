"""Create a provenance-preserving analytical layer for historical Anthropic jobs.

This script reads the verified deduplicated recovery corpus from R2, adds a
transparent role taxonomy and separate date-evidence fields, then writes and
reads back immutable master and audit outputs. It does not analyze language,
gender, or hiring outcomes.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "r2.env"
SOURCE_RUN = "20260929T074631Z"
SOURCE_KEY = f"filtered/job-postings/{SOURCE_RUN}/historical_greenhouse_deduplicated.json"
SOURCE_AUDIT_KEY = f"audit/job-postings/{SOURCE_RUN}/historical_greenhouse_audit.json"
START = dt.date(2026, 4, 1)
END = dt.date(2026, 9, 30)
TAXONOMY = [
    "Research Scientist", "Research Engineer", "Research-oriented MTS",
    "Fellows Researcher", "Alignment / AI Safety", "Interpretability",
    "Pre-training", "Post-training", "Reinforcement Learning", "Evaluations",
    "Model Behavior", "AI/ML Research - Other", "Engineering - Non-Research",
    "Other / Non-Research", "Review Needed",
]
RESEARCH_CLASSES = set(TAXONOMY[:12])


def load_env() -> None:
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso_now() -> str:
    return utcnow().isoformat().replace("+00:00", "Z")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def parse_date(value: Any) -> dt.date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return dt.date.fromisoformat(value[:10])
        except ValueError:
            return None


class R2:
    def __init__(self) -> None:
        endpoint = os.environ["R2_ENDPOINT"].rstrip("/")
        parsed = urlparse(endpoint)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("R2_ENDPOINT must be an absolute URL")
        self.endpoint, self.host = endpoint, parsed.netloc
        self.access = os.environ["R2_ACCESS_KEY_ID"]
        self.secret = os.environ["R2_SECRET_ACCESS_KEY"]
        self.bucket = os.environ["R2_BUCKET"]
        self.client = httpx.Client(timeout=180, follow_redirects=False)

    def request(self, method: str, key: str, body: bytes = b"") -> httpx.Response:
        now = utcnow()
        stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
        digest = sha(body)
        uri = f"/{quote(self.bucket, safe='')}/{quote(key, safe='/')}"
        headers = {"host": self.host, "x-amz-content-sha256": digest, "x-amz-date": stamp}
        if method == "PUT":
            headers.update({"if-none-match": "*", "content-type": "application/json; charset=utf-8"})
        names = ";".join(sorted(headers))
        canon_headers = "".join(f"{k}:{headers[k].strip()}\n" for k in sorted(headers))
        canon = "\n".join((method, uri, "", canon_headers, names, digest))
        scope = f"{day}/auto/s3/aws4_request"
        to_sign = "\n".join(("AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canon.encode()).hexdigest()))
        kd = hmac.new(("AWS4" + self.secret).encode(), day.encode(), hashlib.sha256).digest()
        kr = hmac.new(kd, b"auto", hashlib.sha256).digest()
        ks = hmac.new(kr, b"s3", hashlib.sha256).digest()
        signing = hmac.new(ks, b"aws4_request", hashlib.sha256).digest()
        sig = hmac.new(signing, to_sign.encode(), hashlib.sha256).hexdigest()
        headers["Authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access}/{scope}, SignedHeaders={names}, Signature={sig}"
        )
        outgoing = {k: v for k, v in headers.items() if k != "host"}
        response = self.client.request(method, self.endpoint + uri, headers=outgoing, content=body)
        response.raise_for_status()
        return response

    def get(self, key: str) -> bytes:
        for attempt in range(4):
            try:
                return self.request("GET", key).content
            except httpx.TransportError:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("R2 GET retry exhausted")

    def put(self, key: str, data: bytes) -> None:
        for attempt in range(4):
            try:
                self.request("PUT", key, data)
                return
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 412 and sha(self.get(key)) == sha(data):
                    return
                raise
            except httpx.TransportError:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)


def items(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(str(v) for v in value.values() if v is not None)
    if isinstance(value, list):
        return " ".join(items(v) for v in value)
    return str(value)


def classify(record: dict[str, Any]) -> tuple[str, bool | None, bool, str, str | None]:
    title = str(record.get("exact_title") or "")
    dept = items(record.get("departments"))
    office = items(record.get("offices"))
    desc = str(record.get("description_text") or "")
    title_dept = f"{title} {dept}"
    td = title_dept.casefold()
    fellowship = bool(re.search(r"\bfellows?\b|\bfellowship\b", title, re.I))
    if not title.strip():
        return "Review Needed", None, fellowship, "Exact title is missing; role type cannot be assigned reliably.", None

    # Classification is grounded primarily in exact title and department. Description
    # is used only for specific research-function signals, never generic company copy.
    rules: list[tuple[str, str, str]] = [
        (r"\bfellows?\b|\bfellowship\b", "Fellows Researcher", "title names a fellow/fellowship role"),
        (r"research scientist|scientist.{0,25}research", "Research Scientist", "title names a research scientist role"),
        (r"research engineer|research.{0,15}software engineer", "Research Engineer", "title names a research engineering role"),
        (r"\bmts\b|member of technical staff", "Research-oriented MTS", "title names MTS; research department/context supports research orientation"),
        (r"alignment|ai safety|safety research", "Alignment / AI Safety", "title or department names alignment/AI safety"),
        (r"interpretability|mechanistic interpret", "Interpretability", "title or department names interpretability"),
        (r"pre[- ]training|pretraining", "Pre-training", "title or department names pre-training"),
        (r"post[- ]training|posttraining", "Post-training", "title or department names post-training"),
        (r"reinforcement learning|\brlhf\b", "Reinforcement Learning", "title or department names reinforcement learning"),
        (r"evaluation|evaluations|evals", "Evaluations", "title or department names model evaluations"),
        (r"model behavior|model behaviour", "Model Behavior", "title or department names model behavior"),
    ]
    research_context = bool(re.search(r"research|scientist|machine learning|\bml\b|\bai\b", td, re.I))
    for pattern, category, reason in rules:
        if re.search(pattern, td, re.I):
            if category == "Research-oriented MTS" and not research_context:
                return "Review Needed", None, fellowship, "MTS appears in title, but research orientation is not established by title/department.", None
            return category, True, fellowship, reason, category

    # A description only supports classification when it explicitly describes a
    # research function or role-specific research group, not generic Anthropic copy.
    if re.search(r"\bconduct (?:original )?research\b|\bresearch scientist\b|\bmachine learning research\b", desc, re.I):
        return "AI/ML Research - Other", True, fellowship, "Description explicitly identifies research work; no narrower title category matched.", "AI/ML Research - Other"
    if re.search(r"engineer|engineering|software|infrastructure", title, re.I):
        return "Engineering - Non-Research", False, fellowship, "Engineering title with no specific research category signal.", None
    if re.search(r"research|scientist|machine learning|\bml\b", td, re.I):
        return "AI/ML Research - Other", True, fellowship, "Title or department indicates research/ML, without a narrower category match.", "AI/ML Research - Other"
    if not title.strip() or (not desc.strip() and not dept.strip() and len(title.split()) <= 1):
        return "Review Needed", None, fellowship, "Insufficient title/description/department evidence for a reliable role classification.", None
    return "Other / Non-Research", False, fellowship, "No research or engineering role signal in the title/department evidence.", None


def date_class(record: dict[str, Any]) -> tuple[str, str]:
    posted = parse_date(record.get("first_published_at")) or parse_date(record.get("posting_date_if_known"))
    captured = parse_date(record.get("archive_capture_date"))
    if posted and START <= posted <= END:
        return "GREENHOUSE_POSTING_DATE", "Greenhouse first-published date is within 2026-04-01 through 2026-09-30."
    if posted:
        return "POSTING_DATE_OUTSIDE_WINDOW", f"Established posting date {posted.isoformat()} is outside the study window."
    if captured and START <= captured <= END:
        return "ARCHIVE_CAPTURE_ONLY", "Internet Archive capture is in the study window; actual posting date is not established."
    if record.get("historical_status") == "current_only":
        return "CURRENT_ONLY", "Current listing has no dated evidence establishing availability in the study window."
    return "DATE_UNRESOLVED", "Available source evidence does not establish a posting date or in-window archive capture."


def main() -> None:
    load_env()
    store = R2()
    try:
        source_bytes = store.get(SOURCE_KEY)
        source = json.loads(source_bytes)
        source_audit = json.loads(store.get(SOURCE_AUDIT_KEY))
        records = source.get("records")
        if not isinstance(records, list) or len(records) != 1246:
            raise RuntimeError(f"Unexpected verified corpus shape: {len(records) if isinstance(records, list) else 'missing'} records")
        if source.get("candidate_record_count") != len(records):
            raise RuntimeError("Source candidate_record_count does not match the records array.")
        if source_audit.get("counts", {}).get("unique_reconciled_candidates_including_current_or_unresolved") != len(records):
            raise RuntimeError("Source recovery audit does not corroborate the deduplicated corpus row count.")

        retrieved = iso_now()
        master: list[dict[str, Any]] = []
        for original in records:
            row = dict(original)  # retain every original field and value
            category, research_flag, fellowship_flag, reason, subclass = classify(row)
            evidence_class, evidence_reason = date_class(row)
            row.update({
                "posting_classification": category,
                "research_flag": research_flag,
                "research_subclass": subclass,
                "fellowship_flag": fellowship_flag,
                "date_evidence_class": evidence_class,
                "date_evidence_reason": evidence_reason,
                "classification_reason": reason,
                "analysis_source_r2_key": SOURCE_KEY,
                "analysis_retrieved_at": retrieved,
            })
            master.append(row)

        class_counts = Counter(r["posting_classification"] for r in master)
        date_counts = Counter(r["date_evidence_class"] for r in master)
        subclass_counts = Counter(r["research_subclass"] for r in master if r["research_subclass"])
        research_true = sum(r["research_flag"] is True for r in master)
        research_false = sum(r["research_flag"] is False for r in master)
        research_unknown = sum(r["research_flag"] is None for r in master)
        fellow_true = sum(bool(r["fellowship_flag"]) for r in master)
        review = [r for r in master if r["posting_classification"] == "Review Needed"]
        dts = [parse_date(r.get("first_published_at")) for r in master]
        dts = [d for d in dts if d and START <= d <= END]
        meta = {"analysis_type": "historical_greenhouse_classification", "source_r2_key": SOURCE_KEY,
                "source_sha256": sha(source_bytes), "source_recovery_audit_r2_key": SOURCE_AUDIT_KEY,
                "source_record_count": len(master), "study_window": {"start": START.isoformat(), "end": END.isoformat()},
                "generated_at": retrieved}
        outputs: dict[str, tuple[dict[str, Any], int]] = {}
        outputs["historical_greenhouse_analytical_master.json"] = ({**meta, "records": master}, len(master))
        outputs["classification_summary.json"] = ({**meta, "record_count": len(master),
            "taxonomy_order": TAXONOMY,
            "posting_classification_counts": {name: class_counts.get(name, 0) for name in TAXONOMY},
            "research_subclass_counts": {name: subclass_counts.get(name, 0) for name in TAXONOMY if name in RESEARCH_CLASSES},
            "research_flag_counts": {"true": research_true, "false": research_false, "unknown_review": research_unknown},
            "fellowship_flag_counts": {"true": fellow_true, "false": len(master)-fellow_true}}, len(master))
        outputs["date_evidence_summary.json"] = ({**meta, "record_count": len(master),
            "date_evidence_class_counts": {name: date_counts.get(name, 0) for name in
                ("GREENHOUSE_POSTING_DATE", "ARCHIVE_CAPTURE_ONLY", "POSTING_DATE_OUTSIDE_WINDOW", "CURRENT_ONLY", "DATE_UNRESOLVED")},
            "verified_in_window_posting_date_count": date_counts.get("GREENHOUSE_POSTING_DATE", 0),
            "archive_supported_without_posting_date_count": date_counts.get("ARCHIVE_CAPTURE_ONLY", 0),
            "earliest_supported_posting_date": min(dts).isoformat() if dts else None,
            "latest_supported_posting_date": max(dts).isoformat() if dts else None,
            "date_fields_used": ["first_published_at", "posting_date_if_known", "archive_capture_date"],
            "updated_at_used_as_posting_date": False}, len(master))
        outputs["research_fellowship_summary.json"] = ({**meta, "record_count": len(master),
            "research_flag_counts": {"true": research_true, "false": research_false, "unknown_review": research_unknown},
            "fellowship_flag_counts": {"true": fellow_true, "false": len(master)-fellow_true},
            "research_and_fellowship_true": sum(r["research_flag"] is True and r["fellowship_flag"] for r in master),
            "research_subclass_counts": {name: subclass_counts.get(name, 0) for name in TAXONOMY if name in RESEARCH_CLASSES}}, len(master))
        outputs["review_needed_audit.json"] = ({**meta, "record_count": len(master), "review_needed_count": len(review),
            "records": [{k: r.get(k) for k in ("greenhouse_job_id", "exact_title", "absolute_url", "location",
                "source_url", "source_type", "source_types", "historical_status", "date_evidence_class",
                "description_html", "classification_reason")} for r in review]}, len(review))

        runstamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
        prefix = f"{os.getenv('R2_PREFIX', '').strip('/')}/" if os.getenv("R2_PREFIX", "").strip("/") else ""
        base = f"{prefix}filtered/job-postings/analysis/{runstamp}"
        audit_base = f"{prefix}audit/job-postings/analysis/{runstamp}"
        verification = []
        for filename, (payload, expected_rows) in outputs.items():
            key = f"{base}/{filename}" if filename == "historical_greenhouse_analytical_master.json" else f"{audit_base}/{filename}"
            body = encode(payload)
            store.put(key, body)
            readback = store.get(key)
            parsed = json.loads(readback)
            if sha(readback) != sha(body):
                raise RuntimeError(f"R2 read-back hash mismatch for {key}")
            if filename.endswith("analytical_master.json"):
                actual_rows = len(parsed.get("records", []))
            elif filename == "review_needed_audit.json":
                actual_rows = parsed.get("review_needed_count")
                if actual_rows != len(parsed.get("records", [])):
                    raise RuntimeError("Review audit row count mismatch on R2 read-back.")
            else:
                actual_rows = parsed.get("record_count")
            if actual_rows != expected_rows:
                raise RuntimeError(f"R2 row count mismatch for {key}: {actual_rows} != {expected_rows}")
            verification.append({"key": key, "sha256": sha(readback), "bytes": len(readback),
                                 "row_count": actual_rows, "readback_verified": True})

        audit = {**meta, "analysis_audit": "readback_verified", "outputs": verification,
                 "classification_counts": {name: class_counts.get(name, 0) for name in TAXONOMY},
                 "date_evidence_counts": {name: date_counts.get(name, 0) for name in
                    ("GREENHOUSE_POSTING_DATE", "ARCHIVE_CAPTURE_ONLY", "POSTING_DATE_OUTSIDE_WINDOW", "CURRENT_ONLY", "DATE_UNRESOLVED")},
                 "review_needed_count": len(review), "all_output_objects_read_back_and_verified": True}
        audit_key = f"{audit_base}/analysis_audit.json"
        audit_body = encode(audit)
        store.put(audit_key, audit_body)
        audit_readback = store.get(audit_key)
        if sha(audit_readback) != sha(audit_body) or not json.loads(audit_readback).get("all_output_objects_read_back_and_verified"):
            raise RuntimeError("Analysis audit R2 read-back verification failed.")

        print(json.dumps({"source_r2_key": SOURCE_KEY, "source_rows": len(records),
            "outputs": verification, "analysis_audit_key": audit_key,
            "analysis_audit_readback_verified": True,
            "posting_classification_counts": {name: class_counts.get(name, 0) for name in TAXONOMY},
            "date_evidence_counts": {name: date_counts.get(name, 0) for name in
                ("GREENHOUSE_POSTING_DATE", "ARCHIVE_CAPTURE_ONLY", "POSTING_DATE_OUTSIDE_WINDOW", "CURRENT_ONLY", "DATE_UNRESOLVED")},
            "research_true": research_true, "fellowship_true": fellow_true, "review_needed": len(review)}, indent=2))
    finally:
        store.client.close()


if __name__ == "__main__":
    main()
