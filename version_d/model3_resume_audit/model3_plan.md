# Model 3 plan (pre-registration): paired-résumé audit of stand-in AI screeners

**Status:** written 2026-10-11, after Elizabeth asked for "all three models", and **before any résumé was scored**. This file, the résumé generator (`build_resumes.py`), the name table (`data/names_ssa_1985_2000.csv`) and the configuration (`config.yaml`) are committed before scoring. Nothing below changes after scores are seen; any change goes in the deviation log with a reason.

**Label on every output:** AUDIT OF STAND-IN AI SCREENERS — synthetic résumés scored against Anthropic's public job postings. Not Greenhouse's or Anthropic's system. Not Anthropic applicant data.

## 1. Question

If an off-the-shelf AI matching model were used to rank applicants for Anthropic's technical postings, would it score **identical résumés** differently when the name on top is a woman's rather than a man's?

This is a correspondence (paired-résumé) audit of the kind run on people (Bertrand & Mullainathan, 2004) and on language-model résumé retrieval (Wilson & Caliskan, 2024). It tests stand-in screeners, not the screening Anthropic actually uses, which is not public.

| Thesis question | What Model 3 adds |
|---|---|
| RQ2 Algorithmic influence ("candidate matching") | Direct test of whether a matching model is sensitive to name gender on Anthropic's own posting text |
| RQ5 Governance ("evaluation methods") | A paired-résumé audit Anthropic could run on its real screening tools; this is the template |

Research layers do not change: "Algorithmic causation: Not established". A stand-in model's behavior says nothing about what Greenhouse or Anthropic does.

## 2. Inputs

- **Postings:** Anthropic's public Greenhouse postings, Model 1's primary corpus (one row per posting; 1,227 postings captured 2026-09-29 and earlier). Technical families only, by Model 1's pre-registered title rules: Research-titled (101), Engineering (335), Fellows (7) = 443 postings. Screeners see the full posting: title + full description text (boilerplate kept, as a real screener would see it).
- **Names (gender signal):** U.S. Social Security Administration counts of births 1985–2000 (people roughly 26–41 in 2026), from the `babynames` dataset (Wickham, 2019; source file SHA-256 recorded). Rule: rank names by count within sex; keep names with at least 99% of births of that sex; take the top 10 per sex. Result:
  - Women: Jessica, Ashley, Amanda, Sarah, Emily, Samantha, Jennifer, Brittany, Elizabeth, Stephanie
  - Men: Michael, Christopher, Matthew, Joshua, Daniel, Andrew, David, James, Joseph, Nicholas
- **Surnames:** the ten most frequent 2010 Census surnames (U.S. Census Bureau, 2016), one per résumé by rotation, **identical across that résumé's name variants**: Smith, Johnson, Williams, Brown, Jones, Garcia, Miller, Davis, Rodriguez, Martinez.

## 3. Résumés (synthetic; generator fixed, seed 20261011)

- 300 base résumés: 100 each for **research**, **engineering** and **fellows** (early-career research), matched to the Research-titled, Engineering and Fellows posting families.
- Three designed quality tiers per family (34 strong, 33 mid, 33 entry): years of experience, degree, number of relevant bullets, skills and publications rise with tier.
- Fictional employers; real universities by rotation; no pronouns or gendered words anywhere in the base text (test 2).
- **Variants of each base résumé:** 20 named versions (10 women's names, 10 men's) plus 1 unnamed control ("Applicant", applicant@example.com). Variants differ **only** in the header line and the email address (test 1).
- **Word test variants (M3-3):** the unnamed version with its one activity line replaced by "Captain, chess club" / "Captain, women's chess club" / "Captain, men's chess club", and the same three forms for "soccer team" and "debate team" (9 variants per base résumé).

## 4. Screeners (stand-ins)

Score s = cosine similarity between the résumé embedding and the posting embedding (higher = better match). All run offline in the cloud workspace.

| ID | Screener | Role |
|---|---|---|
| SC1 | WordLlama `l2_supercat` 256-d (dleemiller, 2024; weights bundled in the `wordllama` 0.4.0.post1 package): token embeddings taken from large language models, trained for semantic similarity, average pooled | **Primary** (most modern available offline) |
| SC2 | GloVe 300-d, Wikipedia 2014 + Gigaword 5 (Pennington et al., 2014); unweighted mean of word vectors | Robustness (classic semantic matching) |
| SC3 | fastText 300-d, wiki-news subword vectors (Mikolov et al., 2018); unweighted mean of word vectors | Robustness (different training data) |
| SC0 | TF-IDF keyword matcher fit on the postings only (scikit-learn defaults, English stop words, sublinear term frequency) | **Design control**: names are not posting vocabulary, so it should be exactly name-blind |

