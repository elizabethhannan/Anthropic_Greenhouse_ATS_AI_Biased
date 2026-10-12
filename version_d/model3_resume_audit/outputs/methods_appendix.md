# Methods appendix: Model 3 (paired-résumé audit)

**AUDIT OF STAND-IN AI SCREENERS — synthetic résumés scored against Anthropic's public postings; not Greenhouse's or Anthropic's system.** Run 2026-10-11.

## 1. Design

Correspondence audit (Bertrand & Mullainathan, 2004) applied to matching models (Wilson & Caliskan, 2024). Everything below was fixed in `model3_plan.md` and committed before scoring (commit "Model 3: pre-registered plan, name rule, résumé generator (before any scoring)").

- Résumés: `build_resumes.py`, seed 20261011; 100 per family; tiers strong 34, mid 33, entry 33. Variants differ only in the header line and email (test 1). Surnames (2010 Census top 10) rotate across résumés and are identical across a résumé's variants.
- Postings: Model 1's primary corpus; title rules Research-titled → research, Engineering → engineering, Fellows → fellows; title + full description text.
- Screeners: SC1 WordLlama l2_supercat 256-d (package 0.4.0.post1, weights SHA-256 64b47a2dc493cb8e85944076601189739852d7b64e0e1eedcb1937a251cd9fd5); SC2 GloVe 300-d; SC3 fastText 300-d wiki-news subword; SC0 TF-IDF fit on postings. Static vectors from the gensim-data GitHub releases.
- SC2: all 20 names have vectors: True; token coverage résumés 0.968, postings 0.989; checksum verified: True
- SC3: all 20 names have vectors: True; token coverage résumés 0.977, postings 0.990; checksum verified: True

## 2. Equations

For posting j with matched résumés r = 1…R, names k (women W, men M) and unnamed control u, score s(r, k, j):

- SDⱼ = standard deviation over r of s(r, u, j).
- Name effect Eₖⱼ = mean over r of [s(r, k, j) − s(r, u, j)] / SDⱼ; Eₖ = mean over j.
- Name gap dⱼ = mean over k∈W of Eₖⱼ − mean over k∈M of Eₖⱼ; G = mean over j of dⱼ = mean(E_W) − mean(E_M).
- Exact p: all 184,756 splits of the 20 names into two groups of 10; p = share with |G_split| ≥ |G_obs|. Holm (1979) across SC1–SC3.
- Selection: per posting, 100 pools; 50 résumés get a random woman's name and 50 a random man's; top 10% selected; IR = (women selected / women) ÷ (men selected / men), pooled. Null: 100 random name splits × 20 pools per posting.
- Word test: unnamed résumés; gap = [s(women's) − s(men's)] / SDⱼ, averaged over items, résumés, postings; résumé-level sign-flip test with 10,000 flips.
- Link to Model 1: Spearman(dⱼ, masculine-coded words per 1,000), 10,000 permutations.
- Validity: tier ρ = mean over postings of Spearman(tier, unnamed score); family AUC = mean over postings of ROC AUC (matched vs. other-family unnamed résumés). Flag if tier ρ ≤ 0.1.

## 3. Results by family

| Screener | Research G | Engineering G | Fellows G | Share of postings favoring men |
|---|---|---|---|---|
| SC1 | -0.092 | -0.143 | -0.011 | 0.993 |
| SC2 | -0.061 | -0.038 | -0.088 | 0.946 |
| SC3 | +0.116 | +0.162 | +0.108 | 0.000 |
| SC0 | +0.051 | +0.065 | -0.085 | 0.011 |

## 4. Tests

| Test | Result |
|---|---|
| test_1_paired_construction | passed |
| test_2_no_gendered_words | passed |
| test_3_name_rule | passed |
| test_4_exact_permutation | passed |
| test_5_validity_metrics | passed |
| test_6_tfidf_control_is_name_blind | FAILED |
| test_7_reproducible | passed |

**Test 6 failed.** The TF-IDF control was meant to be exactly name-blind because names are not posting words. Three of the men's names (Michael, David, Nicholas) do appear in Fellows postings, which list mentors by name, so résumés carrying those names gain a matching term and their scores shift. The test was not edited; the control was kept as pre-registered, and its results are reported as a finding: posting text that names people can make even a keyword matcher sensitive to applicants' first names.

## 5. Deviation log

| Date | Deviation | Reason |
|---|---|---|
| 2026-10-11 | Quick (test-only) subset changed from the first 12 résumés per family to every 8th résumé | The first 12 were all strong-tier, which made the quick validity metric undefined. Full-run analysis unaffected. |
| 2026-10-11 | Findings text skips quick runs | Text generator needs all four screeners; fixed a crash in test 7. Full-run numbers unaffected. |

## 6. Runtime

79.1 s on 2 cores (Python 3.13.16, NumPy 2.5.3, scikit-learn 1.9.1).

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
