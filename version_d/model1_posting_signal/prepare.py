"""Model 1, stage A (after the plan was approved): raw scores and labeling samples.

Reads outputs/corpus/ (built by build_corpus.py), assigns role families,
scores every record with the raw lexicon, and draws the two labeling samples:
  labels/sense_audit_sample.csv     200 keyword-in-context matches (<= 10 per stem, spread across families)
  labels/convergent_sample.csv      300 sentences, stratified by family (rater sees text only)
Seed 20261011. The samples are drawn before any label exists.
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_corpus import split_sentences  # noqa: E402
from lexicon import keyword_in_context, load_lexicon, score_text, tokenize  # noqa: E402
from role_family import FAMILIES, assign_family  # noqa: E402

CFG = yaml.safe_load((HERE / "config.yaml").read_text())
CORPUS = HERE / "outputs" / "corpus"
LABELS = HERE / "labels"


def load(name):
    return [json.loads(line) for line in (CORPUS / f"corpus_{name}.jsonl").read_text(encoding="utf-8").splitlines()]


def score_records(recs):
    lex = load_lexicon()
    out = []
    for r in recs:
        if r["excluded_short"]:
            continue
        s = score_text(r["text_clean"], lex)
        out.append({
            "posting_id": r["posting_id"], "title": r["title"], "family": assign_family(r["title"]),
            "captured": r["captured"], "posted": r["posted"], "source_file": r["source_file"],
            "text_sha256": r["text_sha256"], "n_words": s.n_words, "masc": s.masc, "fem": s.fem,
            "masc_per_1k": s.masc_per_1k, "fem_per_1k": s.fem_per_1k, "net_per_1k": s.net_per_1k,
            "decoder_label": s.decoder_label,
            "masc_stems": ";".join(s.masc_stems), "fem_stems": ";".join(s.fem_stems),
        })
    return out


def sense_sample(primary, rng, n=200, per_stem=10):
    lex = load_lexicon()
    by_stem = defaultdict(lambda: defaultdict(list))
    for r in primary:
        if r["excluded_short"]:
            continue
        fam = assign_family(r["title"])
        for lname, stem, tok, ctx in keyword_in_context(r["text_clean"], lex):
            by_stem[(lname, stem)][fam].append({"posting_id": r["posting_id"], "family": fam, "list": lname,
                                                "stem": stem, "token": tok, "context": ctx})
    picked = []
    for key in sorted(by_stem):
        fams = by_stem[key]
        pools = {f: rng.sample(v, len(v)) for f, v in sorted(fams.items())}
        take = []
        while len(take) < per_stem and any(pools.values()):
            for f in FAMILIES:  # round-robin across families
                if pools.get(f) and len(take) < per_stem:
                    take.append(pools[f].pop())
        picked.extend(take)
    total_available = len(picked)
    if len(picked) > n:
        # keep stems balanced: trim the largest stem groups one at a time
        groups = defaultdict(list)
        for p in picked:
            groups[(p["list"], p["stem"])].append(p)
        while sum(len(g) for g in groups.values()) > n:
            k = max(sorted(groups), key=lambda x: len(groups[x]))
            groups[k].pop()
        picked = [p for k in sorted(groups) for p in groups[k]]
    rng.shuffle(picked)
    for i, p in enumerate(picked, 1):
        p["item"] = f"S{i:03d}"
    return picked, total_available, {f"{k[0]}:{k[1]}": sum(len(v) for v in by_stem[k].values()) for k in sorted(by_stem)}


def convergent_sample(primary, rng, n=300, min_tokens=4):
    by_fam = defaultdict(list)
    for r in primary:
        if r["excluded_short"]:
            continue
        fam = assign_family(r["title"])
        for s in split_sentences(r["text_clean"]):
            s = re.sub(r"^[\-•*•\s]+", "", s).strip()
            if len(tokenize(s)) >= min_tokens:
                by_fam[fam].append({"posting_id": r["posting_id"], "family": fam, "sentence": s})
    per = n // len(FAMILIES)
    picked = []
    for f in FAMILIES:
        pool = sorted({(x["posting_id"], x["sentence"]): x for x in by_fam[f]}.values(),
                      key=lambda x: (x["posting_id"], x["sentence"]))
        picked.extend(rng.sample(pool, min(per, len(pool))))
    rng.shuffle(picked)
    for i, p in enumerate(picked, 1):
        p["item"] = f"C{i:03d}"
    return picked, {f: len(v) for f, v in by_fam.items()}


def write_csv(path, rows, cols):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    primary, versions = load("primary"), load("versions")
    out = HERE / "outputs"
    raw_primary = score_records(primary)
    raw_versions = score_records(versions)
    cols = list(raw_primary[0].keys())
    write_csv(out / "scores_primary_raw.csv", raw_primary, cols)
    write_csv(out / "scores_versions_raw.csv", raw_versions, cols)
    rng = random.Random(CFG["seed"])
    sense, avail, stem_counts = sense_sample(primary, rng, CFG["sense_audit"]["sample_size"],
                                             CFG["sense_audit"]["max_per_stem"])
    write_csv(LABELS / "sense_audit_sample.csv", sense,
              ["item", "posting_id", "family", "list", "stem", "token", "context"])
    conv, sent_counts = convergent_sample(primary, random.Random(CFG["seed"] + 1), CFG["convergent_check"]["sentences"])
    write_csv(LABELS / "convergent_sample.csv", conv, ["item", "posting_id", "family", "sentence"])
    meta = {"scored_primary": len(raw_primary), "scored_versions": len(raw_versions),
            "sense_sample": len(sense), "sense_candidates_after_cap": avail,
            "matches_by_stem": stem_counts, "convergent_sample": len(conv),
            "eligible_sentences_by_family": sent_counts}
    (out / "prepare_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k != "matches_by_stem"}, indent=2))
    print("stems matched:", len(stem_counts))


if __name__ == "__main__":
    main()