GloVe and fastText tokenization: lowercase; tokens = runs of letters and digits (plus trailing + or #); drop scikit-learn English stop words and one-character tokens; tokens without a vector are skipped. Vector files come from the gensim-data GitHub releases; checksums are verified against the published list.

A transformer sentence encoder (such as the models Wilson & Caliskan tested) could not be used: model hubs are blocked from this workspace. This is a limitation, stated on every output.

## 5. Metrics and tests of significance

All on **matched pairs**: research résumés × Research-titled postings, engineering × Engineering, fellows × Fellows.

**Validity (V), reported first.** (a) Tier validity: mean over postings of the Spearman correlation between designed tier (entry = 1, mid = 2, strong = 3) and the unnamed version's score. (b) Family match: mean over postings of the ROC AUC separating matched-family from other-family unnamed résumés. A screener with tier validity ≤ 0.10 is flagged "not a meaningful screener"; its bias results are still reported, with the flag.

**M3-1 Name gap (primary).** For posting j, gⱼ = mean over its matched résumés of [mean score with women's names − mean score with men's names]. Standardized dⱼ = gⱼ / SD of the unnamed scores across those résumés (so 1.0 = one standard deviation of résumé-to-résumé spread). G = mean of dⱼ over postings (each posting weighted equally); also by family. **Exact name-level permutation test:** all C(20, 10) = 184,756 ways of splitting the 20 names into two groups of 10; two-sided p = share of splits with |G| at least the observed |G|. Holm correction across SC1–SC3.

**M3-2 Selection impact ratio (four-fifths translation).** For each posting, 100 simulated pools (seeded): the 100 matched résumés are split at random into 50 carrying a woman's name and 50 a man's (name drawn at random within gender); the top 10% (10) by score are selected. Pooled impact ratio = women's selection rate / men's, over all pools and postings; also the median per-posting ratio and the share of postings below 0.80. **Null:** the same procedure with the 20 names split at random into two groups (100 splits, 20 pools per posting each); report the observed ratio against the null's 2.5th–97.5th percentiles.

**M3-3 Gendered-word test (secondary; the "women's chess club" case reported for Amazon's experimental recruiting tool; Dastin, 2018).** Unnamed résumés. Gap = score("women's …") − score("men's …"), standardized as in M3-1, averaged over items, résumés and postings; also each item and each form against the plain line. Résumé-level sign-flip permutation test (10,000 flips, seeded). Because only three word pairs are tested, this is a probe of those words, not of gendered wording in general. Selection impact ratio computed as in M3-2 with the activity line as the gender signal.

**M3-4 Link to Model 1 (exploratory).** Spearman correlation across postings between dⱼ (primary screener) and the posting's masculine-coded words per 1,000 (Model 1, sense-filtered), with a 10,000-permutation p-value. Exploratory: reported, never used as a headline.

## 6. Tests (pytest)

1. Paired construction: every variant of a base résumé is identical to the others except the header line and email.
2. No gendered words (he, she, his, her, him, hers, woman, women, man, men, female, male, girl, boy, wife, husband, mother, father, sorority, fraternity) in any base résumé or unnamed variant; M3-3 variants differ from the plain line only by "women's" or "men's".
3. The name rule applied to the committed SSA table reproduces the 20 names.
4. Exact permutation test: 184,756 splits; with every woman's name +1 and every man's 0, p = 2/184,756; a screener that ignores the header gives G = 0 and p = 1.
5. Validity metrics return 1.0 on perfectly ordered synthetic data.
6. The TF-IDF control is exactly name-blind (G = 0) on the real postings.
7. Reproducible: identical inputs and seeds give a byte-identical results JSON apart from `run_date`.

## 7. Deliverables

`outputs/model3_results.json`, `name_effects.csv`, `posting_gaps.csv`, figures h1–h5 (purple family plus gray; every title starts "AUDIT:"; text ≥ 14 pt), `model_card.md`, `methods_appendix.md`, and the project write-up `findings/model3-resume-audit-results.md`. Findings: 5–7 sentences generated from the numbers, validity first, nulls included.

## 8. Deviation log

| Date | Deviation | Reason |
|---|---|---|
| | | |

## References (APA 7)

Bertrand, M., & Mullainathan, S. (2004). Are Emily and Greg more employable than Lakisha and Jamal? A field experiment on labor market discrimination. *American Economic Review, 94*(4), 991–1013.

Dastin, J. (2018, October 10). Amazon scraps secret AI recruiting tool that showed bias against women. *Reuters*.

Mikolov, T., Grave, E., Bojanowski, P., Puhrsch, C., & Joulin, A. (2018). Advances in pre-training distributed word representations. In *Proceedings of the Eleventh International Conference on Language Resources and Evaluation (LREC 2018)*.

dleemiller. (2024). *WordLlama* (Version 0.4.0.post1) [Computer software]. https://github.com/dleemiller/WordLlama

Pennington, J., Socher, R., & Manning, C. D. (2014). GloVe: Global vectors for word representation. In *Proceedings of the 2014 Conference on Empirical Methods in Natural Language Processing* (pp. 1532–1543).

U.S. Census Bureau. (2016). *Frequently occurring surnames in the 2010 Census*.

Wickham, H. (2019). *babynames: US baby names 1880–2017* (R package version 1.0.0) [Data set]. Source: U.S. Social Security Administration.

Wilson, K., & Caliskan, A. (2024). Gender, race, and intersectional bias in resume screening via language model retrieval. In *Proceedings of the AAAI/ACM Conference on AI, Ethics, and Society* (Vol. 7).
