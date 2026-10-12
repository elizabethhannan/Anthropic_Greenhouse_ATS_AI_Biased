"""Data addendum: Elizabeth's October 11, 2026 captures, compared with the September 29 corpus.

OBSERVED MEASUREMENT — posting text and application forms; describes wording, not intent.

This is an addendum, NOT a re-run. Model 1's pre-registered results (outputs/model1_results.json)
stay as they are. This script:
  1. compares each captured posting with its latest version in the Model 1 corpus (word level,
     after removing page chrome and page-break repeats) and classifies it unchanged / changed / new;
  2. checks the named people on Fellows pages against the private list (aggregates only: names never
     leave outputs/private/);
  3. records, per application form, whether it carries the voluntary self-identification survey and
     which route applications take (Greenhouse or the Constellation partner form);
  4. scores the new Conceptual Reasoning Fellow posting with the Model 1 lexicon (raw and sense-filtered),
     for information only (it is not added to the pre-registered tests).

Inputs: captures/2026-10-11/ (PDFs, extracted text, manifest with SHA-256), the Model 1 corpus
(outputs/corpus/, git-ignored; rebuild with build_corpus.py) and outputs/private/named_people_gender.csv.
Outputs: outputs/captures_2026-10-11_update.json and .md.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures" / "2026-10-11"
CORPUS = HERE / "outputs" / "corpus"
PRIVATE = HERE / "outputs" / "private" / "named_people_gender.csv"
OUT = HERE / "outputs"
LABEL = "OBSERVED MEASUREMENT — posting text and application forms; describes wording, not intent"

# Model 1 version labels for the Sept 29 versions these captures update (private-file labels).
SEP29_LABEL = {
    "5183044008": "AI Safety & Security, combined (Sep 29)",
    "5183051008": "ML Systems & RL, combined (Sep 29)",
    "5183053008": "Economics & Policy, Anthropic Institute (Sep 29)",
}
KNOWN_FELLOWS_VERSIONS = 9          # Model 1 / findings note, as of 2026-10-08
KNOWN_NAMED_PEOPLE = 50

PAGE_CHROME = [
    r"back to jobs .*? apply ",                       # header line of the saved page
    r"create a job alert interested in building your career at anthropic get future opportunities sent straight to your email create alert",
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fix_pdf_glyphs(text: str) -> str:
    """Safari's PDF text layer drops ligatures to stray symbols ('o#ers', 'o$ce'). Restore the common ones."""
    text = re.sub(r"(?<=[A-Za-z])\$(?=[a-z])", "ffi", text)
    text = re.sub(r"(?<=[A-Za-z])[#!\"](?=[a-z])", "ff", text)
    text = re.sub(r"(?<=[A-Za-z])[#!](?![A-Za-z0-9])", "ff", text)   # word-final: 'sta#' -> 'staff'
    return text


def description(raw: str) -> str:
    """Posting text before the application form."""
    i = raw.find("Apply for this job")
    return raw[:i] if i >= 0 else raw


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fix_pdf_glyphs(text).lower())


def real_changes(old: str, new: str) -> tuple[float, list[dict]]:
    """Word-level diff; drops page chrome and chunks that merely repeat text found elsewhere (page breaks)."""
    a, b = words(old), words(new)
    bj = " ".join(b)
    for pat in PAGE_CHROME:
        bj = re.sub(pat, " ", bj)
    b = bj.split()
    # Saved-page header (title, Apply button, locations): drop everything before the posting's first words.
    head = a[:5]
    for k in range(min(len(b), 80)):
        if b[k:k + 5] == head:
            b = b[k:]
            break
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    grams = lambda w: {" ".join(w[i:i + 3]) for i in range(max(0, len(w) - 2))}
    ga, gb = grams(a), grams(b)

    def repeat(chunk: list[str], other: set) -> bool:
        """A chunk is a page-break repeat when nearly all its 3-word runs already occur on the other side."""
        g = grams(chunk)
        return bool(g) and sum(x in other for x in g) / len(g) >= 0.8

    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal" or max(i2 - i1, j2 - j1) < 3:
            continue
        removed, added = a[i1:i2], b[j1:j2]
        if op == "insert" and repeat(added, ga):
            continue
        if op == "delete" and repeat(removed, gb):
            continue
        if op == "replace" and repeat(added, ga) and (not removed or len(removed) <= 2):
            continue
        out.append({"op": op, "removed": " ".join(removed), "added": " ".join(added)})
    return sm.ratio(), out


