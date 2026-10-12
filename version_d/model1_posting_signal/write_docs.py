"""Write outputs/model_card.md, outputs/methods_appendix.md and outputs/dashboard_updates.md
from outputs/model1_results.json and the pytest JUnit reports. Aggregates only; no names.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
CFG = yaml.safe_load((HERE / "config.yaml").read_text())


def f2(x):
    return "n/a" if x is None else f"{x:.2f}"


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def pfmt(p):
    return "< .001" if p < 0.001 else f"{p:.3f}".lstrip("0")


def tests():
    rows = []
    for xml in sorted((OUT / "tests").glob("*.xml")):
        for tc in ET.parse(xml).getroot().iter("testcase"):
            status, msg = "passed", ""
            for tag in ("failure", "error", "skipped"):
                el = tc.find(tag)
                if el is not None:
                    status = {"failure": "FAILED", "error": "ERROR", "skipped": "skipped"}[tag]
                    msg = (el.get("message") or "")[:140]
            rows.append({"name": tc.get("name"), "status": status, "time": float(tc.get("time", 0)), "msg": msg})
    return rows


def family_table(r, key):
    lines = ["| Family | n | Masculine per 1,000 (95% CI) | Feminine per 1,000 (95% CI) | Net (95% CI) |",
             "|---|---|---|---|---|"]
    for x in r["wording"][key]:
        def c(m):
            return f"{f2(x[m]['mean'])} ({f2(x[m]['ci'][0])} to {f2(x[m]['ci'][1])})"
        lines.append(f"| {x['family']} | {x['n']} | {c('masc_per_1k')} | {c('fem_per_1k')} | {c('net_per_1k')} |")
    return "\n".join(lines)


def test_table(r):
    lines = ["| Comparison | Metric | Variant | Difference (95% CI) | Permutation p | Holm p | Cliff's δ |",
             "|---|---|---|---|---|---|---|"]
    for t in r["wording"]["tests"]:
        lines.append(f"| {t['comparison']} (n = {t['n']} vs {t['n_ref']}) | {t['metric']} | {t['variant']} | "
                     f"{f2(t['diff'])} ({f2(t['ci'][0])} to {f2(t['ci'][1])}) | {pfmt(t['p_perm'])} | "
                     f"{pfmt(t['p_holm'])} | {f2(t['cliffs_delta'])} |")
    return "\n".join(lines)


def sense_table(r):
    lines = ["| List | Stem | Labeled | Trait sense | Precision | Kept in sense-filtered score |", "|---|---|---|---|---|---|"]
    drop = set(r["wording"]["sense_audit"]["dropped_stems"])
    for p in r["wording"]["sense_audit"]["precision_by_stem"]:
        lines.append(f"| {p['list']} | {p['stem']} | {p['n']} | {p['trait']} | {f2(p['precision'])} | "
                     f"{'no' if p['stem'] in drop else 'yes'} |")
    return "\n".join(lines)


def conf_table(cc, variant):
    v = cc["variants"][variant]
    cats = v["confusion_matrix"]["rows_rater"]
    lines = ["| Rater \\ Lexicon | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
    for c, row in zip(cats, v["confusion_matrix"]["counts"]):
        lines.append(f"| {c} | " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def vis_table(r):
    v = r["visibility"]
    lines = ["| Version | Named | Women | Men | Unknown |", "|---|---|---|---|---|"]
    for x in v["by_version"]:
        lines.append(f"| {x['version']} | {x['named']} | {x['women']} | {x['men']} | {x['unknown']} |")
    return "\n".join(lines)


def card(r, trows):
    v, w = r["visibility"], r["wording"]
    passed = sum(t["status"] == "passed" for t in trows)
    skipped = sum(t["status"] == "skipped" for t in trows)
    failed = [t["name"] for t in trows if t["status"] in ("FAILED", "ERROR")]
    return f"""# Model card: Model 1, posting-signal model (T7 linguistic bias · T6 visibility bias)

**{r['label']}.** Format follows Mitchell et al. (2019). Generated from `model1_results.json` (run date {r['run_date']}).

## Model details

