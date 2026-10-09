"""Recover and audit public evidence of Anthropic Greenhouse postings.

Scope: postings shown to have been published or publicly available from
2026-04-01 through 2026-09-30. A current listing is not treated as historical
unless Greenhouse's first_published value or a dated archive proves it.

The script preserves source-level observations before deduplicating records.
It searches the public Greenhouse board/API, Bing's public RSS search results,
the Internet Archive CDX index, and Anthropic's careers page/archive. It does
not infer posting dates from updated_at or archive capture dates.
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
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

import httpx


BOARD_TOKEN = "anthropic"
BOARD_API = f"https://boards-api.greenhouse.io/v1/boards/{BOARD_TOKEN}/jobs"
BOARD_PAGE = f"https://job-boards.greenhouse.io/{BOARD_TOKEN}"
CAREERS_PAGE = "https://www.anthropic.com/careers"
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
BING_RSS = "https://www.bing.com/search"
START_DATE = dt.date(2026, 4, 1)
END_DATE = dt.date(2026, 9, 30)
START_CDX = "20260401"
END_CDX = "20260930"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / "r2.env"
OUTPUT_DIR = Path(__file__).resolve().parent / "historical_outputs"
USER_AGENT = "AnthropicBiasData-historical-greenhouse-recovery/1.0"
SEARCH_QUERIES = [
    'site:job-boards.greenhouse.io/anthropic/jobs/ Anthropic after:2026-03-31 before:2026-10-01',
    'site:job-boards.greenhouse.io/anthropic/jobs/ "Anthropic Fellows Program" after:2026-03-31 before:2026-10-01',
    'site:job-boards.greenhouse.io/anthropic/jobs/ "Research Scientist" after:2026-03-31 before:2026-10-01',
    'site:job-boards.greenhouse.io/anthropic/jobs/ "Research Engineer" after:2026-03-31 before:2026-10-01',
    'site:job-boards.greenhouse.io/anthropic/jobs/ "AI Safety" OR Alignment OR Interpretability after:2026-03-31 before:2026-10-01',
    'site:job-boards.greenhouse.io/anthropic/jobs/ "Reinforcement Learning" OR Pre-training OR Post-training after:2026-03-31 before:2026-10-01',
    'site:job-boards.greenhouse.io/anthropic/jobs/ "Model Behavior" OR Evaluations OR "Machine Learning Research" after:2026-03-31 before:2026-10-01',
]
RESEARCH_TERMS = re.compile(
    r"research scientist|research engineer|machine learning research|research fellow|"
    r"research internship|research residency|research role|conduct research|conducting research|"
    r"ai safety|alignment|interpretability|reinforcement learning|pre[- ]training|"
    r"post[- ]training|model behavior|model evaluations|evaluation research|"
    r"mechanistic|model internals|frontier models",
    re.I,
)
FELLOWSHIP_TERMS = re.compile(r"fellow", re.I)
JOB_ID_RE = re.compile(r"/jobs/(\d+)(?:[/?#]|$)")
GREENHOUSE_URL_RE = re.compile(
    r"https?://(?:job-boards|boards)\.greenhouse\.io/anthropic/jobs/\d+(?:[^\s\"'<>)]*)?",
    re.I,
)


class TextExtractor(HTMLParser):
    BLOCK = {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl",
        "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
        "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol",
        "p", "pre", "section", "table", "td", "th", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(markup: str | None) -> str | None:
    if markup is None:
        return None
    decoded = markup
    for _ in range(3):
        next_value = html.unescape(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    parser = TextExtractor()
    parser.feed(decoded)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    lines = [re.sub(r"[\t\r\f\v ]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line)).strip()


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"R2 environment file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key and value:
            os.environ.setdefault(key, value)


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required setting {name} is missing from the environment and r2.env.")
    return value


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def get(client: httpx.Client, url: str, *, params: dict[str, Any] | None = None,
        attempts: int = 3, timeout: float = 45) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = client.get(url, params=params, timeout=timeout)
            if response.status_code in (429, 500, 502, 503, 504):
                response.raise_for_status()
            return response
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt + 1 == attempts:
                break
            time.sleep(min(2 ** attempt, 8))
    assert last_error is not None
    raise last_error


def parse_date(value: Any) -> dt.date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return dt.date.fromisoformat(value[:10])
        except ValueError:
            return None


def in_scope(date_value: dt.date | None) -> bool:
    return date_value is not None and START_DATE <= date_value <= END_DATE


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip().rstrip(".,;"))
    if parsed.netloc.lower().endswith("greenhouse.io") and parsed.path.startswith("/anthropic/jobs/"):
        return urlunparse(("https", "job-boards.greenhouse.io", parsed.path, "", "", ""))
    return urlunparse((parsed.scheme or "https", parsed.netloc, parsed.path, "", "", ""))


def get_job_id(url: str | None, record: dict[str, Any] | None = None) -> str | None:
    if record:
        value = record.get("greenhouse_job_id", record.get("id", record.get("job_id")))
        if value is not None:
            return str(value)
    if url:
        match = JOB_ID_RE.search(urlparse(url).path)
        if match:
            return match.group(1)
    return None


def normalize_record(raw: dict[str, Any], *, source_type: str, source_url: str,
                     retrieved_at: str, archive_capture_date: str | None = None,
                     index_result_date: str | None = None, page_html: str | None = None,
                     search_title: str | None = None, search_snippet: str | None = None,
                     live_status: str | None = None) -> dict[str, Any]:
    job_url = raw.get("absolute_url") or raw.get("url") or source_url
    job_id = get_job_id(job_url, raw)
    description_html = raw.get("description_html", raw.get("content"))
    if description_html is None and page_html:
        # Keep the full captured page in source_page_html. Where a specific
        # Greenhouse description wrapper is identifiable, retain that fragment.
        match = re.search(
            r"<div[^>]*class=[\"'][^\"']*(?:job__description|job-posting)[^\"']*[\"'][^>]*>(.*?)</div>\s*</div>",
            page_html,
            re.I | re.S,
        )
        description_html = match.group(0) if match else None
    location = raw.get("location")
    if isinstance(location, dict):
        location = location.get("name")
    return {
        "greenhouse_job_id": job_id,
        "exact_title": raw.get("exact_title") or raw.get("title") or search_title,
        "absolute_url": canonical_url(job_url),
        "location": location,
        "requisition_id": raw.get("requisition_id"),
        "departments": raw.get("departments", raw.get("department")),
        "offices": raw.get("offices", raw.get("office")),
        "description_html": description_html,
        "description_text": raw.get("description_text") or clean_text(description_html) or search_snippet,
        "created_at": raw.get("created_at"),
        "first_published_at": raw.get("first_published_at") or raw.get("first_published"),
        "updated_at": raw.get("updated_at"),
        "active_live_status": live_status or raw.get("active_live_status") or raw.get("live_status"),
        "source_url": source_url,
        "source_type": source_type,
        "archive_capture_date": archive_capture_date,
        "index_result_date": index_result_date,
        "date_confidence": None,
        "retrieved_at": retrieved_at,
        "historical_status": None,
        "source_page_html": page_html,
        "search_snippet": search_snippet,
        "source_raw_record": raw,
    }


def evidence_status(record: dict[str, Any]) -> tuple[str, str, str | None]:
    published = parse_date(record.get("first_published_at"))
    archive_date = parse_date(record.get("archive_capture_date"))
    if in_scope(published):
        return "historical_verified", "greenhouse_first_published", published.isoformat()
    if in_scope(archive_date):
        if record.get("source_type") in {"internet_archive", "internet_archive_cdx"}:
            confidence = "archive_capture_date_only" if published is None else "archive_capture_plus_greenhouse_date_outside_window"
            return "archive_only", confidence, published.isoformat() if published else None
        confidence = "archive_capture_date_only" if published is None else "archive_capture_plus_greenhouse_date_outside_window"
        return "historical_verified", confidence, published.isoformat() if published else None
    if record.get("source_type") == "search_index":
        return "indexed_only", "index_date_is_not_posting_date", None
    if record.get("active_live_status") == "live_on_board":
        if published:
            return "current_only", "greenhouse_first_published_outside_window", published.isoformat()
        return "current_only", "currently_live_posting_date_unavailable", None
    if published:
        return "date_unresolved", "greenhouse_first_published_outside_window", published.isoformat()
    return "date_unresolved", "no_supported_posting_date", None


def enrich_status(record: dict[str, Any]) -> dict[str, Any]:
    status, confidence, posting_date = evidence_status(record)
    record["historical_status"] = status
    record["date_confidence"] = confidence
    record["posting_date_if_known"] = posting_date
    return record


def fetch_greenhouse(client: httpx.Client, retrieved_at: str) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    response = get(client, BOARD_API, params={"content": "true"})
    response.raise_for_status()
    board = response.json()
    jobs = board.get("jobs")
    if not isinstance(jobs, list):
        raise RuntimeError("Greenhouse board response did not contain a jobs array.")
    total = board.get("meta", {}).get("total")
    if total is not None and total != len(jobs):
        raise RuntimeError(f"Greenhouse meta.total={total}, but only {len(jobs)} jobs were returned.")
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        future_to_job = {
            pool.submit(get, client, f"{BOARD_API}/{job['id']}", params={"pay_transparency": "true"}): job
            for job in jobs if job.get("id") is not None
        }
        details: dict[str, dict[str, Any]] = {}
        for index, future in enumerate(concurrent.futures.as_completed(future_to_job), start=1):
            job = future_to_job[future]
            try:
                detail_response = future.result()
                if detail_response.status_code == 404:
                    failures.append(f"detail_404:{job.get('id')}")
                    detail = {}
                else:
                    detail_response.raise_for_status()
                    detail = detail_response.json()
                details[str(job.get("id"))] = detail
            except Exception as exc:  # keep the list observation if individual detail fetch fails
                failures.append(f"detail_error:{job.get('id')}:{type(exc).__name__}")
                details[str(job.get("id"))] = {}
            if index % 100 == 0 or index == len(future_to_job):
                print(f"Greenhouse job details processed: {index}/{len(future_to_job)}", flush=True)
    for job in jobs:
        detail = details.get(str(job.get("id")), {})
        merged = dict(job)
        merged.update({key: value for key, value in detail.items() if value is not None})
        merged["first_published_at"] = detail.get("first_published", detail.get("first_published_at"))
        merged["created_at"] = detail.get("created_at")
        record = normalize_record(
            merged,
            source_type="greenhouse_current_api",
            source_url=f"{BOARD_API}/{job.get('id')}?content=true",
            retrieved_at=retrieved_at,
            live_status="live_on_board",
        )
        records.append(enrich_status(record))
    metadata = {
        "board_api_url": BOARD_API + "?content=true",
        "board_page_url": BOARD_PAGE,
        "jobs_returned": len(jobs),
        "api_meta_total": total,
        "total_matches_response_count": total is None or total == len(jobs),
        "individual_job_detail_requests": len(jobs),
        "individual_job_detail_failures": failures,
        "retrieved_at": retrieved_at,
        "raw_board_response": board,
    }
    return records, metadata, failures


def cdx_rows(client: httpx.Client, url: str, *, from_date: str, to_date: str,
             match_type: str = "prefix", collapse: str | None = "urlkey") -> tuple[list[dict[str, str]], str | None]:
    params: dict[str, Any] = {
        "url": url,
        "matchType": match_type,
        "from": from_date,
        "to": to_date,
        "output": "json",
        "filter": "statuscode:200",
        "fl": "timestamp,original,statuscode,digest,mimetype",
        "limit": "5000",
    }
    if collapse:
        params["collapse"] = collapse
    try:
        response = get(client, WAYBACK_CDX, params=params)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, list) or not body:
            return [], None
        headers = body[0]
        rows = [dict(zip(headers, row)) for row in body[1:] if len(row) == len(headers)]
        return rows, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def replay_url(timestamp: str, original: str) -> str:
    return f"https://web.archive.org/web/{timestamp}id_/{original}"


def fetch_archived_pages(client: httpx.Client, rows: list[dict[str, str]], retrieved_at: str,
                         source_type: str) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    def fetch_one(row: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
        original = row.get("original", "")
        timestamp = row.get("timestamp", "")
        if not original or not timestamp:
            return None, "CDX row lacked original URL or timestamp"
        url = replay_url(timestamp, original)
        try:
            response = get(client, url, attempts=2, timeout=20)
            response.raise_for_status()
            page_html = response.text
            return ({"row": row, "page_html": page_html, "replay_url": url}, None)
        except Exception as exc:
            return None, f"{original}@{timestamp}:{type(exc).__name__}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        futures = [pool.submit(fetch_one, row) for row in rows]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            item, error = future.result()
            if index % 50 == 0 or index == len(futures):
                print(f"Internet Archive captures processed: {index}/{len(futures)}", flush=True)
            if error:
                errors.append(error)
                continue
            assert item is not None
            row = item["row"]
            original = row["original"]
            page_html = item["page_html"]
            title_match = re.search(r"<title[^>]*>(.*?)</title>", page_html, re.I | re.S)
            title = html.unescape(re.sub(r"<[^>]+>", " ", title_match.group(1))).strip() if title_match else None
            record = normalize_record(
                {"title": title},
                source_type=source_type,
                source_url=item["replay_url"],
                retrieved_at=retrieved_at,
                archive_capture_date=row.get("timestamp", "")[:8],
                page_html=page_html,
                search_title=title,
                live_status="not_reported_in_archive",
            )
            record["absolute_url"] = canonical_url(original)
            record["greenhouse_job_id"] = get_job_id(original)
            timestamp = row.get("timestamp", "")
            record["archive_capture_date"] = (
                f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
                if len(timestamp) >= 8 else None
            )
            record["archive_capture_timestamp"] = row.get("timestamp")
            record["archive_digest"] = row.get("digest")
            h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, re.I | re.S)
            if h1_match:
                record["exact_title"] = html.unescape(re.sub(r"<[^>]+>", " ", h1_match.group(1))).strip()
            location_match = re.search(
                r"<(?:div|span)[^>]*class=[\"'][^\"']*location[^\"']*[\"'][^>]*>(.*?)</(?:div|span)>",
                page_html, re.I | re.S,
            )
            if location_match:
                record["location"] = clean_text(location_match.group(1))
            records.append(enrich_status(record))
    return records, errors


def choose_one_capture_per_job(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Select one clean archive page URL per job ID for HTML retrieval.

    All CDX rows are retained as raw evidence separately. Tracking-query and
    confirmation-page variants are not fetched repeatedly for the same job.
    Prefer a direct /jobs/{id} URL and then the earliest in-window capture.
    """
    chosen: dict[str, dict[str, str]] = {}
    for row in rows:
        original = row.get("original", "")
        job_id = get_job_id(original)
        if not job_id:
            continue
        path = urlparse(original).path.rstrip("/")
        direct = bool(re.fullmatch(r"/anthropic/jobs/\d+", path))
        candidate = dict(row)
        candidate["_direct_job_page"] = "1" if direct else "0"
        old = chosen.get(job_id)
        if old is None or (
            candidate["_direct_job_page"] == "1" and old.get("_direct_job_page") != "1"
        ) or (
            candidate["_direct_job_page"] == old.get("_direct_job_page")
            and candidate.get("timestamp", "") < old.get("timestamp", "")
        ):
            chosen[job_id] = candidate
    return [{key: value for key, value in row.items() if not key.startswith("_")} for row in chosen.values()]


