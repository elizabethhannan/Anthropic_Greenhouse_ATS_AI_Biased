# Methods appendix: Model 1, posting-signal model

**OBSERVED MEASUREMENT — posting text; describes wording, not intent.** Generated from `model1_results.json` (run date 2026-10-11). Pre-registration and deviation log: `analysis_plan.md`.

## 1. Corpus

Sources: Greenhouse current snapshot 2026-09-29 (629 records); Historical Greenhouse deduplicated 20260929T074631Z (1,246 records; 704 with text); Recovered archive pages 20260930T024433Z (932 records; 930 with text).

| Step | Count |
|---|---|
| Records with text loaded | 2,263 |
| Exact duplicates dropped (same posting ID, same normalized text) | 653 |
| Distinct versions | 1,610 |
| Postings (latest version each) | 1,227 |
| Boilerplate sentences removed (in ≥ 50% of postings) | 41 |
| Share of words removed as boilerplate | 51.1% |
| Excluded (< 150 words after removal) | 1 |
| Scored | 1,226 |

Role families (title rules, in order): Fellows 7, Research-titled 101, Engineering 334, Other 784.

## 2. Equations

For posting *j* with *N_j* tokens after boilerplate removal, masc_per_1k = 1000 · M_j / N_j and fem_per_1k = 1000 · F_j / N_j, where M_j (F_j) counts tokens that start with a masculine-coded (feminine-coded) stem; each token counts at most once per list; net = masc − fem. Sense-filtered scores drop stems whose audit precision is below 0.50. Family comparisons use the difference in means vs. Other, a two-sided permutation p (10,000), a bootstrap 95% CI (10,000, groups resampled independently), Cliff's δ = P(X > Y) − P(X < Y), and Holm adjustment across all 12 comparisons. Wilson (1927) intervals for proportions.

## 3. Wording results

Raw lexicon:

| Family | n | Masculine per 1,000 (95% CI) | Feminine per 1,000 (95% CI) | Net (95% CI) |
|---|---|---|---|---|
| Fellows | 7 | 2.83 (2.18 to 3.51) | 8.99 (7.22 to 10.68) | -6.17 (-8.27 to -3.96) |
| Research-titled | 101 | 9.30 (7.81 to 10.90) | 13.11 (12.02 to 14.24) | -3.82 (-5.71 to -1.88) |
| Engineering | 334 | 9.32 (8.63 to 10.04) | 13.19 (12.44 to 13.95) | -3.87 (-4.90 to -2.86) |
| Other | 784 | 12.59 (12.09 to 13.09) | 14.43 (13.95 to 14.92) | -1.83 (-2.55 to -1.10) |

Sense-filtered:

| Family | n | Masculine per 1,000 (95% CI) | Feminine per 1,000 (95% CI) | Net (95% CI) |
|---|---|---|---|---|
| Fellows | 7 | 0.95 (0.60 to 1.20) | 2.18 (1.38 to 3.03) | -1.23 (-2.31 to -0.32) |
| Research-titled | 101 | 0.54 (0.32 to 0.80) | 2.96 (2.45 to 3.51) | -2.42 (-3.00 to -1.84) |
| Engineering | 334 | 0.50 (0.37 to 0.63) | 1.84 (1.56 to 2.13) | -1.35 (-1.66 to -1.03) |
| Other | 784 | 0.29 (0.23 to 0.35) | 2.26 (2.08 to 2.44) | -1.97 (-2.16 to -1.79) |

Tests (T7a, T7b):