def load_latest_versions() -> dict:
    latest = {}
    path = CORPUS / "corpus_versions.jsonl"
    if not path.exists():
        return latest
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        pid, cap = r["posting_id"], r.get("captured") or ""
        if pid not in latest or cap > latest[pid]["captured"]:
            latest[pid] = {"captured": cap, "text": r["text"], "title": r["title"]}
    return latest


def private_people() -> dict:
    by_version = {}
    if not PRIVATE.exists():
        return by_version
    with PRIVATE.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            by_version.setdefault(r["version"], set()).add(r["person"])
    return by_version


def name_found(name: str, text_words: str) -> bool:
    toks = re.findall(r"[a-z0-9]+", fix_pdf_glyphs(name).lower())
    return bool(toks) and (" " + " ".join(toks) + " ") in (" " + text_words + " ")


def redact(chunks: list[dict], people: set) -> list[dict]:
    """Never print a chunk that contains any token of a known person's name."""
    tokens = {t for p in people for t in re.findall(r"[a-z]+", p.lower()) if len(t) > 2}
    safe = []
    for c in chunks:
        joined = f" {c['removed']} {c['added']} "
        hit = any(f" {t} " in joined for t in tokens)
        safe.append({"op": c["op"], "removed": "[redacted]" if hit else c["removed"],
                     "added": "[redacted]" if hit else c["added"]})
    return safe


def form_facts(raw: str) -> dict:
    form = raw[raw.find("Apply for this job"):] if "Apply for this job" in raw else ""
    constellation = bool(re.search(r"managed by\s+Constellation", raw)) and \
        bool(re.search(r"do not need to submit this Greenhouse application", raw))
    return {
        "application_route": "Constellation partner form" if constellation else ("Greenhouse form" if form else "n/a"),
        "self_identification_survey": bool(re.search(r"Voluntary Self-Identification", form)),
        "survey_fields": [f for f in ("Gender", "Hispanic/Latino", "Race & Ethnicity", "Veteran Status")
                          if re.search(re.escape(f), form)] if re.search(r"Voluntary Self-Identification", form) else [],
        "ai_policy_question": bool(re.search(r"AI Policy for Application", form)),
        "names_people": None,   # filled for Fellows pages from the private list
    }


def lexicon_scores(raw: str) -> dict:
    """Model 1 scoring of a captured posting: boilerplate sentences removed as in build_corpus."""
    import build_corpus as bc
    from lexicon import load_lexicon, score_text
    text = fix_pdf_glyphs(description(raw))
    i = text.find("About Anthropic")
    text = text[i:] if i >= 0 else text
    text = bc.normalize_ws(text)
    removed = set()
    bp = CORPUS / "boilerplate_removed.csv"
    if bp.exists():
        with bp.open(newline="", encoding="utf-8") as fh:
            removed = {bc.sentence_key(r["sentence"]) for r in csv.DictReader(fh)}
    clean = bc.remove_sentences(text, removed)
    res = json.loads((OUT / "model1_results.json").read_text(encoding="utf-8"))
    dropped = frozenset(res["wording"]["sense_audit"]["dropped_stems"])
    lex = load_lexicon()
    raw_s, sf_s = score_text(clean, lex), score_text(clean, lex, drop_stems=dropped)
    return {"n_words_clean": raw_s.n_words,
            "raw": {"masc_per_1k": round(raw_s.masc_per_1k, 2), "fem_per_1k": round(raw_s.fem_per_1k, 2),
                    "label": raw_s.decoder_label},
            "sense_filtered": {"masc_per_1k": round(sf_s.masc_per_1k, 2), "fem_per_1k": round(sf_s.fem_per_1k, 2),
                               "label": sf_s.decoder_label}}