- **What it is:** a measurement model of job-posting text. It scores gender-coded wording per 1,000 words with the Gaucher, Friesen, and Kay (2011) word lists as implemented in gender-decoder (commit `{CFG['wordlist']['commit'][:7]}`), checks the lexicon's validity with a sense audit and a blind convergent check, and counts the people Fellows postings name, coded by public self-identification only. It also includes an estimability-gated outcome link (H3) and an applicant-level estimator (Model 1b) built for internal data.
- **Developed by:** Elizabeth Hannan (Blue Blazing Media), Version D of the Human-AI Employment Intelligence & Governance study, October 2026; implementation written with Claude. Pre-registered in `analysis_plan.md` before any score was computed.
- **Corpus:** {r['corpus']['records_total']:,} posting records with text from three captures (current Greenhouse board, historical recovery, recovered archive pages), {r['corpus']['distinct_versions']:,} distinct versions, {r['corpus']['postings_primary']:,} postings (latest version each); {r['corpus']['records_scored']:,} scored after boilerplate removal ({pct(r['corpus']['boilerplate_word_share_removed'])} of words removed).

## Intended use

- Describe what Anthropic's postings signal, by role family: gendered wording, and who postings make visible.
- Serve as a repeatable posting audit, and (Model 1b) as the method for testing, on internal applicant counts, whether wording or visibility changes who applies.

## Out-of-scope uses

- Any claim that wording or named people changed who applied or who was hired.
- Any claim about intent, preference, or discrimination by Anthropic or any person.
- Any person-level statement: named individuals' codes are private and never published.

## Factors

Role family (title rules: Fellows → Research-titled → Engineering → Other); posting version (Fellows change over time); listing role (listed mentor vs. past-project credit).

## Metrics

Masculine-coded, feminine-coded, and net words per 1,000; permutation tests (10,000) with Holm correction, bootstrap 95% CIs (10,000), Cliff's δ; sense-audit precision; Cohen's κ; Wilson 95% CIs; exact binomial and Fisher's exact tests.

## Data

Observed posting text (Anthropic, 2026), captured April–September 2026; hire counts (Dewey & People Data Labs, 2026) for comparisons only. Named-people gender comes only from pronouns or explicit self-description in official bios, personal sites or profiles, or published interviews, with URL, verbatim quote and access date stored privately.

## Quantitative results

### Findings

{chr(10).join('- ' + f for f in r['findings'])}

### Wording by family (raw lexicon)

{family_table(r, 'by_family')}

### Visibility

Named people: {v['named_people']} ({v['coded']['women']} women, {v['coded']['men']} men, {v['coded']['unknown']} Unknown). Women among known: {pct(v['women_share_known']['value'])} (Wilson 95% CI {pct(v['women_share_known']['ci'][0])}–{pct(v['women_share_known']['ci'][1])}; Unknown bounds {pct(v['women_share_known']['bounds'][0])}–{pct(v['women_share_known']['bounds'][1])}). Versus parity: exact binomial p {pfmt(v['comparisons'][0]['p'])}. Versus Fellows hires 8/22: Fisher's exact p {pfmt(v['comparisons'][1]['p'])}.

### Executive conclusion (Model 1)

{r['executive_conclusion_model1']}

## Ethical considerations

- Named people are counted, never named, in every public output; person-level codes stay in a git-ignored private folder.
- Gender is never inferred from names, photos, or voice; Unknown stays Unknown and is reported with bounds.
- Lexical scores describe words, not people or intent.

## Caveats and recommendations

{chr(10).join('- ' + x for x in r['limitations'])}

**Recommendation.** Applicant counts by sex per posting (template `templates/applicants_by_posting.csv`) are the only data that test whether postings change who applies; Model 1b is ready for them.

**Tests:** {passed} passed, {skipped} skipped, {len(failed)} failed{(': ' + ', '.join(failed)) if failed else ''}.

## References