| Comparison | Metric | Variant | Difference (95% CI) | Permutation p | Holm p | Cliff's δ |
|---|---|---|---|---|---|---|
| Fellows vs Other (n = 7 vs 784) | masc_per_1k | raw | -9.77 (-10.60 to -8.91) | .003 | .025 | -0.92 |
| Research-titled vs Other (n = 101 vs 784) | masc_per_1k | raw | -3.30 (-4.86 to -1.63) | < .001 | .001 | -0.31 |
| Engineering vs Other (n = 334 vs 784) | masc_per_1k | raw | -3.28 (-4.15 to -2.39) | < .001 | .001 | -0.29 |
| Fellows vs Other (n = 7 vs 784) | fem_per_1k | raw | -5.43 (-7.31 to -3.67) | .043 | .158 | -0.51 |
| Research-titled vs Other (n = 101 vs 784) | fem_per_1k | raw | -1.31 (-2.50 to -0.08) | .065 | .158 | -0.11 |
| Engineering vs Other (n = 334 vs 784) | fem_per_1k | raw | -1.24 (-2.13 to -0.31) | .006 | .049 | -0.12 |
| Fellows vs Other (n = 7 vs 784) | masc_per_1k | sense_filtered | 0.66 (0.30 to 0.91) | .039 | .158 | 0.62 |
| Research-titled vs Other (n = 101 vs 784) | masc_per_1k | sense_filtered | 0.25 (0.02 to 0.51) | .009 | .058 | 0.08 |
| Engineering vs Other (n = 334 vs 784) | masc_per_1k | sense_filtered | 0.21 (0.06 to 0.35) | .002 | .015 | 0.07 |
| Fellows vs Other (n = 7 vs 784) | fem_per_1k | sense_filtered | -0.08 (-0.92 to 0.78) | .936 | .936 | 0.11 |
| Research-titled vs Other (n = 101 vs 784) | fem_per_1k | sense_filtered | 0.70 (0.15 to 1.27) | .008 | .058 | 0.16 |
| Engineering vs Other (n = 334 vs 784) | fem_per_1k | sense_filtered | -0.42 (-0.75 to -0.08) | .014 | .070 | -0.12 |

T7b (Fellows power): the Fellows family has 7 postings, so its tests have low power; p > .05 is not evidence of no difference.

T7c (change over time, described only):

| Change | Masculine per 1,000 | Feminine per 1,000 |
|---|---|---|
| AI Safety Fellow (Apr 3) → AI Safety & Security, combined (Sep 29) | 2.15 → 1.78 (-0.37) | 9.69 → 10.69 (+1.00) |
| AI Security Fellow (Apr 2) → AI Safety & Security, combined (Sep 29) | 2.36 → 1.78 (-0.57) | 5.89 → 10.69 (+4.80) |
| ML Systems & Performance (Apr 15) → ML Systems & RL, combined (Sep 29) | 2.02 → 3.39 (+1.37) | 8.07 → 11.29 (+3.21) |
| Economics (Apr 26 capture) → Economics & Policy, Anthropic Institute (Jun 7 / Sep 29) | not computed | The April 26 capture is an image-only PDF; its OCR text was not provided, so wording was not scored. Named-people change (2 → 5 listed mentors) is reported under T6. |

## 4. Sense audit (validity)

200 keyword-in-context matches drawn with seed 20261011, at most 10 per stem and spread across families; with 62 stems matched, stratification gave 1–4 matches per stem. Labeled trait vs. other sense by a Claude subagent with written rubric v1 (task verbs, levels, technical terms, proper nouns and headings = other). Overall precision 21.0% (Wilson 95% CI 15.9%–27.2%). Precision by family: Engineering 25.4%, Fellows 13.3%, Other 20.8%, Research-titled 18.0%. Stems dropped: 50.

