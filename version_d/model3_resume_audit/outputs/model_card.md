# Model card: Model 3, paired-résumé audit of stand-in AI screeners

**AUDIT OF STAND-IN AI SCREENERS — synthetic résumés scored against Anthropic's public postings; not Greenhouse's or Anthropic's system.** Run 2026-10-11. Pre-registration: `model3_plan.md`.

## What it is

An audit, not a model of Anthropic. 300 synthetic technical résumés (research 100, engineering 100, fellows 100) were each printed with 10 women's names, 10 men's names and no name, then scored by four stand-in screeners against 442 of Anthropic's public technical postings (research 101, engineering 334, fellows 7). Score = cosine similarity between résumé and posting.

- Women's names: Jessica, Ashley, Amanda, Sarah, Emily, Samantha, Jennifer, Brittany, Elizabeth, Stephanie
- Men's names: Michael, Christopher, Matthew, Joshua, Daniel, Andrew, David, James, Joseph, Nicholas
- Source: U.S. Social Security Administration births 1985–2000 (top 10 per sex, ≥ 99% one sex).

## Intended use

Show whether a matching model *can* treat identical résumés differently by name gender on Anthropic's own posting text, and demonstrate the audit method the thesis calls for (RQ5). **Not** for conclusions about Greenhouse, Anthropic, or any real applicant.

## Results

| Screener | Role | Validity: tier ρ / family AUC | Name gap G (SD) | Exact p (Holm) | Selection IR (random-split 95%) | Word gap (SD) | Word selection IR |
|---|---|---|---|---|---|---|---|
| SC1 WordLlama l2_supercat 256-d | primary | 0.43 / 0.77 | -0.130 | 0.066 (0.132) | 0.824 (0.824–1.221) | -0.131 | 0.798 |
| SC2 GloVe 300-d (Wikipedia 2014 + Gigaword 5) | robustness | 0.36 / 0.59 | -0.044 | 0.162 (0.162) | 0.944 (0.894–1.099) | +0.062 | 1.118 |
| SC3 fastText 300-d (wiki-news subword) — failed validity | robustness | 0.10 / 0.33 | +0.150 | 0.036 (0.109) | 1.397 (0.743–1.424) | -0.003 | 0.988 |
| SC0 TF-IDF keyword matcher (design control) | design control | 0.42 / 0.78 | +0.059 | 0.211 | 1.123 (0.884–1.129) | +0.000 | 0.997 |

G < 0 means men's names scored higher. Selection IR = women's selection rate ÷ men's when the top 10% of a pool are picked.

## Findings

- (Validity) 3 of 4 screeners ranked stronger résumés higher (mean Spearman with designed tier: WordLlama 0.43, GloVe 0.36, TF-IDF 0.42); fastText failed (0.10; family AUC 0.33), so its results are reported but not interpreted.
- (RQ2) With the primary screener (WordLlama), the same résumé scored higher with a men's name in 99% of the 442 technical postings, by 0.13 SD of résumé-to-résumé spread on average; but that is within the range arbitrary splits of the 20 names produce (exact p = 0.066; Holm-adjusted 0.13), so it is not statistically distinguishable from name-specific noise.
- (RQ2) Picking the top 10% by that score, résumés with women's names were selected at 0.82 times the rate of men's (median posting 0.83; 37% of postings below 0.80 versus 10% under random name splits), at the lower edge of the random-split range (0.824–1.221; observed 0.824).
- (RQ2) The other screeners did not agree: GloVe -0.04 SD (p = 0.16; selection ratio 0.94); fastText (failed validity) +0.15 SD (p = 0.04; selection ratio 1.40).
- (RQ2) Changing one word, WordLlama scored "Captain, men's …" above "Captain, women's …" on 100% of the 300 résumés (-0.13 SD; selection ratio 0.80); the other screeners did not repeat it (GloVe +0.062, fastText -0.003 SD).
- (RQ5) The keyword control was not exactly name-blind (test 6 failed): Fellows postings list mentors by name, and Michael, David, Nicholas appear in that text, so even a keyword matcher shifts scores for applicants who share those first names (overall +0.06 SD, p = 0.21; Fellows postings -0.08 SD).
- (Exploratory) Masculine-coded posting language (Model 1) did not predict the size of the name gap (Spearman +0.06, p = 0.20, 442 postings).