{chr(10).join(r['references'])}
"""


def appendix(r, trows):
    v, w = r["visibility"], r["wording"]
    cc = w["convergent_check"]
    sa = w["sense_audit"]
    t_rows = ["| Test | Result | Time (s) | Note |", "|---|---|---|---|"] + [
        f"| `{t['name']}` | {t['status']} | {t['time']:.1f} | {t['msg']} |" for t in trows]
    ch = w["change_over_time"]["pairs"]
    ch_rows = ["| Change | Masculine per 1,000 | Feminine per 1,000 |", "|---|---|---|"]
    for p in ch:
        if p["computed"]:
            ch_rows.append(f"| {p['change']} | {f2(p['from']['masc_per_1k'])} → {f2(p['to']['masc_per_1k'])} "
                           f"({p['delta_masc_per_1k']:+.2f}) | {f2(p['from']['fem_per_1k'])} → "
                           f"{f2(p['to']['fem_per_1k'])} ({p['delta_fem_per_1k']:+.2f}) |")
        else:
            ch_rows.append(f"| {p['change']} | not computed | {p['reason']} |")
    gate = r["outcome_link"]
    cells = ["| Cell | Male | Female | Unknown | Known |", "|---|---|---|---|---|"] + [
        f"| {c['cell']} | {c['male']} | {c['female']} | {c['unknown']} | {c['known']} |" for c in gate["cells"]]
    return f"""# Methods appendix: Model 1, posting-signal model

**{r['label']}.** Generated from `model1_results.json` (run date {r['run_date']}). Pre-registration and deviation log: `analysis_plan.md`.

## 1. Corpus

Sources: {'; '.join(r['corpus']['sources'])}.

| Step | Count |
|---|---|
| Records with text loaded | {r['corpus']['records_total']:,} |
| Exact duplicates dropped (same posting ID, same normalized text) | {r['corpus']['exact_duplicates_dropped']:,} |
| Distinct versions | {r['corpus']['distinct_versions']:,} |
| Postings (latest version each) | {r['corpus']['postings_primary']:,} |
| Boilerplate sentences removed (in ≥ 50% of postings) | {r['corpus']['boilerplate_sentences_removed']} |
| Share of words removed as boilerplate | {pct(r['corpus']['boilerplate_word_share_removed'])} |
| Excluded (< 150 words after removal) | {r['corpus']['excluded_short']} |
| Scored | {r['corpus']['records_scored']:,} |

Role families (title rules, in order): {', '.join(f"{f['family']} {f['n']}" for f in r['corpus']['families'])}.

## 2. Equations

For posting *j* with *N_j* tokens after boilerplate removal, masc_per_1k = 1000 · M_j / N_j and fem_per_1k = 1000 · F_j / N_j, where M_j (F_j) counts tokens that start with a masculine-coded (feminine-coded) stem; each token counts at most once per list; net = masc − fem. Sense-filtered scores drop stems whose audit precision is below 0.50. Family comparisons use the difference in means vs. Other, a two-sided permutation p (10,000), a bootstrap 95% CI (10,000, groups resampled independently), Cliff's δ = P(X > Y) − P(X < Y), and Holm adjustment across all {len(w['tests'])} comparisons. Wilson (1927) intervals for proportions.

## 3. Wording results

Raw lexicon:

{family_table(r, 'by_family')}

Sense-filtered:

{family_table(r, 'by_family_sense_filtered')}

Tests (T7a, T7b):

{test_table(r)}

T7b (Fellows power): the Fellows family has {next(f['n'] for f in w['by_family'] if f['family'] == 'Fellows')} postings, so its tests have low power; p > .05 is not evidence of no difference.

T7c (change over time, described only):

{chr(10).join(ch_rows)}

## 4. Sense audit (validity)

{sa['sampled']} keyword-in-context matches drawn with seed {CFG['seed']}, at most 10 per stem and spread across families; with {sa['stems_audited']} stems matched, stratification gave 1–4 matches per stem. Labeled trait vs. other sense by a Claude subagent with written rubric v1 (task verbs, levels, technical terms, proper nouns and headings = other). Overall precision {pct(sa['overall_precision'])} (Wilson 95% CI {pct(sa['overall_precision_ci'][0])}–{pct(sa['overall_precision_ci'][1])}). Precision by family: {', '.join(f'{k} {pct(x)}' for k, x in sa['by_family'].items())}. Stems dropped: {len(sa['dropped_stems'])}.

{sense_table(r)}

## 5. Convergent check

