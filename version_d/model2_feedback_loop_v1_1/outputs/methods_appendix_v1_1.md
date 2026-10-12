# Methods appendix: Model 2 v1.1

**SIMULATION — synthetic applicants; not Anthropic data.** Run 2026-10-11.

## 1. Equations

All v1.0 equations hold (`../model2_feedback_loop/outputs/methods_appendix.md`). Additions:

- **X1 reliance.** Interview score = (1 − w)·z(q + η − δₕ·f) + w·z(s), z standardized within the interviewed set, s = the screener's decision function; w ∈ [0, 0.25, 0.5, 0.75]. At w = 0 the raw v1.0 score is used, so the ranking is identical.
- **X2 exploration.** Each cycle ⌊ε·N⌋ screened-out applicants (ε ∈ [0.01, 0.05]) are drawn at random from a separate stream seeded from the run seed and interviewed with the shortlist; k hires are made from the union. Labels keep the v1.0 definition (hired = 1 among all applicants of the previous cycle). Interview impact ratio uses the interviewed set as denominator.
- **X3 boosted screener.** `HistGradientBoostingClassifier(random_state = run seed)`, defaults otherwise (100 iterations, no early stopping at N = 10,000). Proxy signal = mean drop in ROC AUC over 5 shuffles of x₃ on a seeded 2,000-row subsample of that cycle's training data. Logistic comparisons use the regression runs with the same seeds.
- **X4 proxy relevance.** x₃ = ρ·f + λ·q + ε₃, λ ∈ [0, 0.3, 0.6], same ε₃ draw as v1.0.
- **X5 cumulative window.** Training data = all cycles 0 … t − 1 concatenated; standardization refit each cycle.
- **P1 power.** Stage pass rate s, pool share p, true ratio r: men's rate s/(p·r + 1 − p), women's r times that. Women at risk ~ Binomial(at-risk, p); selections binomial. Screen at-risk = A (s = 0.1); interview at-risk = ⌊0.10·A⌋ (s = 0.2). 2,000 replicates per cell; two-sided Fisher's exact test at α = 0.05; an undefined observed ratio counts as "not below 0.80".

## 2. Parameters

N = 10,000; shortlist 10%; hire 2%; T = 8; σₓ = 1.0; σᵢ = 0.7; ρ = 0.5; h₀ = 0.178; base seed 20261011. C1 pool 0.203 (δ₀ = 0.1035); C2 pool 0.3, illustrative (δ₀ = 0.3323).

## 3. X1 at cycle 8 (median, 5th–95th for overall ratio)

| Calibration | Scenario | w | Overall impact ratio | Screen impact ratio | Women's hire share | Proxy weight |
|---|---|---|---|---|---|---|
| C1 | S1 | 0 | 1.01 (0.73–1.32) | 1.01 | 0.200 | +0.004 |
| C1 | S1 | 0.25 | 0.97 (0.71–1.35) | 1.01 | 0.200 | +0.004 |
| C1 | S1 | 0.5 | 1.00 (0.74–1.25) | 1.01 | 0.203 | +0.007 |
| C1 | S1 | 0.75 | 1.00 (0.73–1.32) | 1.00 | 0.203 | -0.058 |
| C1 | S2 | 0 | 0.84 (0.63–1.19) | 0.99 | 0.175 | -0.025 |
| C1 | S2 | 0.25 | 0.86 (0.61–1.18) | 1.00 | 0.180 | -0.050 |
| C1 | S2 | 0.5 | 0.90 (0.65–1.16) | 1.00 | 0.190 | -0.046 |
| C1 | S2 | 0.75 | 0.96 (0.71–1.28) | 1.00 | 0.195 | -0.100 |
| C2 | S1 | 0 | 0.98 (0.72–1.33) | 1.00 | 0.295 | +0.003 |
| C2 | S1 | 0.25 | 0.98 (0.75–1.31) | 1.00 | 0.295 | +0.010 |
| C2 | S1 | 0.5 | 0.99 (0.74–1.33) | 1.00 | 0.300 | -0.012 |
| C2 | S1 | 0.75 | 1.02 (0.78–1.33) | 0.98 | 0.300 | -0.181 |
| C2 | S2 | 0 | 0.57 (0.42–0.84) | 0.96 | 0.195 | -0.098 |
| C2 | S2 | 0.25 | 0.66 (0.45–0.89) | 0.96 | 0.220 | -0.125 |
| C2 | S2 | 0.5 | 0.76 (0.55–1.02) | 0.97 | 0.245 | -0.218 |
| C2 | S2 | 0.75 | 0.90 (0.67–1.17) | 0.96 | 0.278 | -0.379 |

