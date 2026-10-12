# Model 2 v1.1 plan (pre-registration)

**Status:** written 2026-10-11, before any v1.1 code was run. Awaiting Elizabeth's **"go"**. v1.0 (`version_d/model2_feedback_loop/`) is not modified; this folder is a copy, and the v1.0 test suite passed on the copy (10 of 10) before any change.

**Label on every output:** SIMULATION — synthetic applicants; not Anthropic data. Never a forecast.

## 1. Thesis alignment

| ID | Reviewer challenge | Extension | Questions served |
|---|---|---|---|
| X1 | Interviewers see the screen score; if they lean on it, the proxy reaches hires and the next labels | Interviewer reliance on the screen score | RQ2, RQ3, RQ4 |
| X2 | The model never sees outcomes for people it screened out | Exploration: interview a random share of screened-out applicants (I4) | RQ5 |
| X3 | Real screeners aren't linear | Gradient-boosted screener | RQ2 |
| X4 | The proxy may carry real job signal | Partly job-relevant proxy; cost of each fix | RQ5 |
| X5 | Systems retrain on all history | Cumulative training window | RQ4 |
| P1 | How much data would Anthropic need to see any of this? | Detection-power table (minimum instrumentation spec) | RQ5 |

Research layers do not change: "Historical feedback loops: Exploratory hypothesis" (sharpened, never confirmed); "Algorithmic causation: Not established"; "Predictive ML analysis: Not estimable from public data".

## 2. Inherited defaults

All v1.0 defaults and integrity rules: N = 10,000 applicants per cycle; shortlist 10% (1,000); hire 2% (200); 8 cycles; σₓ = 1.0; σᵢ = 0.7; ρ = 0.5; h₀ = 0.178; base seed 20261011 (run j = seed + j); L2 logistic regression (C = 1.0); calibrations C1 (pool 20.3%, δ₀ = 0.1035) and C2 (pool 30%, illustrative, δ₀ = 0.3323), recalibrated by the same code; scenarios S1 (even-handed interviews, δₕ = 0) and S2 (interview penalty continues, δₕ = δ₀). 200 runs per configuration, except X3 (100). Sex is never a screener feature.

## 3. Extensions (parameters fixed now)

**X1, interviewer reliance.** The interview ranks the shortlist by score = (1 − w)·z(q + η − δₕ·f) + w·z(screen score), where z standardizes within the shortlist and the screen score is the screener's decision function. w ∈ {0, 0.25, 0.5, 0.75}. Configurations: every w × {S1, S2} × {C1, C2} = 16. All metrics by cycle. Key question: under S1, does reliance stop the screen gap from fading? At w = 0 the ranking is identical to v1.0 (z is a monotone transform).

**X2, exploration (I4).** Each cycle, a random ε·N of the screened-out applicants (ε ∈ {0.01, 0.05}: 100 or 500 people) joins the interview pool; k = 200 hires are made from shortlist ∪ explored by the same interview rule. Training labels keep the v1.0 definition (every applicant of the previous cycle; label = hired), so explored applicants who are hired enter the labels as positives. The exploration draw uses a separate random stream (seeded from the run seed) so the applicant draws match v1.0. Configurations: ε × {S1, S2} × C2 = 4. Reported: proxy weight, screen impact ratio, screen validity, women's hire share, extra interviews per cycle (= ε·N).

**X3, gradient-boosted screener.** `HistGradientBoostingClassifier` with scikit-learn defaults and `random_state` = run seed. Configurations: S0, S1, S2 under C1 and C2, plus I1 (remove proxy) and I2 (reweighing, as sample weights) under S2, C1 and C2 = 10, 100 runs each. proxy_signal = permutation importance of x₃: mean drop in ROC AUC over 5 shuffles of x₃ on a seeded random 2,000-row subsample of that cycle's training data (a subsample keeps runtime within budget).

**X4, partly job-relevant proxy.** x₃ = ρ·f + λ·q + ε₃, λ ∈ {0, 0.3, 0.6} (same ε₃ draw as v1.0, so λ = 0 reproduces v1.0). Configurations: λ × {S2 baseline, I1, I2} under C2 = 9. Reported: screen impact ratio and screen validity for each (the price of each fix when the proxy carries real signal), plus women's hire share.

**X5, cumulative training window.** Each cycle the screener trains on all cycles so far (cycle 0 through t − 1, concatenated; standardization refit each cycle) instead of the last cycle only. Configurations: {S1, S2} × {C1, C2} = 4. Key question: does memory of history slow the fading seen in v1.0's S1?

