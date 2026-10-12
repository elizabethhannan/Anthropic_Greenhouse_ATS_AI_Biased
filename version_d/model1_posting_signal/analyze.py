"""Model 1, stage B: sense audit, convergent check, T7 tests, T6 visibility, H3 gate,
Model 1b, and the results file.

Run after prepare.py, after the two label files exist (labels/), and after
outputs/private/named_people_gender.csv has been built. Seed 20261011.

OBSERVED MEASUREMENT — posting text; describes wording, not intent.
Writes aggregates only to public outputs; names never leave outputs/private/.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import cohen_kappa_score, confusion_matrix

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bias_tests as bt  # noqa: E402
import model1b_estimator as m1b  # noqa: E402
import outcome_link as ol  # noqa: E402
import visibility as vis  # noqa: E402
from lexicon import load_lexicon, score_text, sentence_label  # noqa: E402
from role_family import FAMILIES, assign_family  # noqa: E402

CFG = yaml.safe_load((HERE / "config.yaml").read_text())
OUT = HERE / "outputs"
LABELS = HERE / "labels"
PRIV = OUT / "private"
SEED = CFG["seed"]
D = 4


def r4(x):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [r4(v) for v in x]
    x = float(x)
    return None if np.isnan(x) else round(x, D) + 0.0


def load_jsonl(name):
    return [json.loads(line) for line in (OUT / "corpus" / f"corpus_{name}.jsonl").read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------- sense audit
def sense_audit():
    sample = pd.read_csv(LABELS / "sense_audit_sample.csv", dtype=str)
    labels = pd.read_csv(LABELS / "sense_audit_labels.csv", dtype=str)
    m = sample.merge(labels, on="item", how="left", validate="one_to_one")
    if m["label"].isna().any():
        raise ValueError("unlabeled sense-audit items")
    m["trait"] = (m["label"].str.strip() == "trait").astype(int)
    by = (m.groupby(["list", "stem"]).agg(n=("trait", "size"), trait=("trait", "sum")).reset_index())
    by["precision"] = by["trait"] / by["n"]
    thr = CFG["sense_audit"]["drop_if_precision_below"]
    dropped = sorted(by.loc[by["precision"] < thr, "stem"].tolist())
    return {
        "sampled": int(len(m)), "overall_precision": float(m["trait"].mean()),
        "dropped_stems": dropped,
        "precision_by_stem": [{"stem": r.stem, "list": r.list, "n": int(r.n), "trait": int(r.trait),
                               "precision": float(r.precision)} for r in by.sort_values(["list", "stem"]).itertuples()],
        "by_family": {f: float(g["trait"].mean()) for f, g in m.groupby("family")},
    }, frozenset(dropped)


# ---------------------------------------------------------------- scoring
def score(records, drop=frozenset()):
    lex = load_lexicon()
    rows = []
    for r in records:
        if r["excluded_short"]:
            continue
        s = score_text(r["text_clean"], lex, drop)
        rows.append({"posting_id": r["posting_id"], "title": r["title"], "family": assign_family(r["title"]),
                     "captured": r["captured"], "n_words": s.n_words, "masc_per_1k": s.masc_per_1k,
                     "fem_per_1k": s.fem_per_1k, "net_per_1k": s.net_per_1k, "decoder_label": s.decoder_label})
    return pd.DataFrame(rows)


def family_stats(df, rng):
    out = []
    for f in FAMILIES:
        g = df[df.family == f]
        row = {"family": f, "n": int(len(g))}
        for mtr in ("masc_per_1k", "fem_per_1k", "net_per_1k"):
            x = g[mtr].to_numpy(float)
            lo, hi = bt.bootstrap_mean_ci(x, CFG["bias_tests"]["bootstrap"], rng)
            row[mtr] = {"mean": r4(x.mean()), "ci": [r4(lo), r4(hi)]}
        row["decoder_labels"] = {k: int(v) for k, v in g["decoder_label"].value_counts().sort_index().items()}
        out.append(row)
    return out


# ---------------------------------------------------------------- convergent check
def convergent(drop):
    sample = pd.read_csv(LABELS / "convergent_sample.csv", dtype=str)
    labels = pd.read_csv(LABELS / "convergent_labels.csv", dtype=str)
    m = sample.merge(labels, on="item", how="left", validate="one_to_one")
    if m["label"].isna().any():
        raise ValueError("unlabeled convergent items")
    lex = load_lexicon()
    cats = ["agentic", "communal", "neutral"]
    res = {}
    for variant, dset in (("raw", frozenset()), ("sense_filtered", drop)):
        lexl = [sentence_label(s, lex, dset) for s in m["sentence"]]
        human = m["label"].str.strip().tolist()
        k = cohen_kappa_score(human, lexl, labels=cats)
        cm = confusion_matrix(human, lexl, labels=cats)
        res[variant] = {"kappa": float(k), "agreement": float(np.mean(np.array(human) == np.array(lexl))),
                        "confusion_matrix": {"rows_rater": cats, "cols_lexicon": cats, "counts": cm.tolist()},
                        "rater_counts": {c: human.count(c) for c in cats},
                        "lexicon_counts": {c: lexl.count(c) for c in cats}}
    thr = CFG["convergent_check"]["weak_validity_kappa"]
    # bootstrap 95% CI for kappa (resampling sentences), seed fixed
    rng = np.random.default_rng(SEED + 7)
    human = np.array(m["label"].str.strip().tolist())
    lexraw = np.array([sentence_label(s, lex, frozenset()) for s in m["sentence"]])
    ks = []
    for _ in range(2000):
        idx = rng.integers(0, len(human), len(human))
        ks.append(cohen_kappa_score(human[idx], lexraw[idx], labels=cats))
    res["raw"]["kappa_ci"] = [float(np.percentile(ks, 2.5)), float(np.percentile(ks, 97.5))]
    return {"sentences": int(len(m)), "kappa": res["raw"]["kappa"], "weakly_valid_flag": res["raw"]["kappa"] < thr,
            "threshold": thr, "variants": res, "rater": "Claude subagent, blind to lexicon labels, rubric v1"}


# ---------------------------------------------------------------- T7c
PAIRS = [
    ("AI Safety Fellow (Apr 3) → AI Safety & Security, combined (Sep 29)", "5023394008", "5183044008"),
    ("AI Security Fellow (Apr 2) → AI Safety & Security, combined (Sep 29)", "5030244008", "5183044008"),
    ("ML Systems & Performance (Apr 15) → ML Systems & RL, combined (Sep 29)", "5183051008@2026-04-15", "5183051008@2026-09-29"),
]


def t7c(versions_raw):
    v = versions_raw[versions_raw.family == "Fellows"].copy()
    v["key"] = v["posting_id"] + "@" + v["captured"]
    rows = []
    for label, a, b in PAIRS:
        def get(k):
            sel = v[v.key == k] if "@" in k else v[v.posting_id == k].sort_values("captured").tail(1)
            return sel.iloc[0] if len(sel) else None
        ra, rb = get(a), get(b)
        if ra is None or rb is None:
            rows.append({"change": label, "computed": False, "reason": "version not in corpus"})
            continue
        rows.append({"change": label, "computed": True,
                     "from": {"captured": ra.captured, "masc_per_1k": r4(ra.masc_per_1k), "fem_per_1k": r4(ra.fem_per_1k)},
                     "to": {"captured": rb.captured, "masc_per_1k": r4(rb.masc_per_1k), "fem_per_1k": r4(rb.fem_per_1k)},
                     "delta_masc_per_1k": r4(rb.masc_per_1k - ra.masc_per_1k),
                     "delta_fem_per_1k": r4(rb.fem_per_1k - ra.fem_per_1k)})
    rows.append({"change": "Economics (Apr 26 capture) → Economics & Policy, Anthropic Institute (Jun 7 / Sep 29)",
                 "computed": False,
                 "reason": "The April 26 capture is an image-only PDF; its OCR text was not provided, so wording "
                           "was not scored. Named-people change (2 → 5 listed mentors) is reported under T6."})
    fel = v.sort_values(["captured", "posting_id"])
    table = [{"posting_id": r.posting_id, "title": r.title, "captured": r.captured, "n_words": int(r.n_words),
              "masc_per_1k": r4(r.masc_per_1k), "fem_per_1k": r4(r.fem_per_1k)} for r in fel.itertuples()]
    return {"pairs": rows, "fellows_versions_scored": table}


# ---------------------------------------------------------------- T6
def t6():
    rows = vis.load_private(PRIV / "named_people_gender.csv")
    a = vis.analyze(rows, CFG["visibility"]["fellows_hires"]["women"], CFG["visibility"]["fellows_hires"]["known"],
                    CFG["visibility"]["parity"])
    srcs = {}
    for r in rows:
        srcs.setdefault(r["person"], r)
    src_types = {}
    priv_json = {}
    import glob
    for f in sorted(glob.glob(str(PRIV / "gender_batch_*.json"))):
        for r in json.loads(Path(f).read_text(encoding="utf-8")):
            priv_json[r["person"]] = r
    for p, r in priv_json.items():
        if r["code"] != "unknown":
            src_types[r.get("source_type", "")] = src_types.get(r.get("source_type", ""), 0) + 1
    a["source_types_for_known_codes"] = dict(sorted(src_types.items()))
    a["versions_naming_people"] = len({r["version"] for r in rows})
    a["fellows_versions"] = CFG["visibility"]["fellows_versions"]
    if a["versions_naming_people"] < a["fellows_versions"]:
        # the STEM Fellow version (Apr 18) names no one; keep it visible as a zero row
        a["by_version"].append({"version": "STEM Fellow (Apr 18)", "named": 0, "women": 0, "men": 0, "unknown": 0})
    a["mentor_listings"] = sum(r["role"] == "mentor" for r in rows)
    a["credit_listings"] = sum(r["role"] == "credit" for r in rows)
    a["safety_security_versions_named"] = None
    return a, rows


def main(write=True, run_date=None):
    rng = np.random.default_rng(SEED)
    primary, versions = load_jsonl("primary"), load_jsonl("versions")
    counts = json.loads((OUT / "corpus" / "corpus_counts.json").read_text())
    audit, drop = sense_audit()
    raw = score(primary)
    filt = score(primary, drop)
    vraw = score(versions)
    stats_raw = family_stats(raw, rng)
    stats_filt = family_stats(filt, rng)
    scores = {v: {mtr: {f: d[d.family == f][mtr].to_numpy(float) for f in FAMILIES}
                  for mtr in ("masc_per_1k", "fem_per_1k")} for v, d in (("raw", raw), ("sense_filtered", filt))}
    tests = bt.family_comparisons(scores, FAMILIES, CFG["bias_tests"]["reference_family"],
                                  ["masc_per_1k", "fem_per_1k"], ["raw", "sense_filtered"],
                                  CFG["bias_tests"]["permutations"], CFG["bias_tests"]["bootstrap"], SEED)
    conv = convergent(drop)
    change = t7c(vraw)
    vis_res, vis_rows = t6()
    gate = ol.run(CFG)
    est = m1b.validate(CFG)
    removed = list(csv.DictReader(open(OUT / "corpus" / "boilerplate_removed.csv", encoding="utf-8")))

    core = {
        "label": CFG["label"],
        "run_date": run_date or dt.date.today().isoformat(),
        "corpus": {
            "records_total": counts["records_loaded"], "distinct_versions": counts["distinct_versions"],
            "exact_duplicates_dropped": counts["exact_duplicates_dropped"],
            "postings_primary": counts["postings_primary"],
            "records_scored": counts["records_scored"], "excluded_short": counts["excluded_short"],
            "boilerplate_word_share_removed": counts["boilerplate_word_share_removed"],
            "boilerplate_sentences_removed": len(removed),
            "wordlist_source": f"gender-decoder@{CFG['wordlist']['commit']}",
            "sources": ["Greenhouse current snapshot 2026-09-29 (629 records)",
                        "Historical Greenhouse deduplicated 20260929T074631Z (1,246 records; 704 with text)",
                        "Recovered archive pages 20260930T024433Z (932 records; 930 with text)"],
            "families": [{"family": s["family"], "n": s["n"]} for s in stats_raw],
            "role_family_rule": "Title rules in order: Fellow → Research → Engineer|Developer|Software|Infrastructure|Reliability → Other",
        },
        "wording": {
            "by_family": stats_raw,
            "by_family_sense_filtered": stats_filt,
            "tests": [{**t, "diff": r4(t["diff"]), "ci": r4(t["ci"]), "p_perm": r4(t["p_perm"]),
                       "p_holm": r4(t["p_holm"]), "cliffs_delta": r4(t["cliffs_delta"])} for t in tests],
            "sense_audit": {**audit, "overall_precision": r4(audit["overall_precision"]),
                            "overall_precision_ci": r4(vis.wilson(round(audit["overall_precision"] * audit["sampled"]),
                                                                  audit["sampled"])),
                            "stems_audited": len(audit["precision_by_stem"]),
                            "precision_by_stem": [{**p, "precision": r4(p["precision"])} for p in audit["precision_by_stem"]],
                            "by_family": {k: r4(v) for k, v in audit["by_family"].items()}},
            "convergent_check": {**conv, "kappa": r4(conv["kappa"]),
                                 "kappa_ci": r4(conv["variants"]["raw"]["kappa_ci"]),
                                 "variants": {k: {**v, "kappa": r4(v["kappa"]), "agreement": r4(v["agreement"]),
                                                  **({"kappa_ci": r4(v["kappa_ci"])} if "kappa_ci" in v else {})}
                                              for k, v in conv["variants"].items()}},
            "change_over_time": change,
        },
        "visibility": {
            "fellows_versions": vis_res["fellows_versions"], "versions_naming_people": vis_res["versions_naming_people"],
            "named_people": vis_res["named_people"],
            "mentor_listings": vis_res["mentor_listings"], "credit_listings": vis_res["credit_listings"],
            "coded": vis_res["coded"],
            "women_share_known": {"value": r4(vis_res["women_share_known"]["value"]),
                                  "ci": r4(vis_res["women_share_known"]["ci"]),
                                  "bounds": r4(vis_res["women_share_known"]["bounds"])},
            "listing_weighted_women_share": r4(vis_res["listing_weighted_women_share"]),
            "listings": vis_res["listings"],
            "by_version": vis_res["by_version"],
            "mentors_vs_credits": vis_res["mentors_vs_credits"],
            "comparisons": [{**c, "p": float(f"{c['p']:.3g}")} for c in vis_res["comparisons"]],
            "listing_weighted_ci_descriptive": r4(vis.wilson(vis_res["listings"]["women"],
                                                             vis_res["listings"]["women"] + vis_res["listings"]["men"])),
            "coding_rule": "Public self-identification only (pronouns or explicit self-description in an official bio, "
                           "personal site or profile, or published interview); never inferred from names, photos or voice.",
            "source_types_for_known_codes": vis_res["source_types_for_known_codes"],
        },
        "outcome_link": {k: gate[k] for k in ("estimable", "rule", "cells", "reason", "estimates", "notes")},
        "model1b": {"status": "estimator built; validated on simulated data; awaiting internal applicant data",
                    "coverage_in_simulation": r4(est["coverage_in_simulation"]),
                    "coverage_ci": r4(vis.wilson(round(est["coverage_in_simulation"] * est["simulations"]), est["simulations"])),
                    "simulations": est["simulations"],
                    "true_beta": est["true_beta"], "mean_estimate": r4(est["mean_estimate"]),
                    "label": est["label"], "template": "templates/applicants_by_posting.csv"},
    }
    from m1_text import build_text
    core.update(build_text(core, CFG))
    if write:
        (OUT / "model1_results.json").write_text(json.dumps(core, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        raw.assign(variant="raw").to_csv(OUT / "scores_primary_raw_family.csv", index=False)
        filt.assign(variant="sense_filtered").to_csv(OUT / "scores_primary_sense_filtered.csv", index=False)
    return core


if __name__ == "__main__":
    res = main()
    print(json.dumps({k: res[k] for k in ("corpus",)}, indent=1)[:1500])