## 4. P1 power table

| Stage | Pool share | True ratio | Min. applicants for 80% | A = 250 | A = 500 | A = 1,000 | A = 2,000 | A = 5,000 | A = 10,000 |
|---|---|---|---|---|---|---|---|---|---|
| screen | 0.203 | 0.97 | > 10,000 | 0.03 | 0.04 | 0.05 | 0.05 | 0.05 | 0.07 |
| screen | 0.203 | 0.86 | > 10,000 | 0.03 | 0.05 | 0.07 | 0.13 | 0.26 | 0.48 |
| screen | 0.203 | 0.8 | 10000 | 0.04 | 0.07 | 0.12 | 0.21 | 0.50 | 0.83 |
| screen | 0.203 | 0.62 | 5000 | 0.06 | 0.19 | 0.39 | 0.71 | 0.99 | 1.00 |
| screen | 0.203 | 0.6 | 5000 | 0.08 | 0.22 | 0.44 | 0.76 | 0.99 | 1.00 |
| screen | 0.3 | 0.97 | > 10,000 | 0.04 | 0.04 | 0.05 | 0.04 | 0.05 | 0.07 |
| screen | 0.3 | 0.86 | > 10,000 | 0.04 | 0.06 | 0.10 | 0.15 | 0.34 | 0.61 |
| screen | 0.3 | 0.8 | 10000 | 0.06 | 0.08 | 0.15 | 0.29 | 0.64 | 0.91 |
| screen | 0.3 | 0.62 | 2000 | 0.14 | 0.28 | 0.54 | 0.86 | 1.00 | 1.00 |
| screen | 0.3 | 0.6 | 2000 | 0.15 | 0.32 | 0.60 | 0.88 | 1.00 | 1.00 |
| interview | 0.203 | 0.97 | > 10,000 | 0.01 | 0.03 | 0.03 | 0.04 | 0.05 | 0.05 |
| interview | 0.203 | 0.86 | > 10,000 | 0.01 | 0.02 | 0.03 | 0.05 | 0.07 | 0.12 |
| interview | 0.203 | 0.8 | > 10,000 | 0.01 | 0.01 | 0.03 | 0.06 | 0.14 | 0.24 |
| interview | 0.203 | 0.62 | > 10,000 | 0.01 | 0.02 | 0.07 | 0.18 | 0.42 | 0.76 |
| interview | 0.203 | 0.6 | 10000 | 0.00 | 0.03 | 0.08 | 0.18 | 0.49 | 0.82 |
| interview | 0.3 | 0.97 | > 10,000 | 0.02 | 0.03 | 0.03 | 0.04 | 0.05 | 0.05 |
| interview | 0.3 | 0.86 | > 10,000 | 0.01 | 0.03 | 0.04 | 0.06 | 0.09 | 0.17 |
| interview | 0.3 | 0.8 | > 10,000 | 0.01 | 0.03 | 0.06 | 0.08 | 0.16 | 0.33 |
| interview | 0.3 | 0.62 | 10000 | 0.01 | 0.05 | 0.12 | 0.24 | 0.59 | 0.89 |
| interview | 0.3 | 0.6 | 10000 | 0.01 | 0.06 | 0.13 | 0.25 | 0.63 | 0.91 |

Interview-stage gaps of the simulated size need pooling across periods or role families unless a role family has about 10,000 applicants per period. Full table, including P(observed ratio < 0.80): `power_table.csv`.

## 5. Tests