## Executive conclusion

The most consequential finding is not whether one AI screener is biased against women. It is that the answer depends on which model is used. On Anthropic's own technical postings, the most modern stand-in scored identical résumés lower with women's names in 99% of postings and penalized the word "women's" on every résumé, yet the name gap is not beyond what name choice alone can produce, and two older models did not agree. A gender audit of hiring technology cannot be done once, in general: it has to be run on the specific model in use, with paired résumés, before and after deployment. Anthropic's own screening has not been tested here, and nothing in this audit shows that it behaves this way.

## Thesis alignment

- **RQ2** — A direct test of candidate-matching models on Anthropic's own posting text. The most modern stand-in leaned toward men's names and the word "men's"; two older models did not agree. Model choice changed the answer. *Status: Tested on stand-in models only; not established for any system Anthropic uses.*
- **RQ5** — A ready template for the evaluation method the thesis calls for: paired résumés, exact name-level tests and a selection impact ratio, run on the specific screening model in use. *Status: Method demonstrated; requires access to Anthropic's actual screening configuration.*

Research layers unchanged: "Algorithmic causation: Not established".

## Limitations

- Stand-in screeners only. Nothing here describes Greenhouse's or Anthropic's screening, which is not public.
- Transformer sentence encoders like those in published audits (Wilson & Caliskan, 2024) could not be used: model hubs are blocked from this workspace. WordLlama is LLM-derived but bag-of-tokens.
- Cosine similarity to a posting is a simplified screener; real systems may use other signals or none.
- Synthetic résumés from one template family; results may differ for real résumés.
- Names are the 10 most common per sex for U.S. births 1985–2000; they skew toward white-associated names, so race and its intersection with gender are not tested. Individual names carry other meanings ("Brittany" is also a region), which is why the test is at the name level.
- The word test uses three items and one word pair; it probes those words only.
- fastText vectors are case-sensitive; the pre-registered lowercase lookup may weaken them, and that screener failed the validity check.
- Only 7 Fellows postings; family-level results for Fellows are imprecise.

## Tests

6 of 7 passed. Test 6 (keyword control exactly name-blind) failed as written; see the methods appendix. Tests were not edited.

## References (APA 7)

Bertrand, M., & Mullainathan, S. (2004). Are Emily and Greg more employable than Lakisha and Jamal? A field experiment on labor market discrimination. *American Economic Review, 94*(4), 991–1013.

Dastin, J. (2018, October 10). Amazon scraps secret AI recruiting tool that showed bias against women. *Reuters*.

dleemiller. (2024). *WordLlama* (Version 0.4.0.post1) [Computer software]. https://github.com/dleemiller/WordLlama

Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics, 6*(2), 65–70.

Mikolov, T., Grave, E., Bojanowski, P., Puhrsch, C., & Joulin, A. (2018). Advances in pre-training distributed word representations. In *Proceedings of the Eleventh International Conference on Language Resources and Evaluation (LREC 2018)*.

Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. In *Proceedings of the Conference on Fairness, Accountability, and Transparency* (pp. 220–229).

Pennington, J., Socher, R., & Manning, C. D. (2014). GloVe: Global vectors for word representation. In *Proceedings of the 2014 Conference on Empirical Methods in Natural Language Processing* (pp. 1532–1543).

U.S. Census Bureau. (2016). *Frequently occurring surnames in the 2010 Census*.

Uniform Guidelines on Employee Selection Procedures, 29 C.F.R. § 1607.4(D) (1978).

Wickham, H. (2019). *babynames: US baby names 1880–2017* (R package version 1.0.0) [Data set]. Source: U.S. Social Security Administration.

Wilson, K., & Caliskan, A. (2024). Gender, race, and intersectional bias in resume screening via language model retrieval. In *Proceedings of the AAAI/ACM Conference on AI, Ethics, and Society* (Vol. 7).
