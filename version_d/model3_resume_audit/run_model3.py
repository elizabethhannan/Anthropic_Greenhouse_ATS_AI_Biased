"""Run Model 3: paired-résumé audit of stand-in AI screeners.

AUDIT OF STAND-IN AI SCREENERS — synthetic résumés scored against Anthropic's
public postings; not Greenhouse's or Anthropic's system.

Usage (from this folder):
    MODEL3_VECTORS_DIR=/path/to/vectors python run_model3.py
    python run_model3.py --quick --out DIR     # small subset, SC0 + SC1 only (tests)
    python run_model3.py --text-only           # rebuild findings text from existing results
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import audit  # noqa: E402
from build_resumes import (FAMILIES, WORD_TEST_ITEMS, build_base, render,  # noqa: E402
                           word_test_line)
from names import read_table, select_names  # noqa: E402
from screeners import (StaticScreener, TfidfScreener, WordLlamaScreener,  # noqa: E402
                       cosine, tokenize)

FORMS = ("plain", "women", "men")


def rnd(x, d=4):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [rnd(v, d) for v in x]
    x = float(x)
    return None if np.isnan(x) else round(x, d) + 0.0


def load_config():
    with open(HERE / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_postings(cfg) -> list[dict]:
    sys.path.insert(0, str((HERE / "../model1_posting_signal").resolve()))
    from role_family import assign_family
    fam_map = {v: k for k, v in cfg["postings"]["families"].items()}
    rows = []
    with open((HERE / cfg["postings"]["corpus"]).resolve(), encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("excluded_short"):
                continue
            fam = fam_map.get(assign_family(r["title"]))
            if fam:
                rows.append({"posting_id": r["posting_id"], "title": r["title"], "family": fam,
                             "text": f"{r['title']}\n{r['text']}"})
    rows.sort(key=lambda r: (FAMILIES.index(r["family"]), r["posting_id"]))
    return rows


def load_masc(cfg) -> dict:
    p = (HERE / cfg["postings"]["model1_scores"]).resolve()
    out = {}
    if p.exists():
        with open(p, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                out[r["posting_id"]] = float(r["masc_per_1k"])
    return out


def build_texts(base, names_all):
    """Returns texts list and index maps."""
    texts, idx_named, idx_word = [], {}, {}
    for r in base:
        rid = r["resume_id"]
        for k, nm in enumerate(names_all + [None]):
            idx_named[(rid, k)] = len(texts)
            texts.append(render(r, nm))
        for i, item in enumerate(WORD_TEST_ITEMS):
            for f, form in enumerate(FORMS):
                idx_word[(rid, i, f)] = len(texts)
                texts.append(render(r, None, activity=word_test_line(item, form)))
    return texts, idx_named, idx_word


def make_screener(sc, posting_texts, all_texts, vec_dir):
    if sc["kind"] == "wordllama":
        return WordLlamaScreener(sc.get("dim", 256))
    if sc["kind"] == "tfidf":
        return TfidfScreener(posting_texts)
    if sc["kind"] == "static":
        vocab = set()
        for t in all_texts:
            vocab.update(tokenize(t))
        return StaticScreener(Path(vec_dir) / sc["file"], vocab, sc.get("checksum_md5"))
    raise ValueError(sc["kind"])


def evaluate(scr, sc, cfg, base, postings, names_all, n_f, texts, idx_named, idx_word, masc, d):
    m = cfg["metrics"]
    seed = cfg["seed"]
    n_names = len(names_all)
    female_idx, male_idx = list(range(n_f)), list(range(n_f, n_names))
    E_post = scr.embed([p["text"] for p in postings])
    E_res = scr.embed(texts)
    fam_res = {f: [r for r in base if r["family"] == f] for f in FAMILIES}
    fam_post = {f: [j for j, p in enumerate(postings) if p["family"] == f] for f in FAMILIES}

    # Unnamed résumés x all postings (family AUC, validity)
    un_rows = [idx_named[(r["resume_id"], n_names)] for r in base]
    S_un = cosine(E_res[un_rows], E_post)                      # 300 x P

    S_named, S_word = {}, {}
    for f in FAMILIES:
        rows = [idx_named[(r["resume_id"], k)] for r in fam_res[f] for k in range(n_names + 1)]
        S = cosine(E_res[rows], E_post[fam_post[f]])
        S_named[f] = S.reshape(len(fam_res[f]), n_names + 1, len(fam_post[f]))
        rows = [idx_word[(r["resume_id"], i, ff)] for r in fam_res[f]
                for i in range(len(WORD_TEST_ITEMS)) for ff in range(3)]
        S = cosine(E_res[rows], E_post[fam_post[f]])
        S_word[f] = S.reshape(len(fam_res[f]), len(WORD_TEST_ITEMS), 3, len(fam_post[f]))

    # ---- validity
    tier_r, auc, tier_by = [], [], {}
    for f in FAMILIES:
        res_i = [i for i, r in enumerate(base) if r["family"] == f]
        oth_i = [i for i, r in enumerate(base) if r["family"] != f]
        tiers = np.array([base[i]["tier_code"] for i in res_i])
        tv = audit.tier_validity(S_un[np.ix_(res_i, fam_post[f])], tiers)
        tier_by[f] = rnd(np.nanmean(tv), d)
        tier_r.append(tv)
        auc.append(audit.family_auc(S_un[np.ix_(res_i, fam_post[f])], S_un[np.ix_(oth_i, fam_post[f])]))
    tier_all = np.concatenate(tier_r)
    auc_all = np.concatenate(auc)
    tier_mean = float(np.nanmean(tier_all))
    validity = {"tier_spearman_mean": rnd(tier_mean, d), "tier_spearman_by_family": tier_by,
                "family_auc_mean": rnd(np.nanmean(auc_all), d),
                "flag_not_meaningful": bool(tier_mean <= m["validity_flag_threshold"])}

    # ---- M3-1 name gap
    E_name_post = np.concatenate([audit.name_effects(S_named[f]) for f in FAMILIES], axis=1)  # names x P
    d_post = E_name_post[female_idx].mean(axis=0) - E_name_post[male_idx].mean(axis=0)
    raw_gap = np.concatenate([(S_named[f][:, female_idx, :].mean(axis=1) - S_named[f][:, male_idx, :].mean(axis=1)).mean(axis=0)
                              for f in FAMILIES])
    E_name = E_name_post.mean(axis=1)
    perm = audit.exact_permutation(E_name, female_idx)
    fam_slices, start = {}, 0
    for f in FAMILIES:
        fam_slices[f] = slice(start, start + len(fam_post[f]))
        start += len(fam_post[f])
    name_gap = {"G_std": rnd(perm["G"], d), "p_exact": perm["p_exact"], "n_splits": perm["n_splits"],
                "null_p025": rnd(perm["null_p025"], d), "null_p975": rnd(perm["null_p975"], d),
                "by_family": {f: rnd(d_post[fam_slices[f]].mean(), d) for f in FAMILIES},
                "raw_cosine_gap_mean": rnd(raw_gap.mean(), 6),
                "share_postings_favoring_men": rnd(np.mean(d_post < 0), d),
                "n_postings": int(len(d_post))}
    per_name = [{"name": nm, "group": "women" if k < n_f else "men", "effect_std": rnd(E_name[k], d),
                 **{f"effect_std_{f}": rnd(E_name_post[k, fam_slices[f]].mean(), d) for f in FAMILIES}}
                for k, nm in enumerate(names_all)]

    # ---- M3-2 selection
    cols, seeds = [], []
    for f in FAMILIES:
        for jj, j in enumerate(fam_post[f]):
            cols.append(S_named[f][:, :n_names, jj])
            seeds.append([seed, j])
    sel = audit.selection(cols, female_idx, male_idx, m["selection_pools_per_posting"], m["selection_rate"], seeds)
    rng = np.random.default_rng([seed, 7])
    null_pooled, null_share = [], []
    for s in range(m["null_splits"]):
        ga = sorted(rng.choice(n_names, n_f, replace=False).tolist())
        gb = [k for k in range(n_names) if k not in ga]
        ns = audit.selection(cols, ga, gb, m["null_pools_per_posting"], m["selection_rate"],
                             [[seed, 1000 + s, j] for j in range(len(cols))])
        null_pooled.append(ns["pooled_ir"])
        null_share.append(np.nanmean(ns["per_posting_ir"] < m["four_fifths"]))
    selection = {"pooled_ir": rnd(sel["pooled_ir"], d),
                 "posting_median_ir": rnd(np.nanmedian(sel["per_posting_ir"]), d),
                 "share_postings_below_080": rnd(np.nanmean(sel["per_posting_ir"] < m["four_fifths"]), d),
                 "null_pooled_ir_p025": rnd(np.percentile(null_pooled, 2.5), d),
                 "null_pooled_ir_p975": rnd(np.percentile(null_pooled, 97.5), d),
                 "null_share_below_080_mean": rnd(np.mean(null_share), d),
                 "pools_per_posting": m["selection_pools_per_posting"], "selection_rate": m["selection_rate"]}

    # ---- M3-3 word test
    by_item, d_word_post, D_res = {}, [], []
    wm_all, wp_all, mp_all = [], [], []
    for f in FAMILIES:
        sd = audit.posting_sd(S_named[f])                                   # P_f
        W = S_word[f]
        wm = (W[:, :, 1, :] - W[:, :, 2, :]) / sd                           # res x item x P
        wp = (W[:, :, 1, :] - W[:, :, 0, :]) / sd
        mp = (W[:, :, 2, :] - W[:, :, 0, :]) / sd
        wm_all.append(wm)
        wp_all.append(wp)
        mp_all.append(mp)
        d_word_post.append(wm.mean(axis=(0, 1)))
        D_res.append(wm.mean(axis=(1, 2)))
    d_word_post = np.concatenate(d_word_post)
    D_res = np.concatenate(D_res)
    for i, item in enumerate(WORD_TEST_ITEMS):
        by_item[item] = rnd(np.concatenate([x[:, i, :].mean(axis=0) for x in wm_all]).mean(), d)
    wcols = []
    for f in FAMILIES:
        for jj in range(len(fam_post[f])):
            wcols.append(S_word[f][:, :, :, jj].reshape(len(fam_res[f]), -1))
    wsel = audit.selection(wcols, [1, 4, 7], [2, 5, 8], m["selection_pools_per_posting"], m["selection_rate"],
                           [[seed, 50000 + j] for j in range(len(wcols))])
    word = {"gap_std_women_minus_men": rnd(d_word_post.mean(), d), "by_item": by_item,
            "women_minus_plain": rnd(np.concatenate([x.mean(axis=(0, 1)) for x in wp_all]).mean(), d),
            "men_minus_plain": rnd(np.concatenate([x.mean(axis=(0, 1)) for x in mp_all]).mean(), d),
            "p_signflip": audit.signflip(D_res, m["signflip_permutations"], seed),
            "share_resumes_favoring_men": rnd(np.mean(D_res < 0), d),
            "selection_pooled_ir": rnd(wsel["pooled_ir"], d)}

    # ---- M3-4 link to Model 1
    pids = [postings[j]["posting_id"] for f in FAMILIES for j in fam_post[f]]
    mx = np.array([masc.get(pid, np.nan) for pid in pids])
    link = (audit.spearman_perm(mx, d_post, m["link_permutations"], seed) if np.isfinite(mx).sum() > 5
            else {"spearman": None, "p_perm": None, "n": int(np.isfinite(mx).sum())})
    link = {k: (rnd(v, d) if k == "spearman" else v) for k, v in link.items()}

    entry = {"id": sc["id"], "name": sc["name"], "kind": sc["kind"],
             "role": ("primary" if sc["id"] == cfg["screeners"]["primary"]
                      else "design control" if sc["kind"] == "tfidf" else "robustness"),
             "validity": validity, "name_gap": name_gap, "per_name": per_name,
             "selection": selection, "word_test": word, "posting_link_model1": link}
    if isinstance(scr, StaticScreener):
        res_tokens = [t for i in un_rows for t in tokenize(texts[i])]
        post_tokens = [t for p in postings for t in tokenize(p["text"])]
        entry["vector_coverage"] = {
            "names_with_vector": [nm for nm in names_all if nm.lower() in scr.vectors],
            "names_without_vector": [nm for nm in names_all if nm.lower() not in scr.vectors],
            "token_coverage_resumes": rnd(scr.coverage(res_tokens), d),
            "token_coverage_postings": rnd(scr.coverage(post_tokens), d),
            "checksum_verified": scr.checksum_ok}
    if isinstance(scr, WordLlamaScreener):
        entry["model"] = {"package": "wordllama", "version": scr.version, "weights_sha256": scr.weights_sha256}
    posting_rows = [{"screener": sc["id"], "posting_id": pid, "title": postings[j]["title"],
                     "family": postings[j]["family"], "d_name": rnd(d_post[q], d),
                     "d_word": rnd(d_word_post[q], d), "masc_per_1k": rnd(mx[q], d)}
                    for q, (pid, j) in enumerate(zip(pids, [j for f in FAMILIES for j in fam_post[f]]))]
    return entry, posting_rows, perm["p_exact"]


def main(outdir=None, quick=False) -> dict:
    t0 = time.time()
    cfg = load_config()
    d = cfg["decimals"]
    outdir = Path(outdir) if outdir else HERE / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    names = select_names(read_table())
    names_all = names["women"] + names["men"]
    base = build_base(cfg["seed"])
    committed = json.loads((HERE / "data" / "resumes_base.json").read_text(encoding="utf-8"))
    if base != committed:
        raise RuntimeError("generated résumés differ from the committed data/resumes_base.json")
    postings = load_postings(cfg)
    screener_cfgs = cfg["screeners"]["list"]
    if quick:
        base = [r for f in FAMILIES for r in [x for x in base if x["family"] == f][::8][:12]]  # spans all tiers
        postings = [p for f in FAMILIES for p in [x for x in postings if x["family"] == f][:6]]
        screener_cfgs = [s for s in screener_cfgs if s["id"] in ("SC0", "SC1")]
        cfg["metrics"].update(selection_pools_per_posting=10, null_splits=5, null_pools_per_posting=5,
                              signflip_permutations=500, link_permutations=500)
    masc = load_masc(cfg)
    texts, idx_named, idx_word = build_texts(base, names_all)
    vec_dir = os.environ.get(cfg["screeners"]["vectors_dir_env"], str(HERE / "data" / "vectors"))

    entries, posting_rows, pvals, timings = [], [], {}, {}
    for sc in screener_cfgs:
        t1 = time.time()
        scr = make_screener(sc, [p["text"] for p in postings], texts + [p["text"] for p in postings], vec_dir)
        e, rows, p = evaluate(scr, sc, cfg, base, postings, names_all, len(names["women"]),
                              texts, idx_named, idx_word, masc, d)
        entries.append(e)
        posting_rows += rows
        if sc["kind"] != "tfidf":
            pvals[sc["id"]] = p
        timings[sc["id"]] = round(time.time() - t1, 1)
        del scr
    for sc_id, ph in audit.holm(pvals).items():
        next(e for e in entries if e["id"] == sc_id)["name_gap"]["p_holm"] = ph

    results = {
        "label": cfg["label"], "version": cfg["version"], "run_date": dt.date.today().isoformat(),
        "config": {"seed": cfg["seed"], "names": names, "surnames_rotated": True,
                   "n_base_resumes": len(base),
                   "base_resumes_by_family": {f: sum(r["family"] == f for r in base) for f in FAMILIES},
                   "variants_per_resume": {"named": len(names_all), "unnamed": 1,
                                           "word_test": len(WORD_TEST_ITEMS) * 3},
                   "postings_by_family": {f: sum(p["family"] == f for p in postings) for f in FAMILIES},
                   "posting_family_map": cfg["postings"]["families"], "metrics": cfg["metrics"],
                   "word_test_items": WORD_TEST_ITEMS, "quick": quick},
        "screeners": entries,
    }
    try:
        from findings_m3 import build_text
        results.update(build_text(results))
    except ImportError:
        results.update({"thesis_alignment": [], "findings": [], "limitations": [], "executive_conclusion_model3": ""})

    with open(outdir / "model3_results.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    with open(outdir / "name_effects.csv", "w", newline="", encoding="utf-8") as fh:
        keys = ["screener", "name", "group", "effect_std"] + [f"effect_std_{f}" for f in FAMILIES]
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for e in entries:
            for r in e["per_name"]:
                w.writerow({"screener": e["id"], **r})
    with open(outdir / "posting_gaps.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(posting_rows[0].keys()))
        w.writeheader()
        w.writerows(posting_rows)
    import sklearn
    log = {"run_date": results["run_date"], "timings_seconds": {**timings, "total": round(time.time() - t0, 1)},
           "python": sys.version.split()[0], "numpy": np.__version__, "sklearn": sklearn.__version__}
    if not quick:
        with open(outdir / "run_log.json", "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=2)
            fh.write("\n")
    return results


def rebuild_text(outdir=None):
    from findings_m3 import build_text
    outdir = Path(outdir) if outdir else HERE / "outputs"
    p = outdir / "model3_results.json"
    r = json.loads(p.read_text(encoding="utf-8"))
    r.update(build_text(r))
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--text-only", action="store_true")
    a = ap.parse_args()
    if a.text_only:
        rebuild_text(a.out)
        raise SystemExit(0)
    r = main(a.out, a.quick)
    for e in r["screeners"]:
        print(e["id"], e["validity"], e["name_gap"]["G_std"], e["name_gap"]["p_exact"], e["selection"]["pooled_ir"])
