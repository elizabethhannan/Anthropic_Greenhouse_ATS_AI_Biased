"""Capture Anthropic's current public Greenhouse job board to R2.

This script only captures the live public board. It does not search for
historical or closed roles.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import html
import json
import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx


BOARD_TOKEN = "anthropic"
BOARD_API_URL = f"https://boards-api.greenhouse.io/v1/boards/{BOARD_TOKEN}/jobs"
BOARD_URL = f"https://job-boards.greenhouse.io/{BOARD_TOKEN}"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(__file__).resolve().parent / "snapshots"
ENV_FILE = PROJECT_ROOT / "r2.env"
USER_AGENT = "AnthropicBiasData-current-greenhouse-snapshot/1.0"


class _TextExtractor(HTMLParser):
    """Extract readable text without changing the separately preserved HTML."""

    BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "dd", "div",
        "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li",
        "main", "nav", "ol", "p", "pre", "section", "table", "td",
        "th", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def description_text(description_html: str | None) -> str | None:
    if description_html is None:
        return None
    decoded = description_html
    for _ in range(3):
        next_decoded = html.unescape(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    parser = _TextExtractor()
    parser.feed(decoded)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    lines = [re.sub(r"[\t\r\f\v ]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line)).strip()


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE entries without echoing secrets or requiring dotenv."""
    if not path.exists():
        raise RuntimeError(f"R2 environment file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("\"'")
        if name and value:
            os.environ.setdefault(name, value)


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required setting {name} is missing from the environment and r2.env.")
    return value


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fetch_board() -> tuple[dict[str, Any], str]:
    retrieved_at = utc_now().isoformat().replace("+00:00", "Z")
    response = httpx.get(
        BOARD_API_URL,
        params={"content": "true"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=90,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise RuntimeError("Greenhouse response did not contain a jobs list.")
    total = payload.get("meta", {}).get("total")
    if total is not None and total != len(payload["jobs"]):
        raise RuntimeError(f"Greenhouse returned {len(payload['jobs'])} jobs but meta.total={total}.")
    return payload, retrieved_at


def normalize_job(job: dict[str, Any], retrieved_at: str) -> dict[str, Any]:
    # Keep every API field, including Greenhouse's exact description HTML.
    record = dict(job)
    record.update(
        {
            "job_id": job.get("id"),
            "exact_title": job.get("title"),
            "url": job.get("absolute_url"),
            "location": job.get("location"),
            "requisition_id": job.get("requisition_id"),
            "department": job.get("departments"),
            "office": job.get("offices"),
            "description_html": job.get("content"),
            "description_text": description_text(job.get("content")),
            "retrieved_at": retrieved_at,
            "source_type": "greenhouse_current_public_api",
            "source_url": BOARD_API_URL + "?content=true",
        }
    )
    return record


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


class R2Store:
    """Small S3-compatible client for immutable R2 writes and byte read-back."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
        parsed = urlparse(endpoint)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError("R2_ENDPOINT must be an absolute URL.")
        self.endpoint = endpoint.rstrip("/")
        self.host = parsed.netloc
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.client = httpx.Client(timeout=90, follow_redirects=False)

    def request(self, method: str, key: str, body: bytes = b"", content_type: str | None = None) -> httpx.Response:
        now = utc_now()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date = now.strftime("%Y%m%d")
        payload_hash = sha256(body)
        canonical_uri = f"/{quote(self.bucket, safe='')}/{quote(key, safe='/')}"
        headers = {
            "host": self.host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if method == "PUT":
            headers["if-none-match"] = "*"
            headers["content-type"] = content_type or "application/octet-stream"
        signed_names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name].strip()}\n" for name in sorted(headers))
        canonical_request = "\n".join((method, canonical_uri, "", canonical_headers, signed_names, payload_hash))
        scope = f"{date}/auto/s3/aws4_request"
        string_to_sign = "\n".join((
            "AWS4-HMAC-SHA256", amz_date, scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ))
        key_date = hmac.new(("AWS4" + self.secret_key).encode(), date.encode(), hashlib.sha256).digest()
        key_region = hmac.new(key_date, b"auto", hashlib.sha256).digest()
        key_service = hmac.new(key_region, b"s3", hashlib.sha256).digest()
        signing_key = hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        authorization = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed_names}, Signature={signature}"
        )
        outgoing = {name: value for name, value in headers.items() if name != "host"}
        outgoing["Authorization"] = authorization
        response = self.client.request(method, self.endpoint + canonical_uri, headers=outgoing, content=body)
        response.raise_for_status()
        return response

    def put_immutable(self, key: str, body: bytes, content_type: str) -> None:
        for attempt in range(3):
            try:
                self.request("PUT", key, body=body, content_type=content_type)
                return
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 412:
                    # A prior attempt may have completed but lost its response.
                    if sha256(self.get(key)) == sha256(body):
                        return
                raise
            except httpx.TransportError:
                # The next attempt uses If-None-Match and confirms an already
                # committed object by its content hash if R2 returns 412.
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def get(self, key: str) -> bytes:
        for attempt in range(3):
            try:
                return self.request("GET", key).content
            except httpx.TransportError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("R2 GET retry loop exited unexpectedly.")

    def close(self) -> None:
        self.client.close()


def verify_readback(s3: R2Store, key: str, expected: bytes) -> dict[str, Any]:
    actual = s3.get(key)
    actual_hash = sha256(actual)
    expected_hash = sha256(expected)
    if actual_hash != expected_hash:
        raise RuntimeError(f"R2 read-back SHA-256 mismatch for {key}.")
    return {"key": key, "bytes": len(actual), "sha256": actual_hash, "matches_local": True}


def main() -> None:
    load_env_file(ENV_FILE)
    bucket = required_env("R2_BUCKET")
    prefix = os.getenv("R2_PREFIX", "anthropic-bias-data").strip("/")
    endpoint = required_env("R2_ENDPOINT")
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    snapshot_prefix = f"{prefix}/greenhouse/current-snapshots/{stamp}"

    raw_board, retrieved_at = fetch_board()
    jobs = raw_board["jobs"]
    job_ids = [job.get("id") for job in jobs]
    duplicate_ids = sorted({job_id for job_id in job_ids if job_ids.count(job_id) > 1})
    records = [normalize_job(job, retrieved_at) for job in jobs]
    raw_snapshot = {
        "source": "Greenhouse public Job Board API",
        "source_url": BOARD_API_URL + "?content=true",
        "board_url": BOARD_URL,
        "board_token": BOARD_TOKEN,
        "retrieved_at": retrieved_at,
        "pagination": {
            "mode": "single complete board response",
            "jobs_returned": len(jobs),
            "api_meta_total": raw_board.get("meta", {}).get("total"),
            "total_matches_response_count": raw_board.get("meta", {}).get("total", len(jobs)) == len(jobs),
            "has_more": False,
            "note": "Greenhouse documents this endpoint as returning all job posts; the response meta.total was checked against the jobs array length.",
        },
        "response": raw_board,
    }
    normalized_snapshot = {
        "source": "Greenhouse public Job Board API",
        "source_url": BOARD_API_URL + "?content=true",
        "retrieved_at": retrieved_at,
        "record_count": len(records),
        "records": records,
    }
    raw_bytes = serialize_json(raw_snapshot)
    records_bytes = serialize_json(normalized_snapshot)
    raw_name = "greenhouse_anthropic_current_raw.json"
    records_name = "greenhouse_anthropic_current_records.json"

    missing_html = [str(job.get("id")) for job in jobs if not isinstance(job.get("content"), str) or not job["content"].strip()]
    audit: dict[str, Any] = {
        "audit_type": "current_greenhouse_snapshot_verification",
        "board_token": BOARD_TOKEN,
        "board_url": BOARD_URL,
        "api_url": BOARD_API_URL + "?content=true",
        "retrieved_at": retrieved_at,
        "job_count": len(jobs),
        "unique_job_id_count": len(set(job_ids)),
        "duplicate_job_ids": duplicate_ids,
        "duplicate_job_id_count": len(duplicate_ids),
        "descriptions_present_count": len(jobs) - len(missing_html),
        "descriptions_missing_job_ids": missing_html,
        "exact_html_preserved": all(
            records[i].get("description_html") == jobs[i].get("content") for i in range(len(jobs))
        ),
        "titles_present_count": sum(bool(job.get("title")) for job in jobs),
        "urls_present_count": sum(bool(job.get("absolute_url")) for job in jobs),
        "locations_present_count": sum(bool(job.get("location")) for job in jobs),
        "updated_at_present_count": sum(job.get("updated_at") is not None for job in jobs),
        "pagination_verification": raw_snapshot["pagination"],
        "raw_snapshot": {"key": f"{snapshot_prefix}/{raw_name}", "bytes": len(raw_bytes), "sha256": sha256(raw_bytes)},
        "normalized_snapshot": {"key": f"{snapshot_prefix}/{records_name}", "bytes": len(records_bytes), "sha256": sha256(records_bytes)},
        "immutable_keying": "Unique UTC timestamped snapshot prefix with conditional If-None-Match create.",
        "r2_readback": {},
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_local = OUTPUT_DIR / f"{stamp}_{raw_name}"
    records_local = OUTPUT_DIR / f"{stamp}_{records_name}"
    audit_local = OUTPUT_DIR / f"{stamp}_greenhouse_anthropic_current_audit.json"
    raw_local.write_bytes(raw_bytes)
    records_local.write_bytes(records_bytes)

    s3 = R2Store(
        endpoint=endpoint,
        access_key=required_env("R2_ACCESS_KEY_ID"),
        secret_key=required_env("R2_SECRET_ACCESS_KEY"),
        bucket=bucket,
    )
    raw_key = f"{snapshot_prefix}/{raw_name}"
    records_key = f"{snapshot_prefix}/{records_name}"
    s3.put_immutable(raw_key, raw_bytes, "application/json")
    s3.put_immutable(records_key, records_bytes, "application/json")
    audit["r2_readback"]["raw_snapshot"] = verify_readback(s3, raw_key, raw_bytes)
    audit["r2_readback"]["normalized_snapshot"] = verify_readback(s3, records_key, records_bytes)
    audit["verified"] = (
        not duplicate_ids
        and not missing_html
        and audit["exact_html_preserved"]
        and audit["titles_present_count"] == len(jobs)
        and audit["urls_present_count"] == len(jobs)
        and audit["locations_present_count"] == len(jobs)
        and all(item["matches_local"] for item in audit["r2_readback"].values())
    )

    audit_bytes = serialize_json(audit)
    audit_local.write_bytes(audit_bytes)
    audit_key = f"{snapshot_prefix}/greenhouse_anthropic_current_audit.json"
    s3.put_immutable(audit_key, audit_bytes, "application/json")
    audit_file_readback = verify_readback(s3, audit_key, audit_bytes)
    s3.close()

    print(json.dumps({
        "verified": audit["verified"],
        "job_count": audit["job_count"],
        "duplicate_job_id_count": audit["duplicate_job_id_count"],
        "descriptions_present_count": audit["descriptions_present_count"],
        "titles_present_count": audit["titles_present_count"],
        "urls_present_count": audit["urls_present_count"],
        "locations_present_count": audit["locations_present_count"],
        "updated_at_present_count": audit["updated_at_present_count"],
        "snapshot_prefix": snapshot_prefix,
        "raw_local": str(raw_local),
        "normalized_local": str(records_local),
        "audit_local": str(audit_local),
        "r2_readback": audit["r2_readback"],
        "audit_file_readback": audit_file_readback,
    }, indent=2))
    if not audit["verified"]:
        raise SystemExit("Snapshot captured, but verification found missing fields or duplicate IDs; see the audit.")


if __name__ == "__main__":
    main()