| List | Stem | Labeled | Trait sense | Precision | Kept in sense-filtered score |
|---|---|---|---|---|---|
| feminine | agree | 3 | 0 | 0.00 | no |
| feminine | child | 3 | 0 | 0.00 | no |
| feminine | collab | 3 | 3 | 1.00 | yes |
| feminine | commit | 3 | 0 | 0.00 | no |
| feminine | connect | 3 | 0 | 0.00 | no |
| feminine | cooperat | 3 | 2 | 0.67 | yes |
| feminine | depend | 3 | 0 | 0.00 | no |
| feminine | emotiona | 3 | 1 | 0.33 | no |
| feminine | empath | 3 | 3 | 1.00 | yes |
| feminine | enthusias | 3 | 3 | 1.00 | yes |
| feminine | feel | 3 | 2 | 0.67 | yes |
| feminine | honest | 3 | 0 | 0.00 | no |
| feminine | inclusive | 3 | 1 | 0.33 | no |
| feminine | interdependen | 2 | 0 | 0.00 | no |
| feminine | interpersonal | 3 | 3 | 1.00 | yes |
| feminine | kind | 3 | 0 | 0.00 | no |
| feminine | loyal | 1 | 0 | 0.00 | no |
| feminine | nurtur | 3 | 0 | 0.00 | no |
| feminine | quiet | 3 | 0 | 0.00 | no |
| feminine | respon | 3 | 0 | 0.00 | no |
| feminine | sensitiv | 3 | 0 | 0.00 | no |
| feminine | share | 3 | 0 | 0.00 | no |
| feminine | sharin | 3 | 0 | 0.00 | no |
| feminine | support | 3 | 0 | 0.00 | no |
| feminine | tender | 3 | 0 | 0.00 | no |
| feminine | together | 3 | 0 | 0.00 | no |
| feminine | trust | 3 | 0 | 0.00 | no |
| feminine | understand | 3 | 1 | 0.33 | no |
| feminine | warm | 3 | 0 | 0.00 | no |
| feminine | yield | 3 | 0 | 0.00 | no |
| masculine | active | 3 | 1 | 0.33 | no |
| masculine | aggress | 3 | 0 | 0.00 | no |
| masculine | ambitio | 3 | 1 | 0.33 | no |
| masculine | analy | 3 | 1 | 0.33 | no |
| masculine | assert | 3 | 0 | 0.00 | no |
| masculine | autonom | 4 | 1 | 0.25 | no |
| masculine | battle | 4 | 0 | 0.00 | no |
| masculine | challeng | 4 | 0 | 0.00 | no |
| masculine | champion | 4 | 0 | 0.00 | no |
| masculine | compet | 4 | 0 | 0.00 | no |
| masculine | confident | 4 | 1 | 0.25 | no |
| masculine | decid | 4 | 0 | 0.00 | no |
| masculine | decision | 4 | 0 | 0.00 | no |
| masculine | decisive | 4 | 3 | 0.75 | yes |
| masculine | defend | 4 | 0 | 0.00 | no |
| masculine | determin | 4 | 0 | 0.00 | no |
| masculine | dominant | 1 | 0 | 0.00 | no |
| masculine | driven | 4 | 0 | 0.00 | no |
| masculine | fight | 2 | 0 | 0.00 | no |
| masculine | force | 4 | 0 | 0.00 | no |
| masculine | hierarch | 4 | 0 | 0.00 | no |
| masculine | independen | 4 | 3 | 0.75 | yes |
| masculine | individual | 4 | 0 | 0.00 | no |
| masculine | intellect | 4 | 4 | 1.00 | yes |
| masculine | lead | 4 | 0 | 0.00 | no |
| masculine | logic | 4 | 0 | 0.00 | no |
| masculine | objective | 4 | 0 | 0.00 | no |
| masculine | opinion | 4 | 1 | 0.25 | no |
| masculine | persist | 4 | 4 | 1.00 | yes |
| masculine | principle | 4 | 0 | 0.00 | no |
| masculine | self-sufficien | 2 | 2 | 1.00 | yes |
| masculine | superior | 1 | 1 | 1.00 | yes |

## 5. Convergent check

300 sentences (75 per family, seed 20261012, at least 4 tokens), coded agentic / communal / neutral by a Claude subagent blind to the lexicon labels. Cohen's κ (raw lexicon) = 0.24 (bootstrap 95% CI 0.12–0.35); raw agreement 73.3%. Sense-filtered κ = 0.26. Threshold 0.40 → weakly valid flag: **True**.