def archive_index_records(rows: list[dict[str, str]], retrieved_at: str) -> list[dict[str, Any]]:
    """Preserve every CDX URL/capture even if replay HTML cannot be fetched."""
    records: list[dict[str, Any]] = []
    for row in rows:
        original = row.get("original", "")
        timestamp = row.get("timestamp", "")
        date_text = (
            f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
            if len(timestamp) >= 8 else None
        )
        replay = replay_url(timestamp, original) if original and timestamp else WAYBACK_CDX
        record = normalize_record(
            {}, source_type="internet_archive_cdx", source_url=replay,
            retrieved_at=retrieved_at, archive_capture_date=date_text,
            live_status="archived_capture_indexed",
        )
        record["absolute_url"] = canonical_url(original)
        record["greenhouse_job_id"] = get_job_id(original)
        record["archive_capture_timestamp"] = timestamp
        record["archive_digest"] = row.get("digest")
        record["archive_mimetype"] = row.get("mimetype")
        record["source_raw_record"] = row
        records.append(enrich_status(record))
    return records


def load_prior_archive_pages(output_dir: Path, current_stamp: str) -> tuple[list[dict[str, Any]], str | None, set[str]]:
    """Reuse prior page bodies and identify archive IDs already attempted."""
    paths = sorted(output_dir.glob("*_historical_greenhouse_raw.json"))
    paths = [path for path in paths if not path.name.startswith(current_stamp)]
    for raw_path in reversed(paths):
        try:
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
            pages = [record for record in payload.get("records", [])
                     if record.get("source_type") == "internet_archive"
                     and record.get("source_page_html")]
            cdx_job_ids = {str(record.get("greenhouse_job_id")) for record in payload.get("records", [])
                           if record.get("source_type") == "internet_archive_cdx"
                           and record.get("greenhouse_job_id")}
            if pages or cdx_job_ids:
                return pages, raw_path.name, cdx_job_ids
        except (OSError, json.JSONDecodeError):
            continue
    return [], None, set()


