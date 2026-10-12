# Model card: Model 1, posting-signal model (T7 linguistic bias · T6 visibility bias)

**OBSERVED MEASUREMENT — posting text; describes wording, not intent.** Format follows Mitchell et al. (2019). Generated from `model1_results.json` (run date 2026-10-11).

## Model details

- **What it is:** a measurement model of job-posting text. It scores gender-coded wording per 1,000 words with the Gaucher, Friesen, and Kay (2011) word lists as implemented in gender-decoder (commit `7cb4a6d`), checks the lexicon's validity with a sense audit and a blind convergent check, and counts the people Fellows postings name, coded by public self-identification only. It also includes an estimability-gated outcome link (H3) and an applicant-level estimator (Model 1b) built for internal data.
- **Developed by:** Elizabeth Hannan (Blue Blazing Media), Version D of the Human-AI Employment Intelligence & Governance study, October 2026; implementation written with Claude. Pre-registered in `analysis_plan.md` before any score was computed.
- **Corpus:** 2,263 posting records with text from three captures (current Greenhouse board, historical recovery, recovered archive pages), 1,610 distinct versions, 1,227 postings (latest version each); 1,226 scored after boilerplate removal (51.1% of words removed).

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

- Contrary to H1, Fellows postings used fewer masculine-coded words per 1,000 than Other postings on the raw lexicon (2.83 vs. 12.59; difference -9.77, 95% CI -10.60 to -8.91; Holm-adjusted p = .025; Cliff's δ = -0.92), and so did research-titled postings (-3.30, CI -4.86 to -1.63; Holm p = .001) (RQ1).
- The lexicon proved weakly valid in this technical text: only 21.0% of 200 audited matches used a word in a trait sense (95% CI 15.9%–27.2%), 50 of 62 audited stems fell below the 0.50 precision rule, and agreement with blind sentence ratings was κ = 0.24 (95% CI 0.12–0.35), below the pre-set 0.40 threshold (RQ2).
- After the low-precision stems were removed, the direction reversed but the differences were under one word per 1,000: Fellows 0.95 vs. Other 0.29 (difference 0.66, CI 0.30 to 0.91; Holm p = .158), research-titled 0.25 (CI 0.02 to 0.51; Holm p = .058) and Engineering 0.21 (CI 0.06 to 0.35; Holm p = .015); with 7 Fellows postings and 3–4 audit labels per stem, this robustness check has low power and is not evidence either way (RQ1).
- Among the 50 people named in Fellows postings, 28 had public self-identification: 3 women and 25 men, a women's share of 10.7% (Wilson 95% CI 3.7%–27.2%), below parity (exact binomial p < .001) and below women's 36.4% share of known-sex Fellows hires (Fisher's exact p = .042); because 22 people (44.0%) are Unknown, the share of all named people could lie anywhere from 6.0% to 50.0% (RQ1, RQ3).
- Listed mentors were 2 women, 18 men and 13 Unknown, and past-project credits 1, 9 and 10; counting every appearance across the 9 versions, women were 8.9% of known-gender listings (5 of 56; descriptive Wilson CI 3.9%–19.3%, listings are not independent) (RQ3, RQ4).
- The outcome link (H3) was not estimable: 4 non-overlapping hire cells against 10 required, with both sexes in only 3, so the "Predictive ML analysis" layer stays "Not estimable from public data"; the applicant-level estimator built for internal data (Model 1b) covered the known simulated effect in 96.0% of 200 simulated data sets (95% CI 92.3%–98.0%) (RQ5).

### Wording by family (raw lexicon)

| Family | n | Masculine per 1,000 (95% CI) | Feminine per 1,000 (95% CI) | Net (95% CI) |
|---|---|---|---|---|
| Fellows | 7 | 2.83 (2.18 to 3.51) | 8.99 (7.22 to 10.68) | -6.17 (-8.27 to -3.96) |
| Research-titled | 101 | 9.30 (7.81 to 10.90) | 13.11 (12.02 to 14.24) | -3.82 (-5.71 to -1.88) |
| Engineering | 334 | 9.32 (8.63 to 10.04) | 13.19 (12.44 to 13.95) | -3.87 (-4.90 to -2.86) |
| Other | 784 | 12.59 (12.09 to 13.09) | 14.43 (13.95 to 14.92) | -1.83 (-2.55 to -1.10) |

### Visibility

Named people: 50 (3 women, 25 men, 22 Unknown). Women among known: 10.7% (Wilson 95% CI 3.7%–27.2%; Unknown bounds 6.0%–50.0%). Versus parity: exact binomial p < .001. Versus Fellows hires 8/22: Fisher's exact p .042.

### Executive conclusion (Model 1)

The most consequential Model 1 finding is not that Anthropic's job postings use masculine-coded language: on a standard lexicon, Fellows and research postings show no reliable excess, and the lexicon itself proved weakly valid in technical text. It is that the only postings that show candidates who they would work with, the Fellows postings, show mostly men: among named people with public self-identification, 3 of 28 are women (10.7%), below parity and below women's share of Fellows hires, with 22 people still Unknown. This measures what postings make visible, not whether visibility changed who applied or who was hired; that question needs applicant counts by posting, which the Model 1b estimator is ready to analyze.

## Ethical considerations

- Named people are counted, never named, in every public output; person-level codes stay in a git-ignored private folder.
- Gender is never inferred from names, photos, or voice; Unknown stays Unknown and is reported with bounds.
- Lexical scores describe words, not people or intent.

## Caveats and recommendations

- Lexicon validity in technical text: 21.0% of audited matches were trait sense and κ = 0.24 against blind sentence ratings; terms like 'lead', 'analysis', 'support' and 'responsibilities' dominate the raw scores.
- The gender-decoder word lists include additions to Gaucher et al. (2011); the original appendix was not obtained, so an original-stems-only score was not run.
- Small Fellows n: 7 Fellows postings in the primary corpus (8 of 9 versions; the April 26 Economics capture was not provided as text).
- Role families are title-based; some titles land in a family they do not belong to by function (for example, 'Communications Manager, Research' is research-titled and 'IT Support Engineer' is Engineering).
- Posting families are not hire families: hire groups come from People Data Labs titles and overlap.
- Gender coding is limited to public self-identification: 22 of 50 people are Unknown, 8 of the known codes rest on interview or podcast pages written by hosts, and two personal pages could not be opened in this session.
- Nothing here observes applicants; no statement about who applied or why is possible.
- The sense audit and convergent check were labeled by a single rater (a Claude subagent with a written rubric), so no inter-rater reliability is available; the stem-level precision rests on 3–4 labels per stem.
- 542 of 1,246 historical records had no posting text; 1 record was excluded as under 150 words after boilerplate removal, which removed 51.1% of words.

**Recommendation.** Applicant counts by sex per posting (template `templates/applicants_by_posting.csv`) are the only data that test whether postings change who applies; Model 1b is ready for them.

**Tests:** 10 passed, 0 skipped, 0 failed.

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
