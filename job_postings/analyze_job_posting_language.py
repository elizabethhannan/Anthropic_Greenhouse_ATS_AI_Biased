"""Extract auditable descriptive language measures from verified job postings.

Reads only the verified analytical historical Greenhouse master in R2. Names
are detected conservatively and never used to infer gender. Every extracted
name or explicit gendered expression is retained with its sentence context.
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
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "r2.env"
INPUT_RUN = "20260929T091413Z"
INPUT_RELATIVE_KEY = f"filtered/job-postings/analysis/{INPUT_RUN}/historical_greenhouse_analytical_master.json"
STUDY_START = dt.date(2026, 4, 1)
STUDY_END = dt.date(2026, 9, 30)

PRONOUNS = {
    "masculine": re.compile(r"\b(?:he|him|his|himself)\b", re.I),
    "feminine": re.compile(r"\b(?:she|her|hers|herself)\b", re.I),
}
EXPLICIT_REFERENCES = {
    "explicit_male": re.compile(r"\b(?:man|men|male|males|boy|boys|gentleman|gentlemen)\b", re.I),
    "explicit_female": re.compile(r"\b(?:woman|women|female|females|girl|girls|lady|ladies)\b", re.I),
}
GENDER_PATTERNS = [(kind, pattern) for kind, pattern in (
    [(f"{group}_pronoun", pattern) for group, pattern in PRONOUNS.items()]
    + [(kind, pattern) for kind, pattern in EXPLICIT_REFERENCES.items()]
)]
HONORIFIC_NAME = re.compile(
    r"\b(?:Dr|Doctor|Prof|Professor|Mr|Mrs|Ms|Mx)\.?\s+"
    r"([A-Z][\w’'-]+(?:\s+(?:[A-Z]\.\s*)?[A-Z][\w’'-]+){0,3})"
)
PROPER_NAME = re.compile(r"\b([A-Z][a-z’'-]{1,25}(?:\s+[A-Z][a-z’'-]{1,25}){1,2})\b")
PERSON_VERBS = re.compile(
    r"^\s+(?:is|was|has been|joined|founded|worked|studied|served|led|"
    r"wrote|said|became|graduated|previously worked|formerly worked)\b", re.I
)
PERSON_PRECEDERS = re.compile(
    r"\b(?:according to|named|interview with|biography of|"
    r"testimonial from|for example,?|research lead,|lecture given by|podcast with)\s+$", re.I
)
BIO_CUES = re.compile(
    r"\b(?:biograph(?:y|ical)|testimonial|joined (?:the company|anthropic|our team)|"
    r"previously (?:worked|served|led)|formerly (?:worked|served)|"
    r"grew up|earned (?:a|an|their|her|his)|graduated|career (?:path|journey)|"
    r"(?:he|she) (?:joined|worked|studied|founded|led|served))\b", re.I
)
EXAMPLE_CUES = re.compile(r"\b(?:for example|such as|e\.g\.?|consider|imagine|one example)\b", re.I)
TITLE_WORDS = {
    "Anthropic", "Claude", "Research", "Scientist", "Engineer", "Engineering", "Safety",
    "AI", "ML", "Machine", "Learning", "Model", "Models", "Behavior", "Evaluation",
    "Evaluations", "Interpretability", "Alignment", "Fellows", "Fellowship", "Program",
    "Team", "Role", "Responsibilities", "About", "We", "Our", "The", "This", "You",
    "What", "Who", "Location", "Salary", "Benefits", "Compensation", "Candidates",
    "Applicants", "United", "States", "Remote", "San", "Francisco", "New", "York",
    "Native-level", "Researcher", "Researchers", "Scientist", "Scientists", "Engineer",
    "Engineers", "Director", "Directors", "Founder", "Founders", "Author", "Authors",
    "Professor", "Professors", "Japanese", "Korean", "French", "German", "Spanish",
    "Chinese", "English", "Hindi", "Portuguese", "Arabic", "ASEAN", "Solutions",
    "Architect", "Architects", "Technical", "Account", "Manager", "Managers", "Customer",
    "Success", "Revenue", "Controls", "Neurons", "Multimodal", "Constitutional",
}


def load_env() -> None:
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def source_key(relative: str) -> str:
    prefix = os.getenv("R2_PREFIX", "").strip("/")
    return f"{prefix}/{relative}" if prefix else relative


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
        stamp_dt = utcnow()
        stamp, day = stamp_dt.strftime("%Y%m%dT%H%M%SZ"), stamp_dt.strftime("%Y%m%d")
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
        key_date = hmac.new(("AWS4" + self.secret).encode(), day.encode(), hashlib.sha256).digest()
        key_region = hmac.new(key_date, b"auto", hashlib.sha256).digest()
        key_service = hmac.new(key_region, b"s3", hashlib.sha256).digest()
        signing_key = hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).hexdigest()
        headers["Authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access}/{scope}, SignedHeaders={names}, Signature={signature}"
        )
        outgoing = {name: value for name, value in headers.items() if name != "host"}
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

    def put(self, key: str, body: bytes) -> None:
        for attempt in range(4):
            try:
                self.request("PUT", key, body)
                return
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 412 and sha(self.get(key)) == sha(body):
                    return
                raise
            except httpx.TransportError:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)


def to_text(record: dict[str, Any]) -> str:
    text = record.get("description_text")
    if isinstance(text, str) and text.strip():
        return html.unescape(text)
    markup = record.get("description_html")
    if not isinstance(markup, str) or not markup.strip():
        return ""
    decoded = html.unescape(markup)
    decoded = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>", " ", decoded)
    decoded = re.sub(r"(?s)<[^>]+>", " ", decoded)
    return re.sub(r"\s+", " ", decoded).strip()


def sentences(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group().strip()) for m in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text) if m.group().strip()]


def sentence_at(text: str, start: int, end: int) -> str:
    for left, right, sentence in sentences(text):
        if left <= start < right or left < end <= right:
            return sentence[:600]
    left = max(0, start - 180)
    right = min(len(text), end + 180)
    return text[left:right].strip()[:600]


def person_candidates(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    for match in HONORIFIC_NAME.finditer(text):
        name = re.sub(r"\s+", " ", match.group(1)).strip()
        if any(token in TITLE_WORDS for token in name.split()):
            continue
        start, end = match.span(1)
        candidates.append({"name": name, "start": start, "end": end, "basis": "honorific plus proper name"})
        occupied.append(match.span())
    for match in PROPER_NAME.finditer(text):
        start, end = match.span(1)
        if any(a <= start and end <= b for a, b in occupied):
            continue
        name = re.sub(r"\s+", " ", match.group(1)).strip()
        tokens = name.split()
        if any(token in TITLE_WORDS for token in tokens) or len(tokens) < 2:
            continue
        # Require a person-name construction: a name immediately before a
        # person-specific verb, or immediately after an explicit naming/source
        # marker. Broad cues such as "researcher" and "such as" created false
        # positives from role names, product terms, and languages.
        before = text[max(0, start - 42):start]
        after = text[end:min(len(text), end + 42)]
        preceding_marker = bool(PERSON_PRECEDERS.search(before))
        following_verb = bool(PERSON_VERBS.search(after))
        if preceding_marker or following_verb:
            candidates.append({"name": name, "start": start, "end": end, "basis": "proper-name form near person/example/biography cue"})
    candidates.sort(key=lambda x: (x["start"], x["end"]))
    # Drop overlapping detections while retaining repeated mentions at distinct positions.
    result: list[dict[str, Any]] = []
    last_end = -1
    for item in candidates:
        if item["start"] < last_end:
            continue
        result.append(item)
        last_end = item["end"]
    return result


def gender_matches(text: str) -> list[dict[str, Any]]:
    found = []
    for evidence_type, pattern in GENDER_PATTERNS:
        for match in pattern.finditer(text):
            found.append({"start": match.start(), "end": match.end(), "matched_text": match.group(),
                          "gender_evidence_type": evidence_type})
    return sorted(found, key=lambda item: (item["start"], item["end"]))


def explicit_gender_for_person(text: str, person: dict[str, Any], matches: list[dict[str, Any]]) -> tuple[str, str | None, str | None]:
    # A name is associated only with explicit gender evidence in the same sentence.
    context = sentence_at(text, person["start"], person["end"])
    nearby = [m for m in matches if m["matched_text"].casefold() in context.casefold()]
    kinds = {m["gender_evidence_type"] for m in nearby}
    if any(k.startswith("masculine") or k == "explicit_male" for k in kinds) and not any(k.startswith("feminine") or k == "explicit_female" for k in kinds):
        return "Explicit masculine reference in same sentence", nearby[0]["gender_evidence_type"], nearby[0]["matched_text"]
    if any(k.startswith("feminine") or k == "explicit_female" for k in kinds) and not any(k.startswith("masculine") or k == "explicit_male" for k in kinds):
        return "Explicit feminine reference in same sentence", nearby[0]["gender_evidence_type"], nearby[0]["matched_text"]
    if nearby:
        return "Explicit gender reference in same sentence; direction mixed", "mixed_explicit_evidence", ", ".join(m["matched_text"] for m in nearby)
    return "Not Established", None, None


def analyze_record(record: dict[str, Any], retrieved_at: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    text = to_text(record)
    available = bool(text.strip())
    words = re.findall(r"\b[\w’'-]+\b", text, re.UNICODE) if available else []
    names = person_candidates(text) if available else []
    gender = gender_matches(text) if available else []
    bio_flag = bool(BIO_CUES.search(text)) if available else False
    example_flag = bool(EXAMPLE_CUES.search(text) and names) if available else False
    title = record.get("exact_title")
    posting_id = record.get("greenhouse_job_id") or record.get("dedup_key") or record.get("absolute_url")
    person_rows = []
    for person in names:
        gender_class, associated_type, associated_text = explicit_gender_for_person(text, person, gender)
        sentence = sentence_at(text, person["start"], person["end"])
        person_rows.append({
            "posting_id": posting_id, "exact_title": title, "person_mention": person["name"],
            "gender_classification": gender_class, "gender_evidence_type": associated_type,
            "matched_text": associated_text or person["name"], "surrounding_context": sentence,
            "mention_basis": person["basis"], "testimonial_or_biography_flag": bio_flag,
            "example_person_flag": bool(EXAMPLE_CUES.search(sentence)),
            "source_description": record.get("description_text") or record.get("description_html"),
            "source_url": record.get("absolute_url"), "manual_review_required": True,
        })
    gender_rows = []
    for item in gender:
        sentence = sentence_at(text, item["start"], item["end"])
        linked = [p["name"] for p in names if p["start"] < item["end"] and item["start"] < p["end"]]
        gender_rows.append({
            "posting_id": posting_id, "exact_title": title,
            "person_mention": linked[0] if len(linked) == 1 else None,
            "gender_evidence_type": item["gender_evidence_type"], "matched_text": item["matched_text"],
            "surrounding_context": sentence,
            "source_description": record.get("description_text") or record.get("description_html"),
            "source_url": record.get("absolute_url"),
        })
    masculine_count = sum(item["gender_evidence_type"].startswith("masculine") for item in gender)
    feminine_count = sum(item["gender_evidence_type"].startswith("feminine") for item in gender)
    male_count = sum(item["gender_evidence_type"] == "explicit_male" for item in gender)
    female_count = sum(item["gender_evidence_type"] == "explicit_female" for item in gender)
    metric = dict(record)  # preserve all input fields and add analysis fields
    metric.update({
        "description_available": available,
        "description_word_count": len(words),
        "named_person_mentions": len(names),
        "named_person_names": list(dict.fromkeys(person["name"] for person in names)),
        "masculine_pronoun_count": masculine_count,
        "feminine_pronoun_count": feminine_count,
        "explicit_male_reference_count": male_count,
        "explicit_female_reference_count": female_count,
        "gendered_reference_flag": bool(gender),
        "testimonial_or_biography_flag": bio_flag,
        "example_person_flag": example_flag,
        "research_flag": record.get("research_flag"),
        "research_subclass": record.get("research_subclass"),
        "fellowship_flag": record.get("fellowship_flag"),
        "date_evidence_class": record.get("date_evidence_class"),
        "date_confidence": record.get("date_confidence"),
        "manual_review_required": bool(names or gender or bio_flag or example_flag),
        "language_analysis_retrieved_at": retrieved_at,
    })
    return metric, person_rows, gender_rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "posting_count": len(rows),
        "descriptions_analyzed": sum(bool(r["description_available"]) for r in rows),
        "postings_with_named_person_references": sum(r["named_person_mentions"] > 0 for r in rows),
        "named_person_mentions": sum(r["named_person_mentions"] for r in rows),
        "postings_with_masculine_references": sum(r["masculine_pronoun_count"] > 0 or r["explicit_male_reference_count"] > 0 for r in rows),
        "masculine_pronoun_count": sum(r["masculine_pronoun_count"] for r in rows),
        "explicit_male_reference_count": sum(r["explicit_male_reference_count"] for r in rows),
        "postings_with_feminine_references": sum(r["feminine_pronoun_count"] > 0 or r["explicit_female_reference_count"] > 0 for r in rows),
        "feminine_pronoun_count": sum(r["feminine_pronoun_count"] for r in rows),
        "explicit_female_reference_count": sum(r["explicit_female_reference_count"] for r in rows),
        "postings_with_any_gendered_reference": sum(r["gendered_reference_flag"] for r in rows),
        "gendered_reference_occurrences": sum(
            r["masculine_pronoun_count"] + r["feminine_pronoun_count"] +
            r["explicit_male_reference_count"] + r["explicit_female_reference_count"] for r in rows),
        "testimonial_or_biography_postings": sum(r["testimonial_or_biography_flag"] for r in rows),
        "example_person_postings": sum(r["example_person_flag"] for r in rows),
        "manual_review_postings": sum(r["manual_review_required"] for r in rows),
        "research_postings": sum(r.get("research_flag") is True for r in rows),
        "fellowship_postings": sum(bool(r.get("fellowship_flag")) for r in rows),
        "research_and_fellowship_postings": sum(r.get("research_flag") is True and bool(r.get("fellowship_flag")) for r in rows),
    }


def main() -> None:
    load_env()
    store = R2()
    input_key = source_key(INPUT_RELATIVE_KEY)
    try:
        source_bytes = store.get(input_key)
        source = json.loads(source_bytes)
        postings = source.get("records")
        if not isinstance(postings, list) or not postings:
            raise RuntimeError("Analytical master is missing its records array.")
        if source.get("source_record_count") != len(postings):
            raise RuntimeError("Analytical master source_record_count does not match records.")
        retrieved_at = utcnow().isoformat().replace("+00:00", "Z")
        metrics: list[dict[str, Any]] = []
        person_audit: list[dict[str, Any]] = []
        gender_audit: list[dict[str, Any]] = []
        for posting in postings:
            row, people, gendered = analyze_record(posting, retrieved_at)
            metrics.append(row)
            person_audit.extend(people)
            gender_audit.extend(gendered)

        breakdown: dict[str, Any] = {"all_postings": summarize(metrics)}
        breakdown["research_postings"] = summarize([r for r in metrics if r.get("research_flag") is True])
        breakdown["fellowship_postings"] = summarize([r for r in metrics if r.get("fellowship_flag") is True])
        breakdown["research_and_fellowship"] = summarize([
            r for r in metrics if r.get("research_flag") is True and r.get("fellowship_flag") is True])
        by_date = {}
        for evidence_class in sorted({str(r.get("date_evidence_class") or "MISSING") for r in metrics}):
            by_date[evidence_class] = summarize([r for r in metrics if (r.get("date_evidence_class") or "MISSING") == evidence_class])
        breakdown["date_evidence_class"] = by_date

        runstamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
        base_rel = f"outputs/job-postings/language-analysis/{runstamp}"
        base = source_key(base_rel)
        meta = {"analysis_type": "job_posting_language_descriptive", "source_r2_key": input_key,
                "source_sha256": sha(source_bytes), "source_posting_count": len(postings),
                "generated_at": retrieved_at, "gender_inference_from_names": False,
                "scope_note": "Descriptive extraction only; no bias, discrimination, preference, intent, or hiring comparison claims."}
        outputs = {
            "posting_language_metrics.json": {**meta, "row_count": len(metrics), "records": metrics},
            "person_example_mentions_review.json": {**meta, "row_count": len(person_audit), "records": person_audit},
            "explicit_gender_evidence_audit.json": {**meta, "row_count": len(gender_audit), "records": gender_audit},
            "language_analysis_summary.json": {**meta, "row_count": len(metrics), "breakdowns": breakdown},
        }
        verified = []
        for name, payload in outputs.items():
            key = f"{base}/{name}"
            body = encode(payload)
            store.put(key, body)
            readback = store.get(key)
            parsed = json.loads(readback)
            if sha(readback) != sha(body):
                raise RuntimeError(f"Read-back hash mismatch: {key}")
            count = (parsed.get("row_count") if name == "language_analysis_summary.json"
                     else len(parsed.get("records", [])))
            if count != payload["row_count"]:
                raise RuntimeError(f"Read-back row count mismatch: {key} ({count} vs {payload['row_count']})")
            verified.append({"key": key, "sha256": sha(readback), "bytes": len(readback),
                             "row_count": count, "readback_verified": True})
        audit = {**meta, "output_objects": verified, "all_outputs_read_back_and_verified": True,
                 "posting_count": len(metrics), "description_count": sum(r["description_available"] for r in metrics),
                 "named_person_posting_count": breakdown["all_postings"]["postings_with_named_person_references"],
                 "explicit_masculine_posting_count": breakdown["all_postings"]["postings_with_masculine_references"],
                 "explicit_feminine_posting_count": breakdown["all_postings"]["postings_with_feminine_references"],
                 "gendered_posting_count": breakdown["all_postings"]["postings_with_any_gendered_reference"],
                 "manual_review_posting_count": breakdown["all_postings"]["manual_review_postings"]}
        audit_key = f"{base}/readback_verification.json"
        audit_bytes = encode(audit)
        store.put(audit_key, audit_bytes)
        audit_readback = store.get(audit_key)
        if sha(audit_readback) != sha(audit_bytes) or not json.loads(audit_readback).get("all_outputs_read_back_and_verified"):
            raise RuntimeError("Read-back verification audit failed.")
        result = {"source_key": input_key, "source_postings": len(postings), "outputs": verified,
                  "readback_verification_key": audit_key, "readback_verification_verified": True,
                  "summary": breakdown["all_postings"], "research_summary": breakdown["research_postings"],
                  "fellowship_summary": breakdown["fellowship_postings"],
                  "research_and_fellowship_summary": breakdown["research_and_fellowship"],
                  "date_evidence_class_summary": breakdown["date_evidence_class"]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        store.client.close()


if __name__ == "__main__":
    main()