def search_bing(client: httpx.Client, retrieved_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    raw_results: list[dict[str, Any]] = []
    errors: list[str] = []
    for query in SEARCH_QUERIES:
        try:
            response = get(client, BING_RSS, params={"format": "rss", "count": 50, "q": query})
            response.raise_for_status()
            root = ET.fromstring(response.text)
            for item in root.findall(".//item"):
                title = item.findtext("title") or ""
                url = item.findtext("link") or ""
                snippet = item.findtext("description") or ""
                pub_date = item.findtext("pubDate")
                if "greenhouse.io/anthropic/jobs/" not in url:
                    continue
                raw_result = {
                    "query": query,
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "pub_date": pub_date,
                    "retrieved_at": retrieved_at,
                }
                raw_results.append(raw_result)
                record = normalize_record(
                    {},
                    source_type="search_index",
                    source_url=url,
                    retrieved_at=retrieved_at,
                    index_result_date=pub_date,
                    search_title=title,
                    search_snippet=snippet,
                )
                record["greenhouse_job_id"] = get_job_id(url)
                records.append(enrich_status(record))
        except Exception as exc:
            errors.append(f"{query}: {type(exc).__name__}: {exc}")
    return records, raw_results, errors


def fetch_careers_evidence(client: httpx.Client, retrieved_at: str) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    try:
        response = get(client, CAREERS_PAGE)
        response.raise_for_status()
        page_html = response.text
        urls = sorted({canonical_url(url) for url in GREENHOUSE_URL_RE.findall(page_html) if canonical_url(url)})
        for url in urls:
            records.append(enrich_status(normalize_record(
                {}, source_type="anthropic_careers", source_url=CAREERS_PAGE,
                retrieved_at=retrieved_at, page_html=page_html,
                live_status="linked_from_current_anthropic_careers",
            )))
            records[-1]["absolute_url"] = url
            records[-1]["greenhouse_job_id"] = get_job_id(url)
        metadata = {"source_url": CAREERS_PAGE, "status_code": response.status_code,
                    "greenhouse_job_urls_found": len(urls), "retrieved_at": retrieved_at,
                    "page_html": page_html}
    except Exception as exc:
        failures.append(f"{CAREERS_PAGE}: {type(exc).__name__}: {exc}")
        metadata = {"source_url": CAREERS_PAGE, "retrieved_at": retrieved_at,
                    "error": failures[-1], "greenhouse_job_urls_found": 0}
    return records, metadata, failures


def merge_key(record: dict[str, Any]) -> tuple[str, str]:
    job_id = record.get("greenhouse_job_id")
    if job_id:
        return "id", str(job_id)
    url = canonical_url(record.get("absolute_url"))
    if url:
        return "url", url
    title = re.sub(r"\s+", " ", (record.get("exact_title") or "").strip().lower())
    location = re.sub(r"\s+", " ", str(record.get("location") or "").strip().lower())
    # Without an ID or URL, keep records separate by source URL. Never merge on
    # title alone because repeated roles and titles are common.
    source = canonical_url(record.get("source_url")) or record.get("source_url") or ""
    return "evidence", hashlib.sha256(f"{title}|{location}|{source}".encode()).hexdigest()


def reconcile(raw_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in raw_records:
        posting_url = urlparse(record.get("absolute_url") or "")
        is_greenhouse_posting = (
            posting_url.netloc.lower().endswith("greenhouse.io")
            and posting_url.path.startswith("/anthropic/jobs/")
        )
        if not record.get("greenhouse_job_id") and not is_greenhouse_posting:
            # Keep page-only careers observations in the raw source ledger,
            # but do not count a generic careers page as a job posting.
            continue
        groups[merge_key(record)].append(record)
    output: list[dict[str, Any]] = []
    duplicate_count = sum(max(0, len(group) - 1) for group in groups.values())
    for key, group in groups.items():
        # Greenhouse detail/list fields outrank archived page and index snippets.
        priority = {"greenhouse_current_api": 0, "internet_archive": 1, "internet_archive_cdx": 1,
                    "anthropic_careers_archive": 2, "anthropic_careers": 3,
                    "search_index": 4, "secondary_source": 5}
        group_sorted = sorted(group, key=lambda item: (
            priority.get(item.get("source_type"), 9),
            -len(item.get("description_html") or ""),
            item.get("retrieved_at") or "",
        ))
        chosen = dict(group_sorted[0])
        # Fill nulls from the strongest available evidence, but do not replace
        # a date or HTML with weaker evidence.
        for candidate in group_sorted[1:]:
            for field in (
                "exact_title", "absolute_url", "location", "requisition_id", "departments",
                "offices", "description_html", "description_text", "created_at",
                "first_published_at", "updated_at", "archive_capture_date", "index_result_date",
            ):
                if chosen.get(field) is None and candidate.get(field) is not None:
                    chosen[field] = candidate[field]
        chosen["evidence"] = [
            {"source_type": item.get("source_type"), "source_url": item.get("source_url"),
             "archive_capture_date": item.get("archive_capture_date"),
             "index_result_date": item.get("index_result_date"),
             "retrieved_at": item.get("retrieved_at"),
             "historical_status": item.get("historical_status"),
             "date_confidence": item.get("date_confidence")}
            for item in group
        ]
        chosen["source_types"] = sorted({item.get("source_type") for item in group if item.get("source_type")})
        chosen["source_urls"] = sorted({item.get("source_url") for item in group if item.get("source_url")})
        # Select the strongest date evidence for the merged status.
        status_candidates = [enrich_status(dict(item)) for item in group]
        status_rank = {"historical_verified": 0, "archive_only": 1, "historical_probable": 2,
                       "indexed_only": 3, "current_only": 4, "date_unresolved": 5,
                       "not_recoverable": 6}
        best_status = min(status_candidates, key=lambda item: status_rank.get(item["historical_status"], 9))
        chosen["historical_status"] = best_status["historical_status"]
        chosen["date_confidence"] = best_status["date_confidence"]
        chosen["posting_date_if_known"] = best_status.get("posting_date_if_known")
        departments = chosen.get("departments") or []
        if isinstance(departments, dict):
            departments = [departments]
        department_text = " ".join(
            str(item.get("name", "")) if isinstance(item, dict) else str(item)
            for item in departments
        )
        # Avoid classifying every role as research because Anthropic boilerplate
        # mentions research in generic company descriptions. Use posting title
        # and department labels for this preliminary, auditable tag.
        text_to_classify = " ".join((chosen.get("exact_title") or "", department_text))
        chosen["research_classified"] = bool(RESEARCH_TERMS.search(text_to_classify))
        chosen["fellowship_classified"] = bool(FELLOWSHIP_TERMS.search(text_to_classify))
        chosen["dedup_key_type"] = key[0]
        chosen["dedup_key"] = key[1]
        # The raw observation artifact retains complete Greenhouse API records
        # and archived page HTML. The reconciled output carries exact
        # description_html plus concise source evidence without duplicating
        # whole pages and descriptions a second time.
        chosen.pop("source_page_html", None)
        chosen.pop("source_raw_record", None)
        output.append(chosen)
    output.sort(key=lambda item: (item.get("exact_title") or "", item.get("greenhouse_job_id") or ""))
    return output, duplicate_count


class R2Store:
    """Minimal SigV4 S3-compatible R2 client with conditional immutable writes."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
        parsed = urlparse(endpoint)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError("R2_ENDPOINT must be an absolute URL.")
        self.endpoint, self.host = endpoint.rstrip("/"), parsed.netloc
        self.access_key, self.secret_key, self.bucket = access_key, secret_key, bucket
        self.client = httpx.Client(timeout=180, follow_redirects=False)

    def request(self, method: str, key: str, body: bytes = b"",
                content_type: str | None = None) -> httpx.Response:
        now = utc_now()
        amz_date, date = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
        payload_hash = sha256(body)
        canonical_uri = f"/{quote(self.bucket, safe='')}/{quote(key, safe='/')}"
        headers = {"host": self.host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
        if method == "PUT":
            headers.update({"if-none-match": "*", "content-type": content_type or "application/octet-stream"})
        signed_names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name].strip()}\n" for name in sorted(headers))
        canonical_request = "\n".join((method, canonical_uri, "", canonical_headers, signed_names, payload_hash))
        scope = f"{date}/auto/s3/aws4_request"
        string_to_sign = "\n".join(("AWS4-HMAC-SHA256", amz_date, scope,
                                     hashlib.sha256(canonical_request.encode()).hexdigest()))
        key_date = hmac.new(("AWS4" + self.secret_key).encode(), date.encode(), hashlib.sha256).digest()
        key_region = hmac.new(key_date, b"auto", hashlib.sha256).digest()
        key_service = hmac.new(key_region, b"s3", hashlib.sha256).digest()
        signing_key = hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        auth = (f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, "
                f"SignedHeaders={signed_names}, Signature={signature}")
        outgoing = {name: value for name, value in headers.items() if name != "host"}
        outgoing["Authorization"] = auth
        response = self.client.request(method, self.endpoint + canonical_uri, headers=outgoing, content=body)
        response.raise_for_status()
        return response

    def put_immutable(self, key: str, body: bytes, content_type: str) -> None:
        for attempt in range(4):
            try:
                self.request("PUT", key, body, content_type)
                return
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 412 and sha256(self.get(key)) == sha256(body):
                    return
                raise
            except httpx.TransportError:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)

    def get(self, key: str) -> bytes:
        for attempt in range(4):
            try:
                return self.request("GET", key).content
            except httpx.TransportError:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("R2 GET retry loop exited unexpectedly.")

    def close(self) -> None:
        self.client.close()


def verify_object(store: R2Store, key: str, expected: bytes,
                  expected_row_count: int | None = None) -> dict[str, Any]:
    actual = store.get(key)
    if sha256(actual) != sha256(expected):
        raise RuntimeError(f"R2 read-back mismatch for {key}.")
    result = {"key": key, "bytes": len(actual), "sha256": sha256(actual), "matches_local": True}
    if expected_row_count is not None:
        payload = json.loads(actual)
        row_count = len(payload.get("records", []))
        result.update({"row_count": row_count, "expected_row_count": expected_row_count,
                       "row_count_matches": row_count == expected_row_count})
        if row_count != expected_row_count:
            raise RuntimeError(f"R2 read-back row count mismatch for {key}: {row_count} != {expected_row_count}.")
    return result


def baseline_timestamp_audit() -> dict[str, Any]:
    audit_path = PROJECT_ROOT / "job_postings/snapshots/20260929T061625Z_greenhouse_anthropic_current_audit.json"
    timestamp = "2026-09-29T06:16:25Z"
    utc_value = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    local_value = utc_value.astimezone(ZoneInfo("America/Phoenix"))
    observed_now = utc_now()
    prior_audit: dict[str, Any] | None = None
    if audit_path.exists():
        try:
            prior_audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior_audit = None
    return {
        "snapshot_timestamp_utc": timestamp,
        "snapshot_timestamp_local_phoenix": local_value.isoformat(),
        "system_utc_at_historical_run": observed_now.isoformat().replace("+00:00", "Z"),
        "current_snapshot_audit_local_file_found": audit_path.exists(),
        "current_snapshot_audit_verified": prior_audit.get("verified") if prior_audit else None,
        "finding": "Timestamp date is September 29 UTC because it corresponds to September 28 at 23:16 in America/Phoenix; the UTC system clock is September 29. No future-time discrepancy is indicated by these clocks.",
    }


def main() -> None:
    load_env_file(ENV_FILE)
    retrieved_at = utc_iso()
    run_stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html,application/rss+xml,*/*"},
        timeout=90,
        follow_redirects=True,
    )
    source_errors: list[str] = []
    raw_records: list[dict[str, Any]] = []

    greenhouse_records, greenhouse_meta, greenhouse_errors = fetch_greenhouse(client, retrieved_at)
    raw_records.extend(greenhouse_records)
    source_errors.extend(greenhouse_errors)

    greenhouse_cdx, greenhouse_cdx_error = cdx_rows(
        client, "https://job-boards.greenhouse.io/anthropic/jobs/",
        from_date=START_CDX, to_date=END_CDX, match_type="prefix", collapse="urlkey",
    )
    if greenhouse_cdx_error:
        source_errors.append("greenhouse_wayback_cdx: " + greenhouse_cdx_error)
    archive_cdx_records = archive_index_records(greenhouse_cdx, retrieved_at)
    prior_archive_pages, prior_archive_raw, prior_cdx_job_ids = load_prior_archive_pages(OUTPUT_DIR, run_stamp)
    prior_page_job_ids = {str(record.get("greenhouse_job_id")) for record in prior_archive_pages
                          if record.get("greenhouse_job_id")}
    page_rows = choose_one_capture_per_job(greenhouse_cdx)
    retry_prior_archive_failures = os.getenv("RETRY_ARCHIVE_PAGES", "").lower() in {"1", "true", "yes"}
    page_rows_to_fetch = [
        row for row in page_rows
        if get_job_id(row.get("original")) not in prior_page_job_ids
        and (retry_prior_archive_failures or get_job_id(row.get("original")) not in prior_cdx_job_ids)
    ]
    newly_fetched_archive_records, archive_errors = fetch_archived_pages(
        client, page_rows_to_fetch, retrieved_at, "internet_archive",
    )
    archive_records = prior_archive_pages + newly_fetched_archive_records
    raw_records.extend(archive_cdx_records)
    raw_records.extend(archive_records)
    source_errors.extend("greenhouse_wayback_capture: " + error for error in archive_errors)

    search_records, search_results, search_errors = search_bing(client, retrieved_at)
    raw_records.extend(search_records)
    source_errors.extend("bing_search: " + error for error in search_errors)

    careers_records, careers_current_meta, careers_errors = fetch_careers_evidence(client, retrieved_at)
    raw_records.extend(careers_records)
    source_errors.extend("anthropic_careers: " + error for error in careers_errors)
    careers_cdx, careers_cdx_error = cdx_rows(
        client, CAREERS_PAGE, from_date=START_CDX, to_date=END_CDX,
        match_type="exact", collapse="urlkey",
    )
    if careers_cdx_error:
        source_errors.append("careers_wayback_cdx: " + careers_cdx_error)
    careers_archive_records, careers_archive_errors = fetch_archived_pages(
        client, careers_cdx, retrieved_at, "anthropic_careers_archive",
    )
    # Archive captures of Anthropic's career page are corroborating evidence;
    # retain page observations, and link any Greenhouse URLs explicitly present.
    for record in careers_archive_records:
        page_html = record.get("source_page_html") or ""
        urls = sorted({canonical_url(url) for url in GREENHOUSE_URL_RE.findall(page_html) if canonical_url(url)})
        if urls:
            for url in urls:
                linked = dict(record)
                linked["absolute_url"] = url
                linked["greenhouse_job_id"] = get_job_id(url)
                linked["historical_status"] = "historical_probable"
                linked["date_confidence"] = "anthropic_careers_archive_capture"
                raw_records.append(linked)
        else:
            raw_records.append(record)
    source_errors.extend("careers_wayback_capture: " + error for error in careers_archive_errors)
    client.close()

    deduplicated, duplicate_count = reconcile(raw_records)
    historical_supported_statuses = {"historical_verified", "historical_probable", "archive_only"}
    historical_records = [item for item in deduplicated if item.get("historical_status") in historical_supported_statuses]
    # Keep the full reconciled candidate corpus (including current-only and
    # indexed-only records) so later users can apply their own evidence threshold.
    source_type_counts = Counter(item.get("source_type") for item in raw_records)
    evidence_types_by_posting: dict[str, set[str]] = defaultdict(set)
    for item in deduplicated:
        for source_type in item.get("source_types", []):
            evidence_types_by_posting[source_type].add(item.get("dedup_key", ""))
    verified_dates = [parse_date(item.get("posting_date_if_known")) for item in deduplicated]
    verified_dates = [value for value in verified_dates if in_scope(value)]
    status_counts = Counter(item.get("historical_status") for item in deduplicated)
    confidence_counts = Counter(item.get("date_confidence") for item in deduplicated)
    archive_page_job_ids = {str(item.get("greenhouse_job_id")) for item in archive_records
                            if item.get("greenhouse_job_id")}
    unresolved_archive_only = sum(
        item.get("historical_status") == "archive_only" and not item.get("first_published_at")
        for item in deduplicated
    )
    count_evidence_source = lambda source_type: len(evidence_types_by_posting.get(source_type, set()))
    audit: dict[str, Any] = {
        "audit_type": "historical_greenhouse_recovery",
        "run_timestamp_utc": retrieved_at,
        "target_period": {"start_inclusive": START_DATE.isoformat(), "end_inclusive": END_DATE.isoformat()},
        "baseline_timestamp_review": baseline_timestamp_audit(),
        "methodology": {
            "posting_date_rule": "Only Greenhouse first_published within the target period is treated as a verified posting date.",
            "archive_rule": "archive_capture_date records an Internet Archive capture date and is never copied into posting_date_if_known.",
            "current_board_rule": "Current board presence alone does not establish that a posting existed during the target period.",
            "search_index_rule": "Search engine result dates are stored separately and are not treated as posting dates.",
            "deduplication_rule": "Use Greenhouse job ID; otherwise canonical posting URL; without either, use title/location/source evidence and do not merge on title alone.",
            "research_classification_rule": "Preliminary keyword flag uses exact title and department only, avoiding generic Anthropic description boilerplate; no gender-language analysis is performed.",
            "search_queries": SEARCH_QUERIES,
            "source_order": ["public_greenhouse", "search_index", "internet_archive", "anthropic_careers", "secondary_sources"],
            "secondary_sources_used": False,
        },
        "counts": {
            "raw_source_observations": len(raw_records),
            "unique_historical_postings_recovered": len(historical_records),
            "unique_reconciled_candidates_including_current_or_unresolved": len(deduplicated),
            "with_verified_posting_dates": sum(bool(in_scope(parse_date(item.get("posting_date_if_known")))) for item in deduplicated),
            "with_only_archive_capture_dates": unresolved_archive_only,
            "with_unresolved_dates": status_counts.get("date_unresolved", 0) + status_counts.get("indexed_only", 0) + unresolved_archive_only,
            "recovered_from_greenhouse": count_evidence_source("greenhouse_current_api"),
            "recovered_from_search_index_evidence": count_evidence_source("search_index"),
            "recovered_from_internet_archive": count_evidence_source("internet_archive") + count_evidence_source("internet_archive_cdx"),
            "recovered_from_anthropic_careers_evidence": count_evidence_source("anthropic_careers") + count_evidence_source("anthropic_careers_archive"),
            "recovered_from_secondary_sources": count_evidence_source("secondary_source"),
            "duplicate_records_identified": duplicate_count,
            "research_classified_postings": sum(bool(item.get("research_classified")) for item in historical_records),
            "fellowship_postings": sum(bool(item.get("fellowship_classified")) for item in historical_records),
            "description_html_present": sum(bool(item.get("description_html")) for item in deduplicated),
            "description_html_missing": sum(not bool(item.get("description_html")) for item in deduplicated),
            "exact_titles_present": sum(bool(item.get("exact_title")) for item in deduplicated),
            "absolute_urls_present": sum(bool(item.get("absolute_url")) for item in deduplicated),
            "full_archive_page_html_available_for_unique_job_ids": len(archive_page_job_ids),
            "archive_index_job_ids_without_downloaded_page_html": len({
                str(item.get("greenhouse_job_id")) for item in archive_cdx_records
                if item.get("greenhouse_job_id")
            } - archive_page_job_ids),
            "historical_status_counts": dict(status_counts),
            "date_confidence_counts": dict(confidence_counts),
        },
        "date_range": {
            "earliest_supported_posting_date": min(verified_dates).isoformat() if verified_dates else None,
            "latest_supported_posting_date": max(verified_dates).isoformat() if verified_dates else None,
        },
        "greenhouse": {key: value for key, value in greenhouse_meta.items() if key != "raw_board_response"},
        "internet_archive": {
            "greenhouse_cdx_rows": len(greenhouse_cdx),
            "greenhouse_unique_job_ids_in_cdx": len({get_job_id(row.get("original")) for row in greenhouse_cdx if get_job_id(row.get("original"))}),
            "greenhouse_capture_records_fetched_this_run": len(newly_fetched_archive_records),
            "greenhouse_cached_page_records_reused": len(prior_archive_pages),
            "greenhouse_page_rows_selected_one_per_job_id": len(page_rows),
            "greenhouse_page_rows_attempted_this_run": len(page_rows_to_fetch),
            "greenhouse_prior_index_ids_without_page_html_retried": (
                len(prior_cdx_job_ids - prior_page_job_ids) if retry_prior_archive_failures else 0
            ),
            "retry_prior_archive_failures_environment_setting": "RETRY_ARCHIVE_PAGES=1",
            "prior_archive_page_cache_source": prior_archive_raw,
            "greenhouse_cdx_result_limit": 5000,
            "greenhouse_cdx_limit_reached": len(greenhouse_cdx) >= 5000,
            "greenhouse_cdx_url": WAYBACK_CDX,
            "careers_cdx_rows": len(careers_cdx),
            "careers_capture_records_fetched": len(careers_archive_records),
            "careers_cdx_result_limit": 5000,
            "careers_cdx_limit_reached": len(careers_cdx) >= 5000,
        },
        "search_index": {
            "provider": "Bing public RSS search",
            "queries_run": len(SEARCH_QUERIES),
            "results_retained": len(search_results),
        },
        "anthropic_careers": {
            "current_page": {key: value for key, value in careers_current_meta.items() if key != "page_html"},
            "archived_page_captures": len(careers_archive_records),
        },
        "source_errors": {
            "this_run_count": len(source_errors),
            "this_run_by_category": dict(Counter(item.split(":", 1)[0] for item in source_errors)),
            "prior_indexed_ids_without_page_html": len(prior_cdx_job_ids - prior_page_job_ids),
            "prior_retrieval_note": (
                "The preceding full replay-page attempt encountered ConnectTimeout errors; "
                "the corresponding CDX URL, job ID, and archive capture-date evidence are retained."
            ),
            "retry_prior_failures_setting": "RETRY_ARCHIVE_PAGES=1",
            "examples": source_errors[:20],
        },
        "not_recoverable_note": "A missing or closed posting is not labeled not_recoverable unless a specific target posting is independently known but all searched public sources lack a surviving copy. This run does not invent such records.",
        "r2_readback": {},
    }
    audit["verification"] = {
        "greenhouse_total_matches": greenhouse_meta["total_matches_response_count"],
        "all_raw_observations_retained_before_deduplication": True,
        "archive_capture_dates_separate_from_posting_dates": True,
        "no_updated_at_used_as_posting_date": True,
        "unique_records_equal_output_row_count": len(deduplicated) == len({item["dedup_key"] for item in deduplicated}),
    }

    raw_output = {
        "source": "public source observations before deduplication",
        "retrieved_at": retrieved_at,
        "target_period": audit["target_period"],
        "greenhouse_board_metadata": greenhouse_meta,
        "bing_search_results": search_results,
        "anthropic_careers_current_metadata": careers_current_meta,
        "records": raw_records,
    }
    filtered_output = {
        "source": "deduplicated evidence-linked candidate corpus",
        "retrieved_at": retrieved_at,
        "target_period": audit["target_period"],
        "in_period_supported_record_count": len(historical_records),
        "candidate_record_count": len(deduplicated),
        "records": deduplicated,
    }
    raw_bytes = json_bytes(raw_output)
    filtered_bytes = json_bytes(filtered_output)
    raw_local = OUTPUT_DIR / f"{run_stamp}_historical_greenhouse_raw.json"
    filtered_local = OUTPUT_DIR / f"{run_stamp}_historical_greenhouse_deduplicated.json"
    audit_local = OUTPUT_DIR / f"{run_stamp}_historical_greenhouse_audit.json"
    raw_local.write_bytes(raw_bytes)
    filtered_local.write_bytes(filtered_bytes)

    store = R2Store(
        endpoint=required_env("R2_ENDPOINT"),
        access_key=required_env("R2_ACCESS_KEY_ID"),
        secret_key=required_env("R2_SECRET_ACCESS_KEY"),
        bucket=required_env("R2_BUCKET"),
    )
    raw_key = f"raw/job-postings/historical-greenhouse/{run_stamp}/historical_greenhouse_raw.json"
    filtered_key = f"filtered/job-postings/{run_stamp}/historical_greenhouse_deduplicated.json"
    audit_key = f"audit/job-postings/{run_stamp}/historical_greenhouse_audit.json"
    store.put_immutable(raw_key, raw_bytes, "application/json")
    store.put_immutable(filtered_key, filtered_bytes, "application/json")
    audit["r2_readback"]["raw"] = verify_object(store, raw_key, raw_bytes, len(raw_records))
    audit["r2_readback"]["filtered"] = verify_object(store, filtered_key, filtered_bytes, len(deduplicated))
    audit["verification"].update({
        "r2_raw_object_readback_matches": audit["r2_readback"]["raw"]["matches_local"],
        "r2_filtered_object_readback_matches": audit["r2_readback"]["filtered"]["matches_local"],
        "r2_raw_row_count": len(raw_records),
        "r2_filtered_row_count": len(deduplicated),
        "r2_raw_row_count_matches": audit["r2_readback"]["raw"]["row_count_matches"],
        "r2_filtered_row_count_matches": audit["r2_readback"]["filtered"]["row_count_matches"],
    })
    audit_bytes = json_bytes(audit)
    audit_local.write_bytes(audit_bytes)
    store.put_immutable(audit_key, audit_bytes, "application/json")
    audit_readback = verify_object(store, audit_key, audit_bytes)
    store.close()

    summary = {
        "run_timestamp_utc": retrieved_at,
        "verified": all(item.get("matches_local") for item in audit["r2_readback"].values()) and audit_readback["matches_local"],
        "target_period": audit["target_period"],
        "counts": audit["counts"],
        "date_range": audit["date_range"],
        "r2_objects": {"raw": audit["r2_readback"]["raw"],
                       "filtered": audit["r2_readback"]["filtered"],
                       "audit": audit_readback},
        "local_outputs": {"raw": str(raw_local), "filtered": str(filtered_local), "audit": str(audit_local)},
        "source_errors": audit["source_errors"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["verified"]:
        raise SystemExit("Historical outputs were written, but one or more R2 read-back checks failed.")


if __name__ == "__main__":
    main()