{cc['sentences']} sentences (75 per family, seed {CFG['seed'] + 1}, at least 4 tokens), coded agentic / communal / neutral by a Claude subagent blind to the lexicon labels. Cohen's κ (raw lexicon) = {f2(cc['kappa'])} (bootstrap 95% CI {f2(cc['kappa_ci'][0])}–{f2(cc['kappa_ci'][1])}); raw agreement {pct(cc['variants']['raw']['agreement'])}. Sense-filtered κ = {f2(cc['variants']['sense_filtered']['kappa'])}. Threshold 0.40 → weakly valid flag: **{cc['weakly_valid_flag']}**.

Raw lexicon:

{conf_table(cc, 'raw')}

Sense-filtered lexicon:

{conf_table(cc, 'sense_filtered')}

## 6. Visibility (T6)

{v['named_people']} distinct people across {v['fellows_versions']} Fellows versions ({v['versions_naming_people']} name anyone); {v['mentor_listings']} mentor listings and {v['credit_listings']} credit listings. Coding rule: {v['coding_rule']} Known codes by source type: {', '.join(f'{k} {n}' for k, n in v['source_types_for_known_codes'].items())}.

| Measure | Value |
|---|---|
| Women / men / Unknown (distinct people) | {v['coded']['women']} / {v['coded']['men']} / {v['coded']['unknown']} |
| Women among known (Wilson 95% CI) | {pct(v['women_share_known']['value'])} ({pct(v['women_share_known']['ci'][0])}–{pct(v['women_share_known']['ci'][1])}) |
| Unknown bounds (all Unknown men → all Unknown women) | {pct(v['women_share_known']['bounds'][0])}–{pct(v['women_share_known']['bounds'][1])} |
| Listing-weighted women among known listings | {pct(v['listing_weighted_women_share'])} ({v['listings']['women']} of {v['listings']['women'] + v['listings']['men']}) |
| Mentors: women / men / Unknown | {v['mentors_vs_credits']['mentors']['women']} / {v['mentors_vs_credits']['mentors']['men']} / {v['mentors_vs_credits']['mentors']['unknown']} |
| Credits: women / men / Unknown | {v['mentors_vs_credits']['credits']['women']} / {v['mentors_vs_credits']['credits']['men']} / {v['mentors_vs_credits']['credits']['unknown']} |
| vs. parity 50% (exact binomial) | p {pfmt(v['comparisons'][0]['p'])} |
| vs. Fellows hires 8 of 22 (Fisher's exact) | p {pfmt(v['comparisons'][1]['p'])} |

{vis_table(r)}

## 7. Outcome link (H3)

Rule: {gate['rule']}. Estimable: **{gate['estimable']}**. Reason: {gate['reason']}.

{chr(10).join(cells)}

{chr(10).join('- ' + n for n in gate['notes'])}

## 8. Model 1b (estimator test on simulated data, not a result)

Binomial GLM, logit P(woman) = α_family + β·masc_per_1k + γ·fem_per_1k + δ·named_women_share, SEs clustered by posting; beta-binomial simulated data with true β = {r['model1b']['true_beta']}. 95% CI coverage {pct(r['model1b']['coverage_in_simulation'])} over {r['model1b']['simulations']} data sets (Wilson CI {pct(r['model1b']['coverage_ci'][0])}–{pct(r['model1b']['coverage_ci'][1])}); mean estimate {r['model1b']['mean_estimate']}.

## 9. Tests

{chr(10).join(t_rows)}

## 10. Thesis alignment

| Question | Contribution | Status |
|---|---|---|
{chr(10).join(f"| {x['question']} | {x['contribution']} | {x['status']} |" for x in r['thesis_alignment'])}

## References

{chr(10).join(r['references'])}
"""


def dashboard(r):
    v, w = r["visibility"], r["wording"]
    t_fel = next(t for t in w["tests"] if t["comparison"] == "Fellows vs Other" and t["metric"] == "masc_per_1k"
                 and t["variant"] == "raw")
    t_res = next(t for t in w["tests"] if t["comparison"] == "Research-titled vs Other" and t["metric"] == "masc_per_1k"
                 and t["variant"] == "raw")
    cc, sa = w["convergent_check"], w["sense_audit"]
    fam = {x["family"]: x for x in w["by_family"]}
    wsk = v["women_share_known"]
    return f"""# Dashboard updates from Model 1 (paste into `data.js`)

Generated from `model1_results.json` (run date {r['run_date']}). Aggregates only; no names.

## `DATA.tests` T6

```js
result: "Fellows: {v['named_people']} named people across {v['fellows_versions']} versions; all other postings: 0 across 2,252 records. Public self-identification: {v['coded']['women']} women, {v['coded']['men']} men, {v['coded']['unknown']} Unknown. Women {pct(wsk['value'])} of known (95% CI {pct(wsk['ci'][0])}–{pct(wsk['ci'][1])}); vs. parity p {pfmt(v['comparisons'][0]['p'])}; vs. Fellows hires 8/22 p = {pfmt(v['comparisons'][1]['p'])}.",
meaning: "The only postings that show candidates who they would work with show mostly men among people with known self-identification. With {v['coded']['unknown']} Unknown, the share of all named people could be {pct(wsk['bounds'][0])}–{pct(wsk['bounds'][1])}. This measures visibility, not its effect on who applied.",
status: "observed"
```

## `DATA.tests` T7

```js
result: "Raw lexicon, masculine-coded per 1,000: Fellows {f2(fam['Fellows']['masc_per_1k']['mean'])} vs. Other {f2(fam['Other']['masc_per_1k']['mean'])} (diff {f2(t_fel['diff'])}, Holm p = {pfmt(t_fel['p_holm'])}); research-titled {f2(fam['Research-titled']['masc_per_1k']['mean'])} (Holm p = {pfmt(t_res['p_holm'])}). Lexicon weakly valid here: {pct(sa['overall_precision'])} trait-sense precision; κ = {f2(cc['kappa'])}.",
meaning: "No reliable masculine-coded excess in Fellows or research postings. The standard word lists mostly match technical terms in this text, so wording scores describe words, not intent, and carry little signal here.",
status: "observed"
```

## `DATA.models.m1`

```js
statusMeasure: "MEASURED — wording scored (lexicon weakly valid, κ = {f2(cc['kappa'])}); named people coded: {v['coded']['women']} women, {v['coded']['men']} men, {v['coded']['unknown']} Unknown",
statusOutcome: "NOT ESTIMABLE — {len(r['outcome_link']['cells'])} non-overlapping hire cells (10 required); Model 1b ready for internal applicant data"
```

## `DATA.thesisFrame.researchQuestions` status strings

```js
// n:1 Representation
status: "Observed; origin not established. Posting visibility: women {pct(wsk['value'])} of named people with known self-ID"
// n:3 Human decision-making
status: "Recruiting stage observed (postings); later stages not observed"
// n:5 Governance
status: "Evidence supports further investigation; posting audit and Model 1b estimator ready"
```

## New row for `DATA.thesisFrame.researchLayers`

```js
{{ layer:"Posting signals", conclusion:"Observable" }}
```

## Replit Agent prompt (paste into Replit)

> Add `model1_results.json` to the project root. In section 07, under the Model 1 card, fetch it on load; if it fails, show a dashed panel "Model 1 results pending." If it loads, render: (1) **F1**, a dot-and-interval chart of `wording.by_family` (masculine-coded in navy `#24406b`, feminine-coded in green `#4f7a3a`; these are word counts, not people), with a toggle for `by_family_sense_filtered`; (2) **F2**, a stacked horizontal bar per entry of `visibility.by_version` using women `#4f7fb3`, men `#d97757`, unknown `#b0aea5`, counts only, never names; (3) the `findings` list and the `limitations` list verbatim; (4) a pill "OBSERVED MEASUREMENT" (green observed style), never a SIMULATION tag. Each chart gets a CSV button and the caption "Observed measurement — posting text; describes wording, not intent. (Anthropic, 2026)". Use the existing observed styling, fonts and minimum 14px text; no yellow or gold.
"""


def main():
    r = json.loads((OUT / "model1_results.json").read_text(encoding="utf-8"))
    trows = tests()
    (OUT / "model_card.md").write_text(card(r, trows), encoding="utf-8")
    (OUT / "methods_appendix.md").write_text(appendix(r, trows), encoding="utf-8")
    (OUT / "dashboard_updates.md").write_text(dashboard(r), encoding="utf-8")
    print("wrote model_card.md, methods_appendix.md, dashboard_updates.md;", len(trows), "test cases")


if __name__ == "__main__":
    main()