**P1, detection power.** A role family with A applicants in a reporting period; A ∈ {250, 500, 1,000, 2,000, 5,000, 10,000}; pool share p ∈ {0.203, 0.30}; true impact ratio r ∈ {0.97, 0.86, 0.80, 0.62, 0.60} (values from v1.0's simulation). Two stages:
- screen: at risk = applicants; stage pass rate 10%;
- interview: at risk = the shortlisted, ⌊0.10·A⌋ people, women drawn Binomial(⌊0.10·A⌋, p) (an even-handed screen); stage pass rate 20% (200 of 1,000).
Within a stage, men's selection rate s_m = s / (p·r + 1 − p) and women's = r·s_m, so the overall pass rate equals s. Each replicate draws women ~ Binomial(at-risk, p), then selected women and men as binomials. 2,000 replicates per cell, seed 20261011. Report (a) power of a two-sided Fisher's exact test at α = .05; (b) the probability that the observed impact ratio falls below 0.80 (an undefined ratio counts as not below, and is counted); and the minimum A in the grid reaching 80% power, else "> 10,000". State whether interview-stage effects need pooling across periods or role families.

## 4. Metrics

As v1.0 (screen, interview and overall impact ratios; women's hire share; screen validity), plus proxy_signal (coefficient on standardized x₃ for logistic screeners; permutation importance for X3) and extra_interviews_per_cycle (0 except X2). Monte Carlo summaries: median and 5th/95th percentiles by cycle.

## 5. Tests (pytest)

1. Regression to v1.0: with w = 0, ε = 0, logistic, λ = 0 and a last-cycle window, v1.1 reproduces v1.0's S0–S3 metrics under C1 and C2 for the same seeds exactly (compared with v1.0's `model2_results.json`).
2. X1 null: under S0, every w keeps the median screen and overall impact ratios within [0.95, 1.05] (C1 and C2, 100 runs).
3. X3 null: under S0 and S3, the boosted screener's median screen impact ratio stays within [0.95, 1.05] (C1 and C2, 50 runs).
4. X2 accounting: each cycle interviews exactly ⌊0.10·N⌋ + ⌊ε·N⌋ applicants and hires exactly ⌊0.02·N⌋.
5. P1 calibration: with r = 1.0, the rejection rate is between 0.02 and 0.05 for the screen stage at A ∈ {1,000; 5,000} and p ∈ {0.203, 0.30} (2,000 replicates each).
6. Sex never a feature in any screener, including the boosted one.
7. Reproducible: identical config and seed give byte-identical results JSON apart from `run_date`.

## 6. Runtime rule

Target under 30 minutes on this workspace's 2 cores. Before the full run, a timing pilot (5 runs per extension, results discarded) projects the total; if it exceeds 30 minutes, X1, X2, X4 and X5 drop to 100 runs per configuration and the appendix records it. X3 stays at 100.

## 7. Deliverables

`outputs/model2_v1_1_results.json` (schema in the prompt; extra keys allowed), `power_table.csv`, figures g1–g6 (purple family plus a neutral gray; titles start "SIMULATION:"; text ≥ 14 pt), `model_card_v1_1.md`, `methods_appendix_v1_1.md`, `dashboard_patch_v1_1.md` (E4 reliance, E5 minimum instrumentation), and the project write-up `findings/model2-v1-1-results.md`. Findings: 5–7 sentences with medians and 5th–95th ranges, X1 and P1 first, nulls included.

## 8. Deviation log

| Date | Deviation | Reason |
|---|---|---|
| | | |

## References (APA 7)

Goddard, K., Roudsari, A., & Wyatt, J. C. (2012). Automation bias: A systematic review of frequency, effect mediators, and mitigators. *Journal of the American Medical Informatics Association, 19*(1), 121–127.

Kamiran, F., & Calders, T. (2012). Data preprocessing techniques for classification without discrimination. *Knowledge and Information Systems, 33*(1), 1–33.

Kilbertus, N., Gomez-Rodriguez, M., Schölkopf, B., Muandet, K., & Valera, I. (2020). Fair decisions despite imperfect predictions. In *Proceedings of the 23rd International Conference on Artificial Intelligence and Statistics* (pp. 277–287). PMLR.

Lakkaraju, H., Kleinberg, J., Leskovec, J., Ludwig, J., & Mullainathan, S. (2017). The selective labels problem: Evaluating algorithmic predictions in the presence of unobservables. In *Proceedings of the 23rd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (pp. 275–284).

Parasuraman, R., & Manzey, D. H. (2010). Complacency and bias in human use of automation: An attentional integration. *Human Factors, 52*(3), 381–410.

Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research, 12*, 2825–2830.

Uniform Guidelines on Employee Selection Procedures, 29 C.F.R. § 1607.4(D) (1978).
