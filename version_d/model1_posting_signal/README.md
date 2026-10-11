# Model 1 — Posting-signal model (T7 linguistic bias · T6 visibility bias)

**OBSERVED MEASUREMENT — posting text; describes wording, not intent.**

Model 1 measures what Anthropic's job postings signal, by role family: gender-coded wording (T7; Gaucher, Friesen, & Kay, 2011) and who postings make visible (T6; only Fellows postings name people). It may claim what postings signal. It may never claim that wording or named people changed who applied or who was hired, or anything about intent.

## Status (2026-10-11)

| Component | Status |
|---|---|
| Pre-registration (`analysis_plan.md`) | **Draft written before any score.** Awaiting family counts, sample titles, and Elizabeth's "go" |
| Word lists | Pinned: gender-decoder @ `7cb4a6d` (52 masculine, 50 feminine, 7 hyphenated stems), vendored verbatim with its MIT license |
| Corpus builder, role families, lexicon, bias tests, visibility, outcome gate | Built and unit-tested |
| Posting corpus (input 1) and named-people list (input 3) | **Not in this repository.** They live in R2 and Elizabeth's PyCharm project; not rebuilt from scraping or memory |
| T7 wording scores, sense audit, convergent check | Not run (waiting for corpus and "go") |
| T6 named-people gender coding | Not run (public self-identification only; person-level codes stay in git-ignored `outputs/private/`) |
| H3 estimability gate | **Run: `estimable: false`** — 4 non-overlapping hire cells (< 10 required); 1 cell with < 10 known-sex hires; both sexes in 3 cells (< 5) |
| Model 1b estimator (applicant-level mechanism test) | **Built and validated on simulated data:** 95% CI coverage of the true β = 0.96 across 200 data sets (target ≥ 0.90). An estimator test, not a result. Template: `templates/applicants_by_posting.csv` |
| Tests | 8 passed, 2 skipped (privacy and full-pipeline reproducibility wait for outputs) |

## Files

| File | Role |
|---|---|
| `analysis_plan.md` | Pre-registration: thesis alignment, hypotheses H1–H3, unit, family rules, exclusions, tests, thresholds, deviation log |
| `config.yaml` | Thresholds, rules, seed 20261011, word-list commit and hash |
| `third_party/gender_decoder/` | Word lists at the pinned commit, license, provenance |
| `build_corpus.py` | HTML stripping, normalization, exact-duplicate removal, latest version per posting, ≥ 50% boilerplate removal, < 150-word exclusion |
| `role_family.py` | Fellows → Research-titled → Engineering → Other, applied in order to titles; Version C mapping for comparison |
| `lexicon.py` | Tokenizer, word-start stem matching, per-1,000 scores, gender-decoder label, keyword-in-context |
| `bias_tests.py` | Permutation tests, bootstrap CIs, Cliff's delta, Holm correction |
| `visibility.py` | Wilson CIs, Unknown bounds, exact binomial and Fisher tests; aggregates only |
| `outcome_link.py` | Non-overlapping hire cells and the H3 estimability gate |
| `model1b_estimator.py` | Binomial GLM with posting-clustered SEs; simulation validation |
| `tests/test_model1.py` | Tests 1–8 from the build prompt |

## Run what exists

```bash
cd version_d/model1_posting_signal
python -m pip install numpy scipy pandas statsmodels pyyaml pytest
python -m pytest -q
python model1b_estimator.py            # estimator test on simulated data
python build_corpus.py --input PATH    # once the corpus file is available
```

## References

Gaucher, D., Friesen, J., & Kay, A. C. (2011). Evidence that gendered wording in job advertisements exists and sustains gender inequality. *Journal of Personality and Social Psychology, 101*(1), 109–128.

Matfield, K. (n.d.). *Gender decoder for job ads* [Computer software]. GitHub. https://github.com/lovedaybrooke/gender-decoder
