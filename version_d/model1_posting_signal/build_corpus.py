"""Step 1: build the posting corpus from captured posting versions.

Reads every captured posting version from a local file (never from fresh web
scraping, never from memory). Accepted inputs:
  * Version C master JSON: {"records": [...]} with greenhouse_job_id, exact_title,
    departments, offices, first_published_at / posting_date_if_known,
    archive_capture_date, description_text / description_html
  * JSONL or CSV with equivalent columns (see FIELD_ALIASES)

Steps: strip HTML; normalize whitespace; hash texts and drop exact duplicates;
keep the latest captured version per posting ID for primary tests (all distinct
versions kept for sensitivity); remove sentences that appear in >= 50% of
primary records; exclude records under 150 words after removal.

Usage:
    python build_corpus.py --input PATH [--input PATH ...] --out outputs/corpus
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html as htmllib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lexicon import tokenize  # noqa: E402

FIELD_ALIASES = {
    "posting_id": ["greenhouse_job_id", "job_id", "posting_id", "id", "dedup_key", "absolute_url"],
    "title": ["exact_title", "title", "job_title"],
    "department": ["departments", "department"],
    "location": ["offices", "location", "locations"],
    "posted": ["first_published_at", "posting_date_if_known", "posted_date", "posting_date"],
    "captured": ["archive_capture_date", "capture_date", "captured_at", "retrieved_at", "updated_at"],
    "text": ["description_text", "text", "content_text", "plain_text"],
    "html": ["description_html", "content", "html"],
    "source": ["source", "source_url", "absolute_url"],
}

BLOCK_TAGS = re.compile(r"(?i)</?(p|div|li|ul|ol|br|h[1-6]|tr|td|section|article)\b[^>]*>")
ANY_TAG = re.compile(r"<[^>]+>")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"(])|\n+")


def _flat(v) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        return " ".join(_flat(x) for x in v.values())
    if isinstance(v, list):
        return "; ".join(_flat(x) for x in v)
    return str(v)


MISSING = (None, "", "None", "none", "null", "NULL")


def pick(rec: dict, key: str):
    for a in FIELD_ALIASES[key]:
        if a in rec and not (isinstance(rec[a], str) and rec[a].strip() in MISSING) and rec[a] is not None:
            return rec[a]
    return None


def strip_html(markup: str) -> str:
    t = htmllib.unescape(markup or "")
    t = BLOCK_TAGS.sub("\n", t)
    t = ANY_TAG.sub(" ", t)
    return htmllib.unescape(t)


def normalize_ws(text: str) -> str:
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text) if s and s.strip()]


def sentence_key(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def text_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()


def load_records(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if path.suffix == ".csv":
        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["records"] if isinstance(data, dict) and "records" in data else data


def normalize_record(rec: dict, source_file: str) -> dict | None:
    text = pick(rec, "text")
    if text is None and pick(rec, "html") is not None:
        text = strip_html(str(pick(rec, "html")))
    elif text is not None and "<" in str(text) and ">" in str(text):
        text = strip_html(str(text))
    if not text:
        return None
    text = normalize_ws(str(text))
    pid = pick(rec, "posting_id")
    sha = text_hash(text)
    return {
        # A record with no recognized ID gets a stable, unique fallback from its text hash, so unrelated
        # ID-less records are never merged as versions of one posting.
        "posting_id": str(pid) if pid is not None else f"noid:{sha[:16]}",
        "posting_id_fallback": pid is None,
        "title": _flat(pick(rec, "title")).strip(),
        "department": _flat(pick(rec, "department")),
        "location": _flat(pick(rec, "location")),
        "posted": str(pick(rec, "posted") or "")[:10],
        "captured": str(pick(rec, "captured") or "")[:10],
        "version_c_classification": rec.get("posting_classification"),
        "source_file": source_file,
        "text": text,
        "text_sha256": sha,
    }


def dedupe(records: list[dict]) -> tuple[list[dict], int]:
    """Drop exact duplicates: same posting ID and identical normalized text.
    Identical text under a different posting ID is kept (a distinct posting record)."""
    seen, out = set(), []
    for r in records:
        key = (r["posting_id"], r["text_sha256"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out, len(records) - len(out)


def latest_per_posting(versions: list[dict]) -> list[dict]:
    best = {}
    for r in versions:
        cur = best.get(r["posting_id"])
        stamp = (r["captured"] or r["posted"] or "", r["text_sha256"])
        if cur is None or stamp > (cur["captured"] or cur["posted"] or "", cur["text_sha256"]):
            best[r["posting_id"]] = r
    return sorted(best.values(), key=lambda r: r["posting_id"])


def boilerplate(records: list[dict], share: float) -> tuple[set, list[dict]]:
    """Sentences appearing in >= share of records (document frequency)."""
    df = Counter()
    for r in records:
        df.update({sentence_key(s) for s in split_sentences(r["text"])})
    n = len(records)
    cut = share * n
    removed = {k for k, c in df.items() if c >= cut}
    table = [{"sentence": k, "records": c, "share": round(c / n, 4)} for k, c in df.most_common() if k in removed]
    return removed, table


def remove_sentences(text: str, removed: set) -> str:
    keep = [s for s in split_sentences(text) if sentence_key(s) not in removed]
    return "\n".join(keep)


def build(inputs: list[Path], share: float = 0.50, min_words: int = 150) -> dict:
    raw = []
    for p in inputs:
        for rec in load_records(p):
            r = normalize_record(rec, p.name)
            if r:
                raw.append(r)
    versions, exact_dupes = dedupe(raw)
    primary = latest_per_posting(versions)
    removed, removed_table = boilerplate(primary, share)
    words_before = words_after = 0
    for coll in (primary, versions):
        for r in coll:
            r["text_clean"] = remove_sentences(r["text"], removed)
            r["n_words_raw"] = len(tokenize(r["text"]))
            r["n_words_clean"] = len(tokenize(r["text_clean"]))
            r["excluded_short"] = r["n_words_clean"] < min_words
    for r in primary:
        words_before += r["n_words_raw"]
        words_after += r["n_words_clean"]
    return {
        "versions": versions,
        "primary": primary,
        "removed_sentences": removed_table,
        "counts": {
            "records_loaded": len(raw),
            "exact_duplicates_dropped": exact_dupes,
            "records_without_posting_id": sum(r["posting_id_fallback"] for r in raw),
            "distinct_versions": len(versions),
            "postings_primary": len(primary),
            "excluded_short": sum(r["excluded_short"] for r in primary),
            "records_scored": sum(not r["excluded_short"] for r in primary),
            "boilerplate_word_share_removed": round(1 - words_after / words_before, 4) if words_before else None,
        },
    }


def write(result: dict, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for name in ("versions", "primary"):
        with open(outdir / f"corpus_{name}.jsonl", "w", encoding="utf-8") as fh:
            for r in result[name]:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(outdir / "boilerplate_removed.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["sentence", "records", "share"])
        w.writeheader()
        w.writerows(result["removed_sentences"])
    (outdir / "corpus_counts.json").write_text(json.dumps(result["counts"], indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=HERE / "outputs" / "corpus")
    a = ap.parse_args()
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())
    res = build(a.input, cfg["corpus"]["boilerplate_share"], cfg["corpus"]["min_words_after_removal"])
    write(res, a.out)
    print(json.dumps(res["counts"], indent=2))
