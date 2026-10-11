# Model 1 analysis plan (pre-registration)

**Status:** DRAFT, written 2026-10-11 before any posting score was computed. Awaiting (1) the posting corpus and named-people list from Elizabeth's PyCharm project, (2) family counts and sample titles for review, and (3) Elizabeth's **"go"**. No wording score, sense-audit label, or named-person gender code exists yet.

**Label on every output:** OBSERVED MEASUREMENT — posting text; describes wording, not intent.

## 1. Thesis alignment

Model 1 serves Research Thesis Version C 3.0 (Human-AI Employment Intelligence & Governance). It works on the *recruiting* stage, the first stage named in RQ3 and the only one public data can observe.

| Question | Hypothesis / component | What Model 1 contributes | What it cannot answer |
|---|---|---|---|
| Primary | H1, H2 | Measures one place where recruiting could contribute: what postings signal, and who they show | Whether postings contributed to the disparity |
| RQ1 Representation | H1, H2 | Tests one candidate upstream explanation | "Why", which needs applicant data |
| RQ2 Algorithmic influence | T7 scores | Measures the posting text any matching system would receive | Whether any system uses it, or how |
| RQ3 Stages | H3 (gated) | Observes the recruiting stage directly; H3 tests a link to outcomes | Screening, interviewing, hiring, or advancement |
| RQ4 Long-term AI risk | T7c | Tracks whether posting signals persist across Fellows versions | Feedback into AI systems (Model 2's question) |
| RQ5 Governance | Model 1b | The evaluation method, ready for internal data; the posting audit as a repeatable control | Accountability design |

## 2. Hypotheses

- **H1 (T7, RQ1/RQ2):** Fellows and research-titled postings use more masculine-coded words per 1,000 words than other role families. Null: no difference. This is Elizabeth's stated view; it is tested, not assumed.
- **H2 (T6, RQ1):** Women's share among people named in Fellows postings differs from (a) parity, 50%, and (b) women's share of Fellows hires, 36.4% (8 of 22 known sex). Direction-agnostic.
- **H3 (RQ3):** Across role families, posting signals are associated with women's share of hires. Run only if the estimability gate passes.

## 3. Inputs (located, never invented)

| # | Input | Location | Status |
|---|---|---|---|
| 1 | Posting text corpus, every captured version | Version C master (`historical_greenhouse_analytical_master.json`, R2 run `20260929T091413Z`) and Version D version files, in Elizabeth's PyCharm project / R2 | **Not in the GitHub repo.** Requested from the linked Mac on 2026-10-11; no response yet |
| 2 | April 26 captures (Economics 5183053008; RL 5183052008) | Project evidence doc gives a summary only; full OCR text is with the PDFs | Needs the OCR text files |
| 3 | Named-people list (person, version, role) | `version_d/outputs/` from `01_fellows_named_people.py` | **Not in the GitHub repo**; requested |
| 4 | Hire outcomes | Findings doc; `config.yaml → outcome_link.source_groups` | Available |
| 5 | Word lists | gender-decoder @ `7cb4a6d6a3b0a84a46eae8a6a312b5732cb363fd`, `app/wordlists.py`, vendored verbatim (MIT) | Available: 52 masculine, 50 feminine, 7 hyphenated stems |

The corpus will not be rebuilt from fresh web scraping or from memory.

## 4. Unit of analysis and exclusions

- **Primary unit:** one record per posting ID, its latest captured version. All distinct versions are used for sensitivity checks and the Fellows change-over-time table (T7c).
- **Cleaning:** strip HTML; normalize whitespace; SHA-256 of normalized text; drop exact duplicates (same posting ID, identical text).
- **Boilerplate:** remove every sentence that appears in ≥ 50% of primary records (shared "About Anthropic", benefits, logistics, EEO text). Report each removed sentence with its record share, and the share of words removed.
- **Short records:** exclude records under 150 words after boilerplate removal; report the count.

## 5. Role families

Applied in order to the title; the first match wins (case-insensitive):

1. **Fellows**: title contains "Fellow"
2. **Research-titled**: title contains "Research"
3. **Engineering**: title contains Engineer, Developer, Software, Infrastructure, or Reliability
4. **Other**: everything else

Version C carries a `posting_classification` field (title + department rules, plus a description-based research signal). **Proposed decision for review:** use the title rules above as primary, because they match the pre-registered definition and are reproducible from titles alone; report agreement with Version C's field (`role_family.py → family_report`) as a robustness table. Elizabeth can choose Version C's field instead at the "go" step.

Family counts and 20 sample titles per family: *pending corpus.* Posting families are not the same as hire families (hire groups are title-based from People Data Labs); mismatches will be listed.

## 6. Wording score (T7)

- Lowercase; transliterate to ASCII; tokenize on non-letters, keeping hyphenated forms for the hyphenated list (other hyphenated tokens are split into parts, as gender-decoder does).
- A stem matches a token only at the token's start; each token counts at most once per list.
- Per record: `masc_per_1k`, `fem_per_1k`, `net_per_1k` = masculine − feminine, and gender-decoder's categorical label (applied to these token counts).
- The word lists include additions to Gaucher et al. (2011). Gaucher et al.'s appendix has not been obtained; if it is, an original-stems-only variant is scored as a further robustness check.

## 7. Validity checks

**Sense audit (step 4).** Keyword-in-context sample of 200 matches, stratified by stem (maximum 10 per stem) and by family, drawn with seed 20261011. Each match is labeled:

- **Trait sense:** describes a person's disposition ("ambitious", "supportive teammate", "a confident communicator").
- **Other sense:** technical term, proper noun, product or team name, or section heading ("dependencies", "Trust & Safety", "Responsibilities", "Responsible Scaling Policy", "lead engineer" as a job level, "analysis", "commit" in version control, "customer support").

Precision per stem = trait-sense labels ÷ labels. **Fixed rule:** the sense-filtered score drops every stem with precision < 0.50 in the audit. Primary analysis = raw score; robustness = sense-filtered score. The labeler (Claude) records every label with its context in `labels/sense_audit_labels.csv`.

**Convergent check (step 5).** 300 sentences, stratified by family, seed 20261011. Each is coded agentic (independence, competition, dominance, assertiveness), communal (collaboration, care, support, interpersonal warmth) or neutral, blind to the lexicon's label. Compare with the lexicon's sentence label (masculine > feminine → agentic; feminine > masculine → communal; else neutral). Report Cohen's κ and the confusion matrix. **Fixed rule:** κ < 0.40 → the lexicon is flagged weakly valid in this domain, in the findings.

## 8. Tests and thresholds

| Test | Method | Threshold / reporting |
|---|---|---|
| T7a family differences | Each family vs. Other, for `masc_per_1k` and `fem_per_1k`; permutation test on the mean difference (10,000 permutations, two-sided); bootstrap 95% CI (10,000 resamples); Cliff's delta; Holm correction across all comparisons; raw and sense-filtered | α = .05 after Holm; effect sizes always reported |
| T7b Fellows power | Effect sizes and intervals for Fellows (about 9 records) | Low power stated plainly; p > .05 is not evidence of no difference |
| T7c change over time | Score deltas between Fellows versions (Economics Apr 26 → Jun 7; AI Safety Apr 3 → combined) | Described only, no test |
| T6a named people | Women among known (distinct persons), Wilson 95% CI, Unknown bounds | Unknown stays Unknown |
| T6b listing-weighted | Each appearance counts (63 mentor + 42 credit listings), by version | Descriptive |
| T6c comparisons | vs. 50% (exact binomial); vs. Fellows hires 8/22 (Fisher's exact) | α = .05, two-sided |
| T6d roles | Mentors and past-project credits reported separately | Descriptive |
| H3 gate | ≥ 10 non-overlapping cells, each ≥ 10 known-sex hires, both sexes in ≥ 5 cells | Otherwise `estimable: false` with cell counts; never fit on fewer cells |
| Model 1b | Binomial GLM on applicant counts per posting, SEs clustered by posting ID | Estimator test: 95% CI covers the true β in ≥ 90% of 200 simulated data sets |

**Gender of named people (T6):** public self-identification only (pronouns or explicit self-description in an official bio, faculty page, personal site, or published interview), with URL, exact quote and date accessed. Never inferred from names, photos or voice. If nothing is found, Unknown. Person-level codes are written only to `outputs/private/named_people_gender.csv`, which is git-ignored; every public output carries aggregates only.

## 9. Already run (no posting scores involved)

- **Estimability gate (H3), 2026-10-11:** `estimable: false`. Four non-overlapping cells (Fellows 14 M / 8 F / 10 U; non-Fellows researchers 5 / 0 / 3; Engineering 235 / 51 / 72; Other 352 / 217 / 128) < 10 required; one cell has < 10 known-sex hires; both sexes appear in 3 cells < 5. The Engineering/research overlap cannot be verified from aggregate counts.
- **Model 1b estimator test on simulated data, 2026-10-11:** 95% CI coverage of the true β = 0.96 across 200 simulated data sets (target ≥ 0.90); mean estimate −0.0295 vs. true −0.030. An estimator test, not a result.

## 10. Deviation log

| Date | Deviation | Reason |
|---|---|---|
| 2026-10-11 | Test 1's first draft asserted the fixture sentence had 7 words; it has 6. The test fixture was corrected; the scoring code was not changed. | Miscount in the test itself, caught on first run |

## References (APA 7)

Gaucher, D., Friesen, J., & Kay, A. C. (2011). Evidence that gendered wording in job advertisements exists and sustains gender inequality. *Journal of Personality and Social Psychology, 101*(1), 109–128.

Matfield, K. (n.d.). *Gender decoder for job ads* [Computer software]. GitHub. https://github.com/lovedaybrooke/gender-decoder

Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The preregistration revolution. *Proceedings of the National Academy of Sciences, 115*(11), 2600–2606.

Robinson, W. S. (1950). Ecological correlations and the behavior of individuals. *American Sociological Review, 15*(3), 351–357.