Raw lexicon:

| Rater \ Lexicon | agentic | communal | neutral |
|---|---|---|---|
| agentic | 6 | 1 | 17 |
| communal | 1 | 14 | 7 |
| neutral | 19 | 35 | 200 |

Sense-filtered lexicon:

| Rater \ Lexicon | agentic | communal | neutral |
|---|---|---|---|
| agentic | 0 | 0 | 24 |
| communal | 0 | 9 | 13 |
| neutral | 1 | 4 | 249 |

## 6. Visibility (T6)

50 distinct people across 9 Fellows versions (8 name anyone); 63 mentor listings and 42 credit listings. Coding rule: Public self-identification only (pronouns or explicit self-description in an official bio, personal site or profile, or published interview); never inferred from names, photos or voice. Known codes by source type: interview 8, official_bio 20.

| Measure | Value |
|---|---|
| Women / men / Unknown (distinct people) | 3 / 25 / 22 |
| Women among known (Wilson 95% CI) | 10.7% (3.7%–27.2%) |
| Unknown bounds (all Unknown men → all Unknown women) | 6.0%–50.0% |
| Listing-weighted women among known listings | 8.9% (5 of 56) |
| Mentors: women / men / Unknown | 2 / 18 / 13 |
| Credits: women / men / Unknown | 1 / 9 / 10 |
| vs. parity 50% (exact binomial) | p < .001 |
| vs. Fellows hires 8 of 22 (Fisher's exact) | p .042 |

| Version | Named | Women | Men | Unknown |
|---|---|---|---|---|
| AI Safety & Security, combined (Sep 29) | 30 | 1 | 19 | 10 |
| AI Safety Fellow (Apr 3) | 25 | 1 | 19 | 5 |
| AI Security Fellow (Apr 2) | 11 | 0 | 3 | 8 |
| Economics & Policy, Anthropic Institute (Sep 29) | 12 | 2 | 5 | 5 |
| Economics (Apr 26 capture) | 9 | 1 | 3 | 5 |
| ML Systems & Performance (Apr 15) | 2 | 0 | 0 | 2 |
| ML Systems & RL, combined (Sep 29) | 9 | 0 | 1 | 8 |
| Reinforcement Learning (Jun 10) | 7 | 0 | 1 | 6 |
| STEM Fellow (Apr 18) | 0 | 0 | 0 | 0 |

## 7. Outcome link (H3)

Rule: >= 10 non-overlapping cells, each with >= 10 known-sex hires, and both sexes in >= 5 cells. Estimable: **False**. Reason: 4 cells < 10 required; 1 cell(s) with < 10 known-sex hires; both sexes appear in 3 cell(s) < 5 required.

| Cell | Male | Female | Unknown | Known |
|---|---|---|---|---|
| Fellows | 14 | 8 | 10 | 22 |
| Non-Fellows researchers | 5 | 0 | 3 | 5 |
| Engineering | 235 | 51 | 72 | 286 |
| Other | 352 | 217 | 128 | 569 |

- Fellows are a subset of AI researchers; non-Fellows researchers = researchers - Fellows.
- Engineering (general/unspecified) is treated as disjoint from the research cells; the source notes people can belong to several role groups through different employment records, so this overlap cannot be fully verified from aggregate counts.
- Ecological fallacy (Robinson, 1950): a family-level association would not show that a posting affected applicants.

## 8. Model 1b (estimator test on simulated data, not a result)

Binomial GLM, logit P(woman) = α_family + β·masc_per_1k + γ·fem_per_1k + δ·named_women_share, SEs clustered by posting; beta-binomial simulated data with true β = -0.03. 95% CI coverage 96.0% over 200 data sets (Wilson CI 92.3%–98.0%); mean estimate -0.0295.

## 9. Tests

| Test | Result | Time (s) | Note |
|---|---|---|---|
| `test_0_wordlist_pinned` | passed | 0.0 |  |
| `test_1_lexicon_arithmetic` | passed | 0.0 |  |
| `test_2_word_start_rule` | passed | 0.0 |  |
| `test_3_boilerplate_removal` | passed | 0.0 |  |
| `test_4_wilson_ci` | passed | 0.0 |  |
| `test_5_estimability_gate_current_cells` | passed | 0.0 |  |
| `test_6_model1b_recovery` | passed | 1.3 |  |
| `test_7_privacy` | passed | 0.0 |  |
| `test_8_reproducible` | passed | 30.1 |  |
| `test_holm_and_cliffs` | passed | 0.0 |  |
| `test_corpus_records_without_id_stay_distinct` | passed | 0.0 |  |
| `test_outcome_gate_fits_glm_when_gate_passes` | passed | 0.0 |  |
| `test_outcome_gate_passing_without_covariates_is_flagged` | passed | 0.0 |  |
| `test_visibility_nonbinary_totals_reconcile` | passed | 0.0 |  |

## 10. Thesis alignment

| Question | Contribution | Status |
|---|---|---|
| Primary | Measured two recruiting-stage signals. Wording: no reliable masculine-coded excess in Fellows or research postings, and the lexicon is weakly valid here (κ = 0.24). Visibility: of named people with public self-identification, 3 of 28 are women (10.7%). | Partial |
| RQ1 Representation | H1 not supported (raw scores run opposite; filtered differences under 1 word per 1,000). H2: women are 10.7% of named people with known self-identification, below parity and below Fellows hires, with Unknown bounds 6.0%–50.0%. Explaining "why" needs applicant data. | Partial |
| RQ2 Algorithmic influence | Measured the posting text any matching system would receive. The standard gendered-wording lexicon mostly matches technical terms in this text (21.0% trait sense), so it is a weak instrument for what a system would 'see'. Whether any system uses the text is not observable. | Partial |
| RQ3 Human decision-making | Observed the recruiting stage directly: Fellows postings are the only postings that name people, and among those with known self-identification 89.3% are men. The link to hires (H3) is not estimable from public data. | Partial |
| RQ4 Long-term AI risk | Tracked Fellows postings across versions: wording changed little between the April and September versions, and women stayed a small share of named people in every version with known codes. Feedback into AI systems is Model 2's question. | Partial |
| RQ5 Governance | Delivered a repeatable posting audit (wording with a sense audit, visibility with public self-identification) and the Model 1b estimator, validated at 96.0% CI coverage, ready for internal applicant counts by posting. | Partial — method built; needs internal data |

## References

Anthropic. (2026). Job postings, April–September 2026 [Greenhouse job board captures]. Greenhouse. https://job-boards.greenhouse.io/anthropic
Cliff, N. (1993). Dominance statistics: Ordinal analyses to answer ordinal questions. Psychological Bulletin, 114(3), 494–509.
Cohen, J. (1960). A coefficient of agreement for nominal scales. Educational and Psychological Measurement, 20(1), 37–46.
Dewey & People Data Labs. (2026). Observed Anthropic starts, April–July 2026 [Unpublished data set extract].
Gaucher, D., Friesen, J., & Kay, A. C. (2011). Evidence that gendered wording in job advertisements exists and sustains gender inequality. Journal of Personality and Social Psychology, 101(1), 109–128.
Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 6(2), 65–70.
Matfield, K. (n.d.). Gender decoder for job ads [Computer software]. GitHub. https://github.com/lovedaybrooke/gender-decoder
Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. In Proceedings of the Conference on Fairness, Accountability, and Transparency (pp. 220–229).
Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The preregistration revolution. Proceedings of the National Academy of Sciences, 115(11), 2600–2606.
Robinson, W. S. (1950). Ecological correlations and the behavior of individuals. American Sociological Review, 15(3), 351–357.
Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. Journal of the American Statistical Association, 22(158), 209–212.
