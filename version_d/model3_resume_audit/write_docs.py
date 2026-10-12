"""Write outputs/model_card.md and outputs/methods_appendix.md from the results."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"

REFS = [
    "Bertrand, M., & Mullainathan, S. (2004). Are Emily and Greg more employable than Lakisha and Jamal? A field "
    "experiment on labor market discrimination. *American Economic Review, 94*(4), 991–1013.",
    "Dastin, J. (2018, October 10). Amazon scraps secret AI recruiting tool that showed bias against women. *Reuters*.",
    "dleemiller. (2024). *WordLlama* (Version 0.4.0.post1) [Computer software]. https://github.com/dleemiller/WordLlama",
    "Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics, "
    "6*(2), 65–70.",
    "Mikolov, T., Grave, E., Bojanowski, P., Puhrsch, C., & Joulin, A. (2018). Advances in pre-training distributed "
    "word representations. In *Proceedings of the Eleventh International Conference on Language Resources and "
    "Evaluation (LREC 2018)*.",
    "Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & "
    "Gebru, T. (2019). Model cards for model reporting. In *Proceedings of the Conference on Fairness, "
    "Accountability, and Transparency* (pp. 220–229).",
    "Pennington, J., Socher, R., & Manning, C. D. (2014). GloVe: Global vectors for word representation. In "
    "*Proceedings of the 2014 Conference on Empirical Methods in Natural Language Processing* (pp. 1532–1543).",
    "U.S. Census Bureau. (2016). *Frequently occurring surnames in the 2010 Census*.",
    "Uniform Guidelines on Employee Selection Procedures, 29 C.F.R. § 1607.4(D) (1978).",
    "Wickham, H. (2019). *babynames: US baby names 1880–2017* (R package version 1.0.0) [Data set]. Source: U.S. "
    "Social Security Administration.",
    "Wilson, K., & Caliskan, A. (2024). Gender, race, and intersectional bias in resume screening via language "
    "model retrieval. In *Proceedings of the AAAI/ACM Conference on AI, Ethics, and Society* (Vol. 7).",
]


def tests_table():
    p = OUT / "tests" / "model3_tests.xml"
    if not p.exists():
        return "Test results not found.", 0, 0
    rows, n_pass, n = [], 0, 0
    for tc in ET.parse(p).iter("testcase"):
        n += 1
        fail = tc.find("failure")
        ok = fail is None
        n_pass += ok
        rows.append(f"| {tc.get('name')} | {'passed' if ok else 'FAILED'} |")
    return "| Test | Result |\n|---|---|\n" + "\n".join(rows), n_pass, n


def main():
    r = json.loads((OUT / "model3_results.json").read_text(encoding="utf-8"))
    log = json.loads((OUT / "run_log.json").read_text(encoding="utf-8"))
    c = r["config"]
    S = r["screeners"]
    tt, n_pass, n = tests_table()

    rows = []
    for e in S:
        v, g, s, w = e["validity"], e["name_gap"], e["selection"], e["word_test"]
        rows.append(f"| {e['id']} {e['name']}{' — failed validity' if v['flag_not_meaningful'] else ''} | {e['role']} | "
                    f"{v['tier_spearman_mean']:.2f} / {v['family_auc_mean']:.2f} | {g['G_std']:+.3f} | "
                    f"{g['p_exact']:.3f}{'' if g.get('p_holm') is None else f' ({g['p_holm']:.3f})'} | "
                    f"{s['pooled_ir']:.3f} ({s['null_pooled_ir_p025']:.3f}–{s['null_pooled_ir_p975']:.3f}) | "
                    f"{w['gap_std_women_minus_men']:+.3f} | {w['selection_pooled_ir']:.3f} |")
    table = ("| Screener | Role | Validity: tier ρ / family AUC | Name gap G (SD) | Exact p (Holm) | "
             "Selection IR (random-split 95%) | Word gap (SD) | Word selection IR |\n|---|---|---|---|---|---|---|---|\n"
             + "\n".join(rows))

    card = f"""# Model card: Model 3, paired-résumé audit of stand-in AI screeners

**{r['label']}.** Run {r['run_date']}. Pre-registration: `model3_plan.md`.

## What it is

An audit, not a model of Anthropic. {c['n_base_resumes']} synthetic technical résumés ({', '.join(f'{k} {v}' for k, v in c['base_resumes_by_family'].items())}) were each printed with {len(c['names']['women'])} women's names, {len(c['names']['men'])} men's names and no name, then scored by four stand-in screeners against {sum(c['postings_by_family'].values())} of Anthropic's public technical postings ({', '.join(f'{k} {v}' for k, v in c['postings_by_family'].items())}). Score = cosine similarity between résumé and posting.

- Women's names: {', '.join(c['names']['women'])}
- Men's names: {', '.join(c['names']['men'])}
- Source: U.S. Social Security Administration births 1985–2000 (top 10 per sex, ≥ 99% one sex).

## Intended use

Show whether a matching model *can* treat identical résumés differently by name gender on Anthropic's own posting text, and demonstrate the audit method the thesis calls for (RQ5). **Not** for conclusions about Greenhouse, Anthropic, or any real applicant.

## Results

{table}

G < 0 means men's names scored higher. Selection IR = women's selection rate ÷ men's when the top 10% of a pool are picked.

## Findings

""" + "\n".join(f"- {f}" for f in r["findings"]) + f"""

## Executive conclusion

{r['executive_conclusion_model3']}

## Thesis alignment