def main() -> dict:
    manifest = json.loads((CAP / "manifest.json").read_text(encoding="utf-8"))
    for f in manifest["files"]:
        if sha256(CAP / f["file"]) != f["sha256_pdf"] or sha256(CAP / f["text_file"]) != f["sha256_text"]:
            raise RuntimeError(f"checksum mismatch: {f['file']}")
    latest = load_latest_versions()
    people = private_people()
    all_people = set().union(*people.values()) if people else set()

    postings, new_versions, new_postings = [], 0, 0
    for f in manifest["files"]:
        title = f["title"]
        if title.startswith(("Job board listing", "Introducing")):
            continue
        raw = (CAP / f["text_file"]).read_text(encoding="utf-8")
        entry = {"title": title, "posting_id": f["posting_id"], "pdf_created": f["pdf_created"],
                 "fellows": "fellow" in title.lower(), **form_facts(raw)}
        prev = latest.get(f["posting_id"]) if f["posting_id"] else None
        if prev is None:
            entry["status"] = "new posting (not in the Sept 29 corpus)"
            new_postings += 1
            entry["changes"] = []
        else:
            ratio, ch = real_changes(prev["text"], description(raw))
            entry["compared_with"] = prev["captured"]
            entry["similarity"] = round(ratio, 3)
            entry["status"] = "changed (new version)" if ch else "unchanged"
            entry["changes"] = redact(ch, all_people)
            new_versions += bool(ch)
        if entry["fellows"]:
            tw = " ".join(words(description(raw)))
            if f["posting_id"] in SEP29_LABEL and people:
                expected = people.get(SEP29_LABEL[f["posting_id"]], set())
                found = {p for p in expected if name_found(p, tw)}
                entry["names_people"] = len(found) > 0
                entry["named_people_found"] = len(found)
                entry["named_people_in_sep29_version"] = len(expected)
            else:
                entry["names_people"] = any(name_found(p, tw) for p in all_people)
                entry["named_people_found"] = sum(name_found(p, tw) for p in all_people)
            if entry["status"].startswith("new"):
                entry["lexicon"] = lexicon_scores(raw)
        else:
            entry["names_people"] = any(name_found(p, " ".join(words(description(raw)))) for p in all_people)
        postings.append(entry)

    fellows_new_versions = sum(1 for p in postings if p["fellows"] and p["status"].startswith(("changed", "new")))
    result = {
        "label": LABEL,
        "addendum_to": "outputs/model1_results.json (pre-registered results are not re-run)",
        "capture_date": manifest["capture_date"],
        "files": [{"file": f["file"], "title": f["title"], "pdf_created": f["pdf_created"],
                   "sha256_pdf": f["sha256_pdf"]} for f in manifest["files"]],
        "postings": postings,
        "summary": {
            "postings_compared": len(postings),
            "unchanged": sum(p["status"] == "unchanged" for p in postings),
            "changed_new_version": new_versions,
            "new_postings": new_postings,
            "fellows_posting_versions_before": KNOWN_FELLOWS_VERSIONS,
            "fellows_posting_versions_after": KNOWN_FELLOWS_VERSIONS + fellows_new_versions,
            "distinct_named_people_before": KNOWN_NAMED_PEOPLE,
            "new_named_people": 0 if not any(c["added"] == "[redacted]" or c["removed"] == "[redacted]"
                                             for p in postings for c in p["changes"]) else None,
            "new_named_people_note": ("No changed text contains a name; the one new posting (Conceptual Reasoning "
                                      "Fellow) was read in full and names no one."),
            "non_fellows_postings_naming_people": sum(1 for p in postings if not p["fellows"] and p["names_people"]),
            "forms_with_self_identification_survey": [p["title"] for p in postings if p["self_identification_survey"]],
            "forms_without_self_identification_survey": [p["title"] for p in postings
                                                         if not p["self_identification_survey"]],
            "constellation_route": [p["title"] for p in postings
                                    if p["application_route"] == "Constellation partner form"],
            "corpus_available": bool(latest), "private_list_available": bool(people),
        },
    }
    (OUT / "captures_2026-10-11_update.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                                          encoding="utf-8")
    write_md(result)
    return result


def write_md(r: dict) -> None:
    s = r["summary"]
    rows = []
    for p in r["postings"]:
        ch = "; ".join(f"\"{c['removed']}\" → \"{c['added']}\"" for c in p["changes"]) or "—"
        named = (f"{p['named_people_found']} of {p['named_people_in_sep29_version']}"
                 if "named_people_in_sep29_version" in p else ("yes" if p["names_people"] else "none"))
        rows.append(f"| {p['title']} | {p['status']} | {ch} | {named} | {p['application_route']} | "
                    f"{'yes' if p['self_identification_survey'] else 'no'} |")
    cr = next((p for p in r["postings"] if p.get("lexicon")), None)
    lex = ""
    if cr:
        L = cr["lexicon"]
        lex = (f"\n## New posting scored with the Model 1 lexicon (information only)\n\n"
               f"{cr['title']} ({L['n_words_clean']} words after boilerplate removal): raw {L['raw']['masc_per_1k']} masculine-coded and {L['raw']['fem_per_1k']} "
               f"feminine-coded words per 1,000 ({L['raw']['label']}); sense-filtered "
               f"{L['sense_filtered']['masc_per_1k']} and {L['sense_filtered']['fem_per_1k']} "
               f"({L['sense_filtered']['label']}). Approximate: PDF line breaks can keep some shared boilerplate sentences that the corpus removes. Not added to the pre-registered tests.\n")
    md = f"""# Model 1 data addendum: captures of October 11, 2026

**{r['label']}.** Addendum to `model1_results.json`; the pre-registered results are not re-run. Sources: `captures/2026-10-11/` (PDFs saved by Elizabeth Hannan, text extracted with pdftotext, SHA-256 in `manifest.json`), compared with the latest version of each posting in the Model 1 corpus (September 29, 2026).

## Summary

- Postings compared: {s['postings_compared']} — unchanged {s['unchanged']}, changed (new version) {s['changed_new_version']}, new {s['new_postings']}.
- Fellows posting versions: {s['fellows_posting_versions_before']} → {s['fellows_posting_versions_after']}. Distinct named people: {s['distinct_named_people_before']}, no new names (every Fellows page names the same people as its September 29 version).
- Non-Fellows postings naming people: {s['non_fellows_postings_naming_people']}. The new Conceptual Reasoning Fellow page names no one.
- Application route: {', '.join(s['constellation_route']) or 'none'} → Constellation partner form; all others → Greenhouse form.
- Voluntary self-identification survey (gender, Hispanic/Latino, race and ethnicity, veteran status, "for government reporting purposes"): present on {len(s['forms_with_self_identification_survey'])} forms ({'; '.join(s['forms_with_self_identification_survey'])}); absent on {len(s['forms_without_self_identification_survey'])} ({'; '.join(s['forms_without_self_identification_survey'])}). The Constellation form itself was not captured. This describes the forms only, not how any data is stored or used.

## By posting

| Posting | Status vs. Sept 29 | Real text change | Named people incl. past-project credits (found / Sept 29) | Application route | Self-ID survey on form |
|---|---|---|---|---|---|
""" + "\n".join(rows) + "\n" + lex + """
## Method

- Word-level comparison after restoring dropped ligatures (for example "o#ers" → "offers"), removing the saved page's header and job-alert lines, and ignoring chunks that repeat text found elsewhere on the page (page-break duplicates). A chunk of three or more words that remains is a real change.
- Named people are matched against the private list by full name; only counts leave the private folder, and any change chunk containing a name token is redacted.

## APA 7

Anthropic. (2026). *Job postings and application forms* [Greenhouse job board; captures by E. Hannan, October 11, 2026]. Greenhouse. https://job-boards.greenhouse.io/anthropic
"""
    (OUT / "captures_2026-10-11_update.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    res = main()
    print(json.dumps(res["summary"], indent=2, ensure_ascii=False))
    for p in res["postings"]:
        print(p["title"], "|", p["status"], "|", p["changes"], "|", p.get("named_people_found"), "/",
              p.get("named_people_in_sep29_version"), "|", p["application_route"], "| selfID", p["self_identification_survey"])
