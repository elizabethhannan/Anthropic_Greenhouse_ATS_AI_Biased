# Methods appendix: Model 2, screening feedback-loop simulation

**SIMULATION — synthetic applicants; not Anthropic data.** Generated from the result files of the run dated 2026-10-11.

## 1. Model

Hiring cycles t = 0, 1, …, T; each cycle draws a fresh pool of N applicants.

**Applicants.** fᵢ ~ Bernoulli(p) (fᵢ = 1 is a woman); qᵢ ~ N(0, 1) independent of sex (assumption A1); x₁ = q + ε₁, x₂ = q + ε₂, ε ~ N(0, σₓ²); x₃ = ρ·f + ε₃, ε₃ ~ N(0, 1).

**Cycle 0 (history).** Hire the top k = ⌊h·N⌋ by qᵢ + ηᵢ − δ₀·fᵢ, η ~ N(0, σᵢ²). δ₀ is found by Brent's method so that the mean women's share of cycle-0 hires over 50 calibration seeds equals h₀; the same seeds are used at every trial δ (common random numbers), so the objective is deterministic.

**Cycles t ≥ 1.** (1) Train Mₜ: L2-regularized logistic regression (C = 1.0) on standardized [x₁, x₂, x₃] from cycle t − 1, with y = 1 if hired, else 0; screened-out applicants are labeled 0. (2) Screen a new pool: shortlist the top ⌊s·N⌋ by Mₜ's score. (3) Interview: hire the top k of the shortlist by qᵢ + ηᵢ − δₕ·fᵢ. (4) Record metrics.

**Metrics.** SR = selected ÷ applicants for a group at a stage. Screen IR = SR(women, shortlist) ÷ SR(men, shortlist); interview IR = [hired women ÷ shortlisted women] ÷ [hired men ÷ shortlisted men]; overall IR = SR(women, hired) ÷ SR(men, hired); hire share = women among hires; proxy weight = Mₜ's coefficient on standardized x₃; screen validity = Spearman correlation between Mₜ's score and q.

**Interventions (on S2).** I1 removes x₃ from the screener's features. I2 reweighs each cycle's training data with w(s, y) = P(s)·P(y) ÷ P(s, y) so sex and label are independent (Kamiran & Calders, 2012); sex sets weights only. I3 trains the screener once, after cycle 0, and uses it unchanged from cycle 1 on.

## 2. Parameters (fixed before any run)

| Parameter | Symbol | Value | Basis |
|---|---|---|---|
| Applicants per cycle | N | 10000 | assumption |
| Shortlist rate | s | 0.1 | assumption |
| Hire rate | h | 0.02 | assumption (20% of shortlist hired) |
| Hiring cycles | T | 8 | assumption |
| Signal noise | σₓ | 1.0 | assumption |
| Interview noise | σᵢ | 0.7 | assumption |
| Proxy strength (main scenarios) | ρ | 0.5 | assumption; swept 0–1.5 |
| Target cycle-0 hire share (women) | h₀ | 0.178 | observed engineering share (Dewey & People Data Labs, 2026) |
| Pool share, C1 | p | 0.203 | U.S. Bureau of Labor Statistics (2026), software developers, 2025 |
| Pool share, C2 | p | 0.3 | illustrative assumption |
| Screener regularization | C | 1.0 | assumption (scikit-learn convention, L2) |
| Monte Carlo runs per scenario | — | 200 | — |
| Grid runs per cell | — | 100 | — |
| Calibration seeds | — | 50 | common random numbers |
| Calibration tolerance (Brent xtol on δ₀) | — | 0.002 | — |
| Base seed | — | 20261011 | run j uses base seed + j |

## 3. Implementation notes