""" + "\n".join(f"- **{t['question']}** — {t['contribution']} *Status: {t['status']}.*" for t in r["thesis_alignment"]) + """

Research layers unchanged: "Algorithmic causation: Not established".

## Limitations

""" + "\n".join(f"- {x}" for x in r["limitations"]) + f"""

## Tests

{n_pass} of {n} passed. Test 6 (keyword control exactly name-blind) failed as written; see the methods appendix. Tests were not edited.

## References (APA 7)

""" + "\n\n".join(REFS) + "\n"
    (OUT / "model_card.md").write_text(card, encoding="utf-8")

    cov = "\n".join(f"- {e['id']}: all 20 names have vectors: {not e['vector_coverage']['names_without_vector']}; "
                    f"token coverage résumés {e['vector_coverage']['token_coverage_resumes']:.3f}, postings "
                    f"{e['vector_coverage']['token_coverage_postings']:.3f}; checksum verified: "
                    f"{e['vector_coverage']['checksum_verified']}" for e in S if "vector_coverage" in e)
    wl = next((e["model"] for e in S if "model" in e), {})
    per_fam = "\n".join(f"| {e['id']} | " + " | ".join(f"{e['name_gap']['by_family'][f]:+.3f}" for f in ("research", "engineering", "fellows"))
                        + f" | {e['name_gap']['share_postings_favoring_men']:.3f} |" for e in S)
    appendix = f"""# Methods appendix: Model 3 (paired-résumé audit)

**{r['label']}.** Run {r['run_date']}.

## 1. Design

Correspondence audit (Bertrand & Mullainathan, 2004) applied to matching models (Wilson & Caliskan, 2024). Everything below was fixed in `model3_plan.md` and committed before scoring (commit "Model 3: pre-registered plan, name rule, résumé generator (before any scoring)").

- Résumés: `build_resumes.py`, seed {c['seed']}; 100 per family; tiers strong 34, mid 33, entry 33. Variants differ only in the header line and email (test 1). Surnames (2010 Census top 10) rotate across résumés and are identical across a résumé's variants.
- Postings: Model 1's primary corpus; title rules Research-titled → research, Engineering → engineering, Fellows → fellows; title + full description text.
- Screeners: SC1 WordLlama l2_supercat 256-d (package {wl.get('version')}, weights SHA-256 {wl.get('weights_sha256')}); SC2 GloVe 300-d; SC3 fastText 300-d wiki-news subword; SC0 TF-IDF fit on postings. Static vectors from the gensim-data GitHub releases.
{cov}

## 2. Equations

For posting j with matched résumés r = 1…R, names k (women W, men M) and unnamed control u, score s(r, k, j):

- SDⱼ = standard deviation over r of s(r, u, j).
- Name effect Eₖⱼ = mean over r of [s(r, k, j) − s(r, u, j)] / SDⱼ; Eₖ = mean over j.
- Name gap dⱼ = mean over k∈W of Eₖⱼ − mean over k∈M of Eₖⱼ; G = mean over j of dⱼ = mean(E_W) − mean(E_M).
- Exact p: all {S[0]['name_gap']['n_splits']:,} splits of the 20 names into two groups of 10; p = share with |G_split| ≥ |G_obs|. Holm (1979) across SC1–SC3.
- Selection: per posting, {c['metrics']['selection_pools_per_posting']} pools; 50 résumés get a random woman's name and 50 a random man's; top {c['metrics']['selection_rate']:.0%} selected; IR = (women selected / women) ÷ (men selected / men), pooled. Null: {c['metrics']['null_splits']} random name splits × {c['metrics']['null_pools_per_posting']} pools per posting.
- Word test: unnamed résumés; gap = [s(women's) − s(men's)] / SDⱼ, averaged over items, résumés, postings; résumé-level sign-flip test with {c['metrics']['signflip_permutations']:,} flips.
- Link to Model 1: Spearman(dⱼ, masculine-coded words per 1,000), {c['metrics']['link_permutations']:,} permutations.
- Validity: tier ρ = mean over postings of Spearman(tier, unnamed score); family AUC = mean over postings of ROC AUC (matched vs. other-family unnamed résumés). Flag if tier ρ ≤ {c['metrics']['validity_flag_threshold']}.

## 3. Results by family

| Screener | Research G | Engineering G | Fellows G | Share of postings favoring men |
|---|---|---|---|---|
{per_fam}

## 4. Tests

{tt}

**Test 6 failed.** The TF-IDF control was meant to be exactly name-blind because names are not posting words. Three of the men's names (Michael, David, Nicholas) do appear in Fellows postings, which list mentors by name, so résumés carrying those names gain a matching term and their scores shift. The test was not edited; the control was kept as pre-registered, and its results are reported as a finding: posting text that names people can make even a keyword matcher sensitive to applicants' first names.

## 5. Deviation log

| Date | Deviation | Reason |
|---|---|---|
| 2026-10-11 | Quick (test-only) subset changed from the first 12 résumés per family to every 8th résumé | The first 12 were all strong-tier, which made the quick validity metric undefined. Full-run analysis unaffected. |
| 2026-10-11 | Findings text skips quick runs | Text generator needs all four screeners; fixed a crash in test 7. Full-run numbers unaffected. |

## 6. Runtime

{log['timings_seconds']['total']} s on 2 cores (Python {log['python']}, NumPy {log['numpy']}, scikit-learn {log['sklearn']}).

## References (APA 7)

""" + "\n\n".join(REFS) + "\n"
    (OUT / "methods_appendix.md").write_text(appendix, encoding="utf-8")


if __name__ == "__main__":
    main()