| Test | Result | Message |
|---|---|---|
| test_1_regression_to_v1_0 | passed |  |
| test_2_x1_null_under_S0[C1] | FAILED | AssertionError: ('C1', 0.75, 'overall_impact_ratio', array([1.03145814, 1.03214389, 1.00064737, 0.92762071, 1.01427768, |
| test_2_x1_null_under_S0[C2] | FAILED | AssertionError: ('C2', 0.75, 'overall_impact_ratio', array([1.0005933 , 1.01659809, 1.0117696 , 0.93803006, 0.98227272, |
| test_3_x3_null[S0-C1] | passed |  |
| test_3_x3_null[S0-C2] | passed |  |
| test_3_x3_null[S3-C1] | passed |  |
| test_3_x3_null[S3-C2] | passed |  |
| test_4_x2_accounting[0.01] | passed |  |
| test_4_x2_accounting[0.05] | passed |  |
| test_5_p1_calibration[0.203-1000] | passed |  |
| test_5_p1_calibration[0.203-5000] | FAILED | AssertionError: 0.051 |
| test_5_p1_calibration[0.3-1000] | passed |  |
| test_5_p1_calibration[0.3-5000] | passed |  |
| test_6_sex_never_a_feature | passed |  |
| test_7_reproducible | passed |  |

**Test 2 (X1 null) failed at one point, in both calibrations.** Under S0 at w = 0.75, the median overall impact ratio at cycle 4 was 0.928 (C1) and 0.938 (C2) against a band of 0.95–1.05; every other cycle and every other w passed. A post-hoc diagnostic with 400 runs (`diagnostic_test2.py`, output `diagnostic_test2.json`; no parameter changed) gave cycle-4 medians of 0.966 (C1) and 0.975 (C2); all medians were within the band (True), the mean log ratio ranged from -0.035 to -0.001, and the run-to-run SD of the overall ratio was 0.15–0.19. Reading: Monte Carlo noise, widened by reliance. The C1 and C2 failures share seeds, so they are not independent.

**Test 5 (P1 calibration) failed in one of four cells.** With r = 1.0, the screen-stage rejection rate at A = 5,000, p = 0.203 was 0.051 against a cap of 0.05. The Monte Carlo standard error at 2,000 replicates is about 0.005, so this is within noise of the nominal rate; Fisher's exact test is close to nominal at large A.

Neither test was edited.

**Pre-registration scope.** `v1_1_plan.md` was committed (27a28e9) before any v1.1 code existed. `config_v1_1.yaml`, the v1.1 code and the test file were written after the plan and before the runs, and were committed together with the results; their values match the plan.

## 6. Runtime

Pilot projected 36.2 minutes at full runs (by part: REG 3.16, X1 3.08, X2 0.65, X3 22.15, X4 1.52, X5 1.6, P1 4.04), over the 30-minute target, so X1, X2, X4 and X5 dropped to 100 runs as pre-registered. Actual: 28.92 minutes on 2 cores (by part: REG 1.84, X1 1.19, X2 0.28, X3 20.26, X4 0.68, X5 0.69, P1 2.6). Python 3.13.16, NumPy 2.5.3, scikit-learn 1.9.1.

## References (APA 7)

Goddard, K., Roudsari, A., & Wyatt, J. C. (2012). Automation bias: A systematic review of frequency, effect mediators, and mitigators. *Journal of the American Medical Informatics Association, 19*(1), 121–127.

Kamiran, F., & Calders, T. (2012). Data preprocessing techniques for classification without discrimination. *Knowledge and Information Systems, 33*(1), 1–33.

Kilbertus, N., Gomez-Rodriguez, M., Schölkopf, B., Muandet, K., & Valera, I. (2020). Fair decisions despite imperfect predictions. In *Proceedings of the 23rd International Conference on Artificial Intelligence and Statistics* (pp. 277–287). PMLR.

Lakkaraju, H., Kleinberg, J., Leskovec, J., Ludwig, J., & Mullainathan, S. (2017). The selective labels problem: Evaluating algorithmic predictions in the presence of unobservables. In *Proceedings of the 23rd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (pp. 275–284).

Parasuraman, R., & Manzey, D. H. (2010). Complacency and bias in human use of automation: An attentional integration. *Human Factors, 52*(3), 381–410.

Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research, 12*, 2825–2830.

Uniform Guidelines on Employee Selection Procedures, 29 C.F.R. § 1607.4(D) (1978).