- Python 3.13.16, NumPy 2.5.3; `numpy.random.default_rng(seed)` only; joblib (loky) parallelism over runs; one BLAS thread per worker.
- Pools are drawn in a fixed order (u, q, ε₁, ε₂, ε₃, η), so runs with the same seed share random numbers across scenarios.
- Calibration seeds are base seed + 1,000,000 + j (j = 0…49), kept apart from run seeds. The tolerance of 0.002 is applied to δ₀ (Brent's `xtol`).
- Cycle 0 does not use the proxy, so δ₀ depends only on p and h₀: within a grid column, δ₀ is the same for every ρ and for S1 and S2.
- Grid cells run 5 cycles (cycles 6–8 cannot affect cycles 1 and 5). Screen validity is not computed in grid runs.
- The grid ran at the full 100 runs per cell; no reduction to 50 was needed.

## 4. Calibration results

| Calibration | Pool share p | Target h₀ | δ₀ | Achieved (calibration seeds) | Brent evaluations | S0 target | S0 δ₀ | S0 achieved |
|---|---|---|---|---|---|---|---|---|
| C1 Benchmark pool | 0.203 | 0.178 | 0.103 | 0.1778 | 9 | 0.203 | 0.013 | 0.203 |
| C2 Larger historical gap (illustrative) | 0.3 | 0.178 | 0.332 | 0.1782 | 9 | 0.3 | -0.003 | 0.3002 |

Out-of-sample check (mean cycle-0 women's hire share over the 200 run seeds, which are not the calibration seeds):

| Calibration | Scenario | Mean cycle-0 women's hire share over the run seeds |
|---|---|---|
| C1 | S0 | 0.1997 |
| C1 | S1 | 0.1734 |
| C1 | S2 | 0.1734 |
| C1 | S3 | 0.1734 |
| C2 | S0 | 0.3026 |
| C2 | S1 | 0.1797 |
| C2 | S2 | 0.1797 |
| C2 | S3 | 0.1797 |

Grid calibration (h₀ = 0.178; identical across ρ within a column):

| Pool share p | δ₀ (h₀ = 0.178) | Achieved cycle-0 share |
|---|---|---|
| 0.178 | 0.0078 | 0.178 |
| 0.203 | 0.1035 | 0.1778 |
| 0.25 | 0.2190 | 0.178 |
| 0.3 | 0.3323 | 0.1782 |
| 0.35 | 0.4455 | 0.1781 |
| 0.4 | 0.5478 | 0.1783 |

## 5. Results

### Findings (generated from the numbers)

- Null checks held: with no historical penalty (S0) the median screen impact ratio stayed between 0.99 and 1.01 across all 8 cycles under both calibrations (C1, cycle 5: 1.00 (0.87–1.14)), and with no proxy (S3) it stayed between 0.99 and 1.01 even though the interview penalty continued (C2, cycle 5: 1.00 (0.89–1.11)), so in this model a sex-blind screener carries a gap only through a sex-correlated feature (RQ2).
- When interviews were even-handed (S1), the screen-stage gap faded: under the illustrative C2 calibration with ρ = 0.5, the screen impact ratio was 0.97 (0.85–1.09) at cycle 1 and 1.00 (0.90–1.11) by cycle 5 as the screener's proxy weight moved from -0.064 to -0.002; under the benchmark C1 calibration it was 1.00 (0.87–1.12) at cycle 1, indistinguishable from the null (RQ4).
- When the interview penalty continued (S2, C2), retraining kept the gap at the screen, with the screen impact ratio at 0.97 (0.85–1.09) at cycle 1 and 0.97 (0.85–1.08) at cycle 5 and the proxy weight strengthened from -0.064 to -0.105, but most of the gap formed at the interview: the cycle-5 interview impact ratio was 0.62 (0.46–0.82) and the overall impact ratio 0.60 (0.43–0.80) (C1: screen 0.99 (0.86–1.13), overall 0.86 (0.62–1.10)) (RQ4).
- Under C2 at cycle 5, removing the proxy (I1) gave a screen impact ratio of 1.00 (0.89–1.10) and reweighing (I2) 1.00 (0.89–1.10), against 0.97 (0.85–1.08) for the S2 baseline, while freezing the screener after cycle 1 (I3) gave 0.97 (0.85–1.11), essentially unchanged; none of the three changed women's share of hires at cycle 5 (baseline 0.205; interventions 0.205, 0.205, 0.205), because the continuing interview penalty set it, and screen validity stayed at 0.80 (interventions 0.80, 0.80, 0.80) (RQ5).
- Across the S2 sensitivity grid (100 runs per cell, δ₀ calibrated per cell to a 0.178 cycle-0 hire share), the median screen impact ratio fell below 0.80 at cycle 5 only when the proxy strength was ρ = 1.5 and the assumed pool share of women was at least 0.35 (historical penalty δ₀ ≥ 0.45); the most extreme cell (ρ = 1.5, pool share 0.40) was 0.70 (0.58–0.79), while every cell with ρ ≤ 1 stayed at or above 0.82; under S1 (even-handed interviews) every cell's median was at least 0.98 by cycle 5 (RQ2).

### Scenarios

| Calib. | Scenario | δ₀ | δₕ | ρ | Screen IR c1 | Screen IR c5 | Overall IR c5 | Interview IR c5 | Women's hire share c5 | Proxy weight c1 → c5 |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | S0 Null check | 0.013 | 0.000 | 0.5 | 1.01 (0.88–1.13) | 1.00 (0.87–1.14) | 1.01 (0.74–1.29) | 1.00 (0.75–1.24) | 0.20 (0.16–0.25) | 0.011 → -0.001 |
| C1 | S1 Historical gap, even-handed interviews | 0.103 | 0.000 | 0.5 | 1.00 (0.87–1.12) | 1.00 (0.87–1.14) | 1.01 (0.74–1.29) | 1.00 (0.75–1.24) | 0.20 (0.16–0.25) | -0.015 → -0.001 |
| C1 | S2 Historical gap continues at interview | 0.103 | 0.103 | 0.5 | 1.00 (0.87–1.12) | 0.99 (0.86–1.13) | 0.86 (0.62–1.10) | 0.87 (0.64–1.08) | 0.18 (0.14–0.22) | -0.015 → -0.029 |
| C1 | S3 No proxy | 0.103 | 0.103 | 0 | 1.00 (0.89–1.12) | 1.00 (0.88–1.13) | 0.87 (0.62–1.10) | 0.87 (0.64–1.07) | 0.18 (0.14–0.22) | 0.005 → 0.000 |
| C2 | S0 Null check | -0.003 | 0.000 | 0.5 | 1.00 (0.89–1.12) | 1.00 (0.89–1.11) | 0.99 (0.80–1.27) | 1.01 (0.79–1.28) | 0.30 (0.26–0.35) | 0.012 → -0.000 |
| C2 | S1 Historical gap, even-handed interviews | 0.332 | 0.000 | 0.5 | 0.97 (0.85–1.09) | 1.00 (0.90–1.11) | 0.99 (0.80–1.27) | 1.01 (0.79–1.27) | 0.30 (0.26–0.35) | -0.064 → -0.002 |
| C2 | S2 Historical gap continues at interview | 0.332 | 0.332 | 0.5 | 0.97 (0.85–1.09) | 0.97 (0.85–1.08) | 0.60 (0.43–0.80) | 0.62 (0.46–0.82) | 0.20 (0.16–0.26) | -0.064 → -0.105 |
| C2 | S3 No proxy | 0.332 | 0.332 | 0 | 1.00 (0.90–1.10) | 1.00 (0.89–1.11) | 0.61 (0.46–0.81) | 0.62 (0.45–0.80) | 0.20 (0.16–0.26) | 0.008 → -0.000 |

### Interventions

| Calib. | Intervention | Screen IR c5 | Women's hire share c5 | Overall IR c5 | Screen validity c5 |
|---|---|---|---|---|---|
| C1 | S2 baseline | 0.99 (0.86–1.13) | 0.18 (0.14–0.22) | 0.86 (0.62–1.10) | 0.80 (0.79–0.81) |
| C1 | I1 Remove the proxy | 0.99 (0.88–1.13) | 0.18 (0.14–0.22) | 0.86 (0.63–1.10) | 0.80 (0.80–0.81) |
| C1 | I2 Reweighing | 1.00 (0.86–1.13) | 0.18 (0.14–0.22) | 0.86 (0.62–1.11) | 0.80 (0.79–0.81) |
| C1 | I3 Freeze the screener | 0.99 (0.85–1.14) | 0.18 (0.14–0.22) | 0.86 (0.63–1.11) | 0.80 (0.79–0.81) |
| C2 | S2 baseline | 0.97 (0.85–1.08) | 0.20 (0.16–0.26) | 0.60 (0.43–0.80) | 0.80 (0.79–0.81) |
| C2 | I1 Remove the proxy | 1.00 (0.89–1.10) | 0.20 (0.16–0.26) | 0.61 (0.46–0.82) | 0.80 (0.80–0.81) |
| C2 | I2 Reweighing | 1.00 (0.89–1.10) | 0.20 (0.16–0.26) | 0.60 (0.45–0.80) | 0.80 (0.79–0.81) |
| C2 | I3 Freeze the screener | 0.97 (0.85–1.11) | 0.20 (0.16–0.26) | 0.60 (0.45–0.81) | 0.80 (0.79–0.81) |

### Sensitivity grids: median screen impact ratio (bold < 0.80)

S2, cycle 1:

| ρ \ p | 0.178 | 0.203 | 0.25 | 0.3 | 0.35 | 0.4 |
|---|---|---|---|---|---|---|
| 0 | 1.00 | 1.01 | 1.00 | 1.00 | 0.99 | 1.00 |
| 0.25 | 1.00 | 1.00 | 0.98 | 0.99 | 0.98 | 0.99 |
| 0.5 | 1.01 | 0.99 | 0.97 | 0.97 | 0.95 | 0.95 |
| 0.75 | 1.00 | 0.98 | 0.95 | 0.93 | 0.91 | 0.89 |
| 1 | 1.00 | 0.96 | 0.93 | 0.90 | 0.85 | 0.83 |
| 1.5 | 1.00 | 0.94 | 0.87 | 0.81 | **0.75** | **0.70** |

S2, cycle 5:

| ρ \ p | 0.178 | 0.203 | 0.25 | 0.3 | 0.35 | 0.4 |
|---|---|---|---|---|---|---|
| 0 | 1.01 | 1.01 | 0.99 | 1.00 | 1.00 | 1.01 |
| 0.25 | 1.01 | 1.00 | 0.99 | 0.99 | 0.99 | 0.99 |
| 0.5 | 1.00 | 0.99 | 0.98 | 0.97 | 0.95 | 0.94 |
| 0.75 | 1.00 | 0.98 | 0.97 | 0.94 | 0.90 | 0.87 |
| 1 | 1.00 | 0.97 | 0.94 | 0.89 | 0.85 | 0.82 |
| 1.5 | 1.00 | 0.94 | 0.88 | 0.81 | **0.75** | **0.70** |

S1, cycle 1:

| ρ \ p | 0.178 | 0.203 | 0.25 | 0.3 | 0.35 | 0.4 |
|---|---|---|---|---|---|---|
| 0 | 1.00 | 1.01 | 1.00 | 1.00 | 0.99 | 1.00 |
| 0.25 | 1.00 | 1.00 | 0.98 | 0.99 | 0.98 | 0.99 |
| 0.5 | 1.01 | 0.99 | 0.97 | 0.97 | 0.95 | 0.95 |
| 0.75 | 1.00 | 0.98 | 0.95 | 0.93 | 0.91 | 0.89 |
| 1 | 1.00 | 0.96 | 0.93 | 0.90 | 0.85 | 0.83 |
| 1.5 | 1.00 | 0.94 | 0.87 | 0.81 | **0.75** | **0.70** |

S1, cycle 5:

| ρ \ p | 0.178 | 0.203 | 0.25 | 0.3 | 0.35 | 0.4 |
|---|---|---|---|---|---|---|
| 0 | 1.00 | 1.01 | 1.00 | 1.00 | 1.00 | 1.00 |
| 0.25 | 1.00 | 1.00 | 0.99 | 1.00 | 1.00 | 1.00 |
| 0.5 | 1.00 | 1.00 | 1.01 | 1.00 | 1.00 | 1.00 |
| 0.75 | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | 0.99 |
| 1 | 1.00 | 1.00 | 1.00 | 0.99 | 0.99 | 0.99 |
| 1.5 | 1.00 | 1.00 | 0.99 | 0.99 | 0.98 | 0.99 |

5th and 95th percentiles for every cell are in `sensitivity_S1.csv` and `sensitivity_S2.csv`.

### Diagnostics (reported, not asserted)

Direction and size of the S1 and S2 effects:

- C1_S1: screen IR c1 0.995 → c5 1.000 (change +0.005); proxy weight -0.015 → -0.001; overall IR c5 1.005; interview IR c5 1.000
- C1_S2: screen IR c1 0.995 → c5 0.993 (change -0.002); proxy weight -0.015 → -0.029; overall IR c5 0.863; interview IR c5 0.870
- C2_S1: screen IR c1 0.973 → c5 1.000 (change +0.027); proxy weight -0.064 → -0.002; overall IR c5 0.994; interview IR c5 1.015
- C2_S2: screen IR c1 0.973 → c5 0.970 (change -0.003); proxy weight -0.064 → -0.105; overall IR c5 0.602; interview IR c5 0.615

Does the median screen impact ratio fall monotonically as ρ rises (within each pool-share column)?

- S1_cycle1: p = 0.178: no, p = 0.203: yes, p = 0.25: yes, p = 0.3: yes, p = 0.35: yes, p = 0.4: yes
- S1_cycle5: p = 0.178: no, p = 0.203: no, p = 0.25: no, p = 0.3: no, p = 0.35: yes, p = 0.4: no
- S2_cycle1: p = 0.178: no, p = 0.203: yes, p = 0.25: yes, p = 0.3: yes, p = 0.35: yes, p = 0.4: yes
- S2_cycle5: p = 0.178: no, p = 0.203: yes, p = 0.25: yes, p = 0.3: yes, p = 0.35: yes, p = 0.4: yes

In the p = 0.178 column the historical penalty is about zero (δ₀ = 0.008), so the values fluctuate around 1 and are not expected to be monotone. Under S1 at cycle 5 the gap has faded in every column, so the same applies.

## 6. Tests

| Suite | Test | Result | Time (s) | Note |
|---|---|---|---|---|
| pytest_default | `test_1_impact_ratio_arithmetic` | passed | 0.0 |  |
| pytest_default | `test_2_calibration_hits_target[C1]` | passed | 0.1 |  |
| pytest_default | `test_2_calibration_hits_target[C2]` | passed | 0.1 |  |
| pytest_default | `test_3_null_scenario_S0[C1]` | passed | 6.1 |  |
| pytest_default | `test_3_null_scenario_S0[C2]` | passed | 4.9 |  |
| pytest_default | `test_4_no_proxy_S3[C1]` | passed | 4.7 |  |
| pytest_default | `test_4_no_proxy_S3[C2]` | passed | 4.6 |  |
| pytest_default | `test_5_sex_never_a_feature` | passed | 0.5 |  |
| pytest_default | `test_6_counts_conserved` | passed | 0.9 |  |
| pytest_default | `test_7_reproducible` | passed | 3.4 |  |
| pytest_full_repro | `test_7_reproducible` | passed | 290.8 |  |

Test 7 runs in two modes: by default a small smoke configuration run twice into temporary folders; with `MODEL2_FULL_REPRO=1`, the full configuration is re-run and compared byte for byte (apart from `run_date`) with `outputs/model2_results.json`.

## 7. Runtime

Full run 287 s on 2 CPU cores: calibration 0.7 s, scenarios 77 s, interventions 47 s, grid 162 s.

## 8. Thesis alignment

| Question | Contribution | Status |
|---|---|---|
| 2. Algorithmic influence: Could AI-assisted screening, candidate matching, or historical hiring patterns reinforce existing demographic disparities? | A sex-blind screener retrained on past outcomes produced a screen impact ratio below 1 only when a sex-correlated proxy existed (S3 without a proxy: 0.99–1.01). With ρ = 0.5 the screen-stage effect was small (C2, S2 cycle 5: 0.97); reaching the four-fifths threshold at the screen required a strong proxy and a large historical gap in the sensitivity grid. | Simulated only; mechanism characterized under stated assumptions; not established for Anthropic |
| 4. Long-term AI risk: Could repeated employment outcomes become feedback signals that lead future AI systems to reproduce historical hiring preferences? | Repeated retraining reproduced the historical pattern only while the human interview stage kept applying the penalty (S2: proxy weight -0.064 → -0.105); with even-handed interviews the screen gap faded by cycle 5 (S1, C2: 0.97 → 1.00). | Exploratory hypothesis — sharpened by simulation, not confirmed |
| 5. Governance: What internal data, evaluation methods, and executive accountability are required to distinguish algorithmic bias from human, structural, and applicant-pool factors? | Removing the proxy (I1) or reweighing training data (I2) restored screen parity (1.00, 1.00) with no measurable loss of screen validity; freezing (I3) did not. Women's share of hires did not move while the interview penalty continued, so stage-level impact ratios, not hire counts, are the evaluation method that separates screen effects from human-stage effects. | Evaluation method specified; requires internal stage-level data to apply |

## References

Dewey & People Data Labs. (2026). Observed Anthropic starts, April–July 2026 [Unpublished data set extract].

Kamiran, F., & Calders, T. (2012). Data preprocessing techniques for classification without discrimination. Knowledge and Information Systems, 33(1), 1–33.

Lakkaraju, H., Kleinberg, J., Leskovec, J., Ludwig, J., & Mullainathan, S. (2017). The selective labels problem: Evaluating algorithmic predictions in the presence of unobservables. In Proceedings of the 23rd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (pp. 275–284).

Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. In Proceedings of the Conference on Fairness, Accountability, and Transparency (pp. 220–229).

Perdomo, J. C., Zrnic, T., Mendler-Dünner, C., & Hardt, M. (2020). Performative prediction. In Proceedings of the 37th International Conference on Machine Learning (pp. 7599–7609). PMLR.

Raghavan, M., Barocas, S., Kleinberg, J., & Levy, K. (2020). Mitigating bias in algorithmic hiring: Evaluating claims and practices. In Proceedings of the 2020 Conference on Fairness, Accountability, and Transparency (pp. 469–481).

U.S. Bureau of Labor Statistics. (2026). Employed persons by detailed occupation, sex, race, and Hispanic or Latino ethnicity (Labor Force Statistics from the Current Population Survey, Table 11, 2025 annual averages). https://www.bls.gov/cps/cpsaat11.htm

Uniform Guidelines on Employee Selection Procedures, 29 C.F.R. § 1607.4(D) (1978).
