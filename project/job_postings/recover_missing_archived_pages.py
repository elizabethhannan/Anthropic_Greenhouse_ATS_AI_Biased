"""Retry missing Internet Archive page copies for historical Greenhouse jobs.

Only ID-backed records with archived Greenhouse evidence and no archived page
HTML are attempted. This writes a new run and never edits the recovery corpus.
Archive capture timestamps remain archive evidence and are never posting dates.
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import hmac
import html
import json
import os
import re
import time
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

PROJECT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT / "r2.env"
OUTPUT_DIR = Path(__file__).resolve().parent / "missing_archive_outputs"
SOURCE_RUN = "20260929T074631Z"
SOURCE_RAW_KEY = f"raw/job-postings/historical-greenhouse/{SOURCE_RUN}/historical_greenhouse_raw.json"
SOURCE_FILTERED_KEY = f"filtered/job-postings/{SOURCE_RUN}/historical_greenhouse_deduplicated.json"
WAYBACK_RE = re.compile(r"https?://web\.archive\.org/web/(\d{14})(?:id_)?/(https?://[^\s\"'<>]+)", re.I)
JOB_ID_RE = re.compile(r"/jobs/(\d+)(?:[/?#]|$)", re.I)
HTML_CONTAINER_RE = re.compile(
    r"<(?P<tag>div|section|article)\b(?=[^>]*(?:class|id)=[\"'][^\"']*"
    r"(?:job__description|job-description|job-posting__description|job-posting-description)"
    r"[^\"']*[\"'])[^>]*>", re.I
)
USER_AGENT = "AnthropicBiasData-missing-archive-page-recovery/1.0"


def load_env() -> None:
    if not ENV_FILE.exists():
        raise FileNotFoundError(f"R2 settings file not found: {ENV_FILE}")
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


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def get_id(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value)
        if re.fullmatch(r"\d{5,}", text):
            return text
        match = re.search(r"/jobs/(\d{5,})", urlparse(text).path, re.I)
        if match:
            return match.group(1)
    return None


def canonical_original(value: str | None, job_id: str) -> str:
    if value:
        parsed = urlparse(value)
        if parsed.netloc.lower().endswith("greenhouse.io") and JOB_ID_RE.search(parsed.path):
            host = "job-boards.greenhouse.io" if parsed.netloc.lower().startswith("job-boards.") else "boards.greenhouse.io"
            return f"https://{host}/anthropic/jobs/{job_id}" + (f"?{parsed.query}" if parsed.query else "")
    return f"https://job-boards.greenhouse.io/anthropic/jobs/{job_id}"


def extract_capture(record: dict[str, Any]) -> dict[str, Any] | None:
    raw = record.get("source_raw_record")
    raw = raw if isinstance(raw, dict) else {}
    timestamp = str(record.get("archive_capture_timestamp") or raw.get("timestamp") or "")
    original = raw.get("original") or record.get("absolute_url")
    if (not timestamp or not re.fullmatch(r"\d{14}", timestamp)) and record.get("source_url"):
        match = WAYBACK_RE.search(str(record["source_url"]))
        if match:
            timestamp = timestamp or match.group(1)
            original = original or match.group(2)
    job_id = get_id(record.get("greenhouse_job_id"), original, record.get("absolute_url"))
    if not job_id or not re.fullmatch(r"\d{14}", timestamp):
        return None
    return {
        "timestamp": timestamp,
        "original": canonical_original(str(original) if original else None, job_id),
        "statuscode": str(raw.get("statuscode") or record.get("archive_statuscode") or ""),
        "mimetype": str(raw.get("mimetype") or record.get("archive_mimetype") or ""),
        "digest": raw.get("digest") or record.get("archive_digest"),
        "record_source_url": record.get("source_url"),
    }


def capture_rank(item: dict[str, Any], preferred_ts: str | None) -> tuple[Any, ...]:
    parsed = urlparse(item["original"])
    job_id = get_id(item["original"])
    direct = parsed.path == f"/anthropic/jobs/{job_id}" and not parsed.query
    valid = item.get("statuscode") in ("", "200") and item.get("mimetype", "").lower() in ("", "text/html")
    preferred = item["timestamp"] == preferred_ts
    # Prefer the known source capture, then clean direct HTML captures, newest first.
    return (not preferred, not direct, not valid, -int(item["timestamp"]))


class TextExtractor(HTMLParser):
    BLOCK = {"address", "article", "blockquote", "br", "dd", "div", "dl", "dt", "h1", "h2", "h3", "h4", "li", "p", "section", "td", "th", "tr", "ul", "ol"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden += 1
        if not self.hidden and tag.lower() in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        if not self.hidden and tag.lower() in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def clean_text(markup: str | None) -> str | None:
    if not markup:
        return None
    parser = TextExtractor()
    parser.feed(markup)
    parser.close()
    lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line)).strip() or None


def container_html(page: str) -> str | None:
    match = HTML_CONTAINER_RE.search(page)
    if not match:
        return None
    tag, start = match.group("tag").lower(), match.start()
    tokens = re.compile(rf"</?{tag}\b[^>]*>", re.I)
    depth = 0
    for token in tokens.finditer(page, match.start()):
        if token.group().startswith("</"):
            depth -= 1
            if depth == 0:
                return page[start:token.end()]
        elif not token.group().rstrip().endswith("/>"):
            depth += 1
    return None


def title_from_html(page: str) -> str | None:
    for pattern in (r"<h1\b[^>]*>(.*?)</h1\s*>", r"<title\b[^>]*>(.*?)</title\s*>"):
        match = re.search(pattern, page, re.I | re.S)
        if match:
            title = clean_text(match.group(1))
            if title:
                title = re.sub(r"\s*[|–-]\s*(?:Anthropic|Greenhouse).*$", "", title, flags=re.I).strip()
                if title:
                    return title
    return None


def replay_urls(capture: dict[str, Any]) -> list[str]:
    timestamp, original = capture["timestamp"], capture["original"]
    return [f"https://web.archive.org/web/{timestamp}id_/{original}",
            f"https://web.archive.org/web/{timestamp}/{original}"]


def fetch_capture(client: httpx.Client, capture: dict[str, Any]) -> dict[str, Any]:
    outcomes = []
    for url in replay_urls(capture):
        try:
            response = client.get(url, timeout=24)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            page = response.content.decode(response.encoding or "utf-8", errors="replace")
            if "html" not in content_type and "<html" not in page[:1500].lower() and "<!doctype html" not in page[:1500].lower():
                outcomes.append({"result": "not_html", "http_status": response.status_code,
                                 "url": str(response.url), "content_type": content_type})
                continue
            title = title_from_html(page)
            description_html = container_html(page)
            description_text = clean_text(description_html)
            outcomes.append({"result": "html", "http_status": response.status_code,
                             "url": str(response.url), "content_type": content_type,
                             "title": title, "description_html": description_html,
                             "description_text": description_text, "source_page_html": page})
            # If this replay form returned HTML, it is the observation for this capture.
            break
        except httpx.TimeoutException as exc:
            outcomes.append({"result": "wayback_timeout", "url": url, "error_type": type(exc).__name__})
        except httpx.HTTPStatusError as exc:
            outcomes.append({"result": "http_failure", "url": url,
                             "http_status": exc.response.status_code, "error_type": type(exc).__name__})
        except httpx.HTTPError as exc:
            outcomes.append({"result": "wayback_timeout" if isinstance(exc, httpx.TimeoutException) else "network_failure",
                             "url": url, "error_type": type(exc).__name__})
    return {"capture": capture, "attempts": outcomes}


def load_env_file() -> None:
    load_env()


class R2Store:
    def __init__(self) -> None:
        endpoint = os.environ["R2_ENDPOINT"].rstrip("/")
        parsed = urlparse(endpoint)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("R2_ENDPOINT must be an absolute URL")
        self.endpoint, self.host = endpoint, parsed.netloc
        self.access = os.environ["R2_ACCESS_KEY_ID"]
        self.secret = os.environ["R2_SECRET_ACCESS_KEY"]
        self.bucket = os.environ["R2_BUCKET"]
        self.client = httpx.Client(timeout=240, follow_redirects=False)

    def request(self, method: str, key: str, body: bytes = b"") -> httpx.Response:
        now = utcnow()
        stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
        digest = sha(body)
        uri = f"/{quote(self.bucket, safe='')}/{quote(key, safe='/')}"
        headers = {"host": self.host, "x-amz-content-sha256": digest, "x-amz-date": stamp}
        if method == "PUT":
            headers.update({"if-none-match": "*", "content-type": "application/json; charset=utf-8"})
        names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name].strip()}\n" for name in sorted(headers))
        canonical = "\n".join((method, uri, "", canonical_headers, names, digest))
        scope = f"{day}/auto/s3/aws4_request"
        to_sign = "\n".join(("AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()))
        kd = hmac.new(("AWS4" + self.secret).encode(), day.encode(), hashlib.sha256).digest()
        kr = hmac.new(kd, b"auto", hashlib.sha256).digest()
        ks = hmac.new(kr, b"s3", hashlib.sha256).digest()
        signing_key = hmac.new(ks, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).hexdigest()
        headers["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={self.access}/{scope}, "
                                    f"SignedHeaders={names}, Signature={signature}")
        response = self.client.request(method, self.endpoint + uri,
            headers={k: v for k, v in headers.items() if k != "host"}, content=body)
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
                self.client = httpx.Client(timeout=240, follow_redirects=False)
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
                self.client = httpx.Client(timeout=240, follow_redirects=False)
                time.sleep(2 ** attempt)


def archive_evidence(record: dict[str, Any]) -> bool:
    if record.get("archive_capture_timestamp") or record.get("archive_capture_date"):
        return True
    types = set(record.get("source_types") or [])
    types.add(record.get("source_type"))
    if any(str(value or "").startswith("internet_archive") for value in types):
        return True
    return any(str(item.get("source_type") or "").startswith("internet_archive")
               for item in record.get("evidence", []) if isinstance(item, dict))


def main() -> None:
    load_env_file()
    retrieved_at = iso_now()
    run_stamp = utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    store = R2Store()
    try:
        raw_bytes = store.get(SOURCE_RAW_KEY)
        filtered_bytes = store.get(SOURCE_FILTERED_KEY)
        raw_records = json.loads(raw_bytes).get("records", [])
        filtered_records = json.loads(filtered_bytes).get("records", [])
        if len(raw_records) != 2580 or len(filtered_records) != 1246:
            raise RuntimeError(f"Unexpected source counts: raw={len(raw_records)}, filtered={len(filtered_records)}")

        filtered_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        all_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        captures_by_id: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
        recovered_archive_ids: set[str] = set()
        for rec in filtered_records:
            job_id = get_id(rec.get("greenhouse_job_id"), rec.get("absolute_url"), rec.get("source_url"))
            if job_id:
                filtered_by_id[job_id].append(rec)
                all_by_id[job_id].append(rec)
        for rec in raw_records:
            if not isinstance(rec, dict):
                continue
            job_id = get_id(rec.get("greenhouse_job_id"), rec.get("absolute_url"), rec.get("source_url"))
            if not job_id:
                continue
            all_by_id[job_id].append(rec)
            capture = extract_capture(rec)
            if capture:
                key = (capture["timestamp"], capture["original"], str(capture.get("digest") or ""))
                captures_by_id[job_id][key] = capture
            if (rec.get("source_type") == "internet_archive" and
                    (rec.get("source_page_html") or rec.get("description_html"))):
                recovered_archive_ids.add(job_id)

        targets: list[dict[str, Any]] = []
        no_valid_capture_count = 0
        for job_id, rows in filtered_by_id.items():
            archive_rows = [row for row in rows if archive_evidence(row)]
            if not archive_rows or job_id in recovered_archive_ids:
                continue
            captures = list(captures_by_id.get(job_id, {}).values())
            for row in archive_rows:
                capture = extract_capture(row)
                if capture:
                    captures_by_id[job_id][(capture["timestamp"], capture["original"], str(capture.get("digest") or ""))] = capture
            captures = list(captures_by_id.get(job_id, {}).values())
            captures = [item for item in captures
                        if item.get("statuscode") in ("", "200")
                        and item.get("mimetype", "").lower() in ("", "text/html")]
            preferred_ts = next((str(row.get("archive_capture_timestamp")) for row in archive_rows
                                 if row.get("archive_capture_timestamp")), None)
            captures.sort(key=lambda item: capture_rank(item, preferred_ts))
            if not captures:
                # Archive evidence must supply at least one retrievable capture.
                no_valid_capture_count += 1
                continue
            representative = dict(archive_rows[0])
            original_date_evidence = {
                "first_published_at": representative.get("first_published_at"),
                "posting_date_if_known": representative.get("posting_date_if_known"),
                "updated_at": representative.get("updated_at"),
                "date_confidence": representative.get("date_confidence"),
                "historical_status": representative.get("historical_status"),
                "evidence": representative.get("evidence", []),
            }
            targets.append({
                "greenhouse_job_id": job_id,
                "input_record_count_for_job_id": len(rows),
                "source_record": representative,
                "original_date_evidence": original_date_evidence,
                "captures": captures,
                "multiple_capture_count": len(captures),
            })
        duplicate_ids = {job_id: len(rows) for job_id, rows in filtered_by_id.items() if len(rows) > 1}

        http = httpx.Client(headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
                            follow_redirects=True, timeout=24)

        def process(target: dict[str, Any]) -> dict[str, Any]:
            id_results = []
            selected = None
            for index, capture in enumerate(target["captures"]):
                result = fetch_capture(http, capture)
                for form in result["attempts"]:
                    form["capture_timestamp"] = capture["timestamp"]
                    form["capture_date"] = f"{capture['timestamp'][:4]}-{capture['timestamp'][4:6]}-{capture['timestamp'][6:8]}"
                id_results.append(result)
                html_results = [item for item in result["attempts"] if item.get("result") == "html"]
                if html_results:
                    observation = html_results[0]
                    # Keep the best successful capture; prefer a full description.
                    if selected is None or (observation.get("description_html") and not selected.get("description_html")):
                        selected = {**observation, "capture": capture}
                    if observation.get("description_html"):
                        break
                if index + 1 < len(target["captures"]):
                    continue
            outcomes = [attempt for result in id_results for attempt in result["attempts"]]
            is_full = bool(selected and selected.get("description_html") and selected.get("description_text"))
            has_title = bool(selected and selected.get("title"))
            if is_full:
                status = "full_description_recovered"
            elif has_title:
                status = "title_only"
            else:
                status = "still_missing"
            chosen_capture = selected.get("capture") if selected else target["captures"][0]
            chosen_page = selected or {}
            capture_date = (f"{chosen_capture['timestamp'][:4]}-{chosen_capture['timestamp'][4:6]}-{chosen_capture['timestamp'][6:8]}"
                            if chosen_capture.get("timestamp") else None)
            original = target["source_record"]
            compact_attempts = []
            for result in id_results:
                capture_result = {"capture": result["capture"], "attempts": []}
                for outcome in result["attempts"]:
                    compact = {key: value for key, value in outcome.items()
                               if key not in {"source_page_html", "description_html", "description_text"}}
                    page = outcome.get("source_page_html")
                    if page:
                        page_bytes = page.encode("utf-8")
                        compact["source_page_html_sha256"] = sha(page_bytes)
                        compact["source_page_html_bytes"] = len(page_bytes)
                        compact["description_html_recovered"] = bool(outcome.get("description_html"))
                    capture_result["attempts"].append(compact)
                compact_attempts.append(capture_result)
            compact_source = {key: original.get(key) for key in (
                "greenhouse_job_id", "exact_title", "absolute_url", "location", "requisition_id",
                "departments", "offices", "first_published_at", "posting_date_if_known", "updated_at",
                "date_confidence", "historical_status", "archive_capture_date", "archive_capture_timestamp",
                "archive_digest", "archive_mimetype", "source_url", "source_type", "source_types",
                "source_urls", "evidence")}
            recovered_record = {
                "greenhouse_job_id": target["greenhouse_job_id"],
                "exact_title": chosen_page.get("title") or original.get("exact_title"),
                "absolute_url": original.get("absolute_url") or chosen_capture.get("original"),
                "location": original.get("location"),
                "requisition_id": original.get("requisition_id"),
                "departments": original.get("departments"),
                "offices": original.get("offices"),
                "description_html": chosen_page.get("description_html"),
                "description_text": chosen_page.get("description_text"),
                "source_page_html": chosen_page.get("source_page_html"),
                "created_at": original.get("created_at"),
                "first_published_at": target["original_date_evidence"]["first_published_at"],
                "updated_at": target["original_date_evidence"]["updated_at"],
                "active_live_status": original.get("active_live_status"),
                "source_url": chosen_page.get("url") or replay_urls(chosen_capture)[0],
                "source_type": "internet_archive_replay",
                "archive_capture_date": capture_date,
                "archive_capture_timestamp": chosen_capture.get("timestamp"),
                "archive_digest": chosen_capture.get("digest"),
                "date_confidence": target["original_date_evidence"]["date_confidence"],
                "historical_status": target["original_date_evidence"]["historical_status"],
                "posting_date_if_known": target["original_date_evidence"]["posting_date_if_known"],
                "retrieved_at": retrieved_at,
                "original_date_evidence": target["original_date_evidence"],
                "recovery_status": status,
                "capture_attempt_count": len(id_results),
                "capture_count_available": target["multiple_capture_count"],
                "capture_attempts": compact_attempts,
            }
            return {
                "greenhouse_job_id": target["greenhouse_job_id"],
                "source_record": compact_source,
                "original_date_evidence": target["original_date_evidence"],
                "candidate_captures": target["captures"],
                "recovered_record": recovered_record,
                "recovery_status": status,
                "http_failure": any(item["result"] in {"http_failure", "not_html"} for item in outcomes),
                "wayback_timeout": any(item["result"] == "wayback_timeout" for item in outcomes),
                "network_failure": any(item["result"] == "network_failure" for item in outcomes),
                "multiple_captures": target["multiple_capture_count"] > 1,
                "alternate_capture_attempted": len(id_results) > 1,
            }

        results: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            futures = {pool.submit(process, target): target["greenhouse_job_id"] for target in targets}
            for number, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                results.append(future.result())
                if number % 50 == 0 or number == len(futures):
                    print(f"Archived job IDs processed: {number}/{len(futures)}", flush=True)
        http.close()
        results.sort(key=lambda item: item["greenhouse_job_id"])

        stats = {
            "attempted": len(results),
            "recovered": sum(item["recovery_status"] != "still_missing" for item in results),
            "full_description_recovered": sum(item["recovery_status"] == "full_description_recovered" for item in results),
            "title_only": sum(item["recovery_status"] == "title_only" for item in results),
            "still_missing": sum(item["recovery_status"] == "still_missing" for item in results),
            "http_failure_job_ids": sum(item["http_failure"] for item in results),
            "wayback_timeout_job_ids": sum(item["wayback_timeout"] for item in results),
            "network_failure_job_ids": sum(item["network_failure"] for item in results),
            "multiple_captures_available_job_ids": sum(item["multiple_captures"] for item in results),
            "alternate_capture_attempted_job_ids": sum(item["alternate_capture_attempted"] for item in results),
            "duplicate_job_ids_in_filtered_input": len(duplicate_ids),
            "duplicate_filtered_rows_for_job_ids": sum(count - 1 for count in duplicate_ids.values()),
            "target_job_ids_without_any_valid_capture": no_valid_capture_count,
        }
        audit = {
            "audit_type": "missing_archived_greenhouse_page_recovery",
            "run_timestamp_utc": retrieved_at,
            "source_raw_r2_key": SOURCE_RAW_KEY,
            "source_filtered_r2_key": SOURCE_FILTERED_KEY,
            "source_raw_sha256": sha(raw_bytes),
            "source_filtered_sha256": sha(filtered_bytes),
            "source_raw_rows": len(raw_records),
            "source_filtered_rows": len(filtered_records),
            "selection_rule": "ID-backed historical records with Internet Archive capture evidence and no existing Internet Archive page HTML for that Greenhouse job ID.",
            "attempt_order": ["best known clean/direct capture", "alternate valid capture(s) when needed"],
            "page_content_rule": "A description is counted as recovered only when a Greenhouse job-description HTML container and nonempty extracted text are present; a page title alone is title_only.",
            "capture_date_rule": "archive_capture_date is copied only from the selected Wayback timestamp. It is never substituted for first_published_at or posting_date_if_known.",
            "counts": stats,
            "r2_readback": {},
        }
        raw_output = {"run_timestamp_utc": retrieved_at, "candidate_record_count": len(results), "records": results}
        recovered_records = [item["recovered_record"] for item in results if item["recovery_status"] != "still_missing"]
        filtered_output = {"run_timestamp_utc": retrieved_at, "record_count": len(recovered_records), "records": recovered_records}

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        raw_key = f"raw/job-postings/missing-archive-pages/{run_stamp}/missing_archived_pages_recovery.json"
        filtered_key = f"filtered/job-postings/missing-archive-pages/{run_stamp}/missing_archived_pages_recovered.json"
        audit_key = f"audit/job-postings/missing-archive-pages/{run_stamp}/missing_archived_pages_audit.json"
        raw_body, filtered_body = json_bytes(raw_output), json_bytes(filtered_output)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / f"{run_stamp}_missing_archived_pages_recovery.json").write_bytes(raw_body)
        (OUTPUT_DIR / f"{run_stamp}_missing_archived_pages_recovered.json").write_bytes(filtered_body)
        print(json.dumps({"uploading": True, "raw_bytes": len(raw_body),
                          "recovered_bytes": len(filtered_body), "candidate_ids": len(results),
                          "recovered_ids": len(recovered_records)}, indent=2), flush=True)
        store.put_immutable(raw_key, raw_body)
        store.put_immutable(filtered_key, filtered_body)
        raw_back, filtered_back = store.get(raw_key), store.get(filtered_key)
        if sha(raw_back) != sha(raw_body) or len(json.loads(raw_back).get("records", [])) != len(results):
            raise RuntimeError("R2 recovery raw output read-back verification failed.")
        if sha(filtered_back) != sha(filtered_body) or len(json.loads(filtered_back).get("records", [])) != len(recovered_records):
            raise RuntimeError("R2 recovered output read-back verification failed.")
        audit["r2_readback"] = {
            "raw": {"key": raw_key, "sha256": sha(raw_back), "bytes": len(raw_back), "row_count": len(results), "verified": True},
            "filtered": {"key": filtered_key, "sha256": sha(filtered_back), "bytes": len(filtered_back), "row_count": len(recovered_records), "verified": True},
        }
        audit_body = json_bytes(audit)
        store.put_immutable(audit_key, audit_body)
        if sha(store.get(audit_key)) != sha(audit_body):
            raise RuntimeError("R2 recovery audit read-back verification failed.")
        (OUTPUT_DIR / f"{run_stamp}_missing_archived_pages_audit.json").write_bytes(audit_body)
        print(json.dumps({"run_timestamp_utc": retrieved_at, "audit": stats,
                          "r2_raw_key": raw_key, "r2_filtered_key": filtered_key,
                          "r2_audit_key": audit_key, "r2_readback_verified": True}, indent=2))
    finally:
        store.client.close()


if __name__ == "__main__":
    main()
