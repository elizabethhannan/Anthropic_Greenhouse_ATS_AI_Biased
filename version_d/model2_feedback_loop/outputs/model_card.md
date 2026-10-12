# Model card: Model 2, screening feedback-loop simulation

**SIMULATION — synthetic applicants; not Anthropic data.** Not a forecast. Format follows Mitchell et al. (2019). Generated from `model2_results.json` (run date 2026-10-11).

## Model details

- **What it is:** a Monte Carlo simulation of a hiring pipeline with a sex-blind logistic-regression screener (L2, C = 1.0) that is retrained every hiring cycle on the outcomes it helped produce, followed by a human interview stage.
- **Developed by:** Elizabeth Hannan (Blue Blazing Media), Version D of the Human-AI Employment Intelligence & Governance study, October 2026; implementation written with Claude.
- **Version:** Model 2, Version D. Code: `version_d/model2_feedback_loop/`. Parameters: `config.yaml` (fixed before any run).
- **Research question:** if a sex-blind screening model is trained on past hiring outcomes and retrained every cycle on the outcomes it helped produce, does a historical gap in women's hiring persist, grow, or fade, and under which assumptions?
- **Thesis link:** Research Thesis Version C 3.0, questions RQ2, RQ4 and RQ5; research layer "Historical feedback loops: Exploratory hypothesis" (unchanged).

## Intended use

- **Primary use:** show how this mechanism behaves under stated assumptions, and which assumptions would have to hold for a screening model to carry a historical gap forward.
- **Primary users:** technical executives and ML researchers reviewing AI-hiring governance.
- **Supports:** the design of stage-level evaluation (impact ratios at screen and interview), and the comparison of mitigation options (proxy removal, reweighing, freezing).

## Out-of-scope uses

- **Any statement about Anthropic's systems, applicants, screening configuration, or future workforce.** No Anthropic applicant, screening, or interview data was used; none is available.
- Forecasting hiring outcomes or workforce composition.
- Decisions about individual candidates.
- Legal determinations of adverse impact.

## Factors

- **Group:** sex is generated as women / men (Bernoulli with pool share p). It is used only to generate applicants, to compute metrics, and, in intervention I2 only, to compute training weights. It is never a screener input (test 5).
- **Swept assumptions:** pool share of women (p), proxy strength (ρ), historical penalty (δ₀, calibrated), interview penalty (δₕ).
- **Calibrations:** C1 benchmark pool, p = 0.203 (U.S. Bureau of Labor Statistics, 2026); C2 larger historical gap, p = 0.3 (illustrative). Both target a 0.178 women's share of cycle-0 hires, the observed engineering share (Dewey & People Data Labs, 2026).

## Metrics

- **Screen impact ratio:** SR(women, shortlist) ÷ SR(men, shortlist). **Interview impact ratio:** [hired women ÷ shortlisted women] ÷ [hired men ÷ shortlisted men]. **Overall impact ratio:** SR(women, hired) ÷ SR(men, hired). Reference threshold 0.80 (Uniform Guidelines on Employee Selection Procedures, 1978).
- **Women's hire share**, **proxy weight** (screener coefficient on standardized x₃), **screen validity** (Spearman correlation of screener score with true qualification).
- Each is summarized over 200 runs per scenario as the median with the 5th–95th percentile range.

## Data

Synthetic only. Each cycle draws 10,000 applicants: sex fᵢ ~ Bernoulli(p); qualification qᵢ ~ N(0, 1), independent of sex; job-relevant signals x₁ = q + ε₁ and x₂ = q + ε₂ (ε ~ N(0, 1.0²)); proxy x₃ = ρ·f + ε₃ (ε₃ ~ N(0, 1)), unrelated to qualification. Cycle 0 hires the top 200 by q + η − δ₀·f (η ~ N(0, 0.7²)). Later cycles shortlist the top 1000 by the screener's score and hire the top 200 of the shortlist by q + η − δₕ·f. Screened-out applicants are labeled 0 (selective labels; Lakkaraju et al., 2017).

Calibrated historical penalties: C1 δ₀ = 0.103 (achieved 0.1778); C2 δ₀ = 0.332 (achieved 0.1782).

## Quantitative results

### Findings

- Null checks held: with no historical penalty (S0) the median screen impact ratio stayed between 0.99 and 1.01 across all 8 cycles under both calibrations (C1, cycle 5: 1.00 (0.87–1.14)), and with no proxy (S3) it stayed between 0.99 and 1.01 even though the interview penalty continued (C2, cycle 5: 1.00 (0.89–1.11)), so in this model a sex-blind screener carries a gap only through a sex-correlated feature (RQ2).
- When interviews were even-handed (S1), the screen-stage gap faded: under the illustrative C2 calibration with ρ = 0.5, the screen impact ratio was 0.97 (0.85–1.09) at cycle 1 and 1.00 (0.90–1.11) by cycle 5 as the screener's proxy weight moved from -0.064 to -0.002; under the benchmark C1 calibration it was 1.00 (0.87–1.12) at cycle 1, indistinguishable from the null (RQ4).
- When the interview penalty continued (S2, C2), retraining kept the gap at the screen, with the screen impact ratio at 0.97 (0.85–1.09) at cycle 1 and 0.97 (0.85–1.08) at cycle 5 and the proxy weight strengthened from -0.064 to -0.105, but most of the gap formed at the interview: the cycle-5 interview impact ratio was 0.62 (0.46–0.82) and the overall impact ratio 0.60 (0.43–0.80) (C1: screen 0.99 (0.86–1.13), overall 0.86 (0.62–1.10)) (RQ4).
- Under C2 at cycle 5, removing the proxy (I1) gave a screen impact ratio of 1.00 (0.89–1.10) and reweighing (I2) 1.00 (0.89–1.10), against 0.97 (0.85–1.08) for the S2 baseline, while freezing the screener after cycle 1 (I3) gave 0.97 (0.85–1.11), essentially unchanged; none of the three changed women's share of hires at cycle 5 (baseline 0.205; interventions 0.205, 0.205, 0.205), because the continuing interview penalty set it, and screen validity stayed at 0.80 (interventions 0.80, 0.80, 0.80) (RQ5).
- Across the S2 sensitivity grid (100 runs per cell, δ₀ calibrated per cell to a 0.178 cycle-0 hire share), the median screen impact ratio fell below 0.80 at cycle 5 only when the proxy strength was ρ = 1.5 and the assumed pool share of women was at least 0.35 (historical penalty δ₀ ≥ 0.45); the most extreme cell (ρ = 1.5, pool share 0.40) was 0.70 (0.58–0.79), while every cell with ρ ≤ 1 stayed at or above 0.82; under S1 (even-handed interviews) every cell's median was at least 0.98 by cycle 5 (RQ2).

### Scenarios (median, 5th–95th percentile; c1 = cycle 1, c5 = cycle 5)

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

### Interventions on S2, cycle 5

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

### Sensitivity grid, S2, median screen impact ratio at cycle 5 (100 runs per cell; bold < 0.80)

| ρ \ p | 0.178 | 0.203 | 0.25 | 0.3 | 0.35 | 0.4 |
|---|---|---|---|---|---|---|
| 0 | 1.01 | 1.01 | 0.99 | 1.00 | 1.00 | 1.01 |
| 0.25 | 1.01 | 1.00 | 0.99 | 0.99 | 0.99 | 0.99 |
| 0.5 | 1.00 | 0.99 | 0.98 | 0.97 | 0.95 | 0.94 |
| 0.75 | 1.00 | 0.98 | 0.97 | 0.94 | 0.90 | 0.87 |
| 1 | 1.00 | 0.97 | 0.94 | 0.89 | 0.85 | 0.82 |
| 1.5 | 1.00 | 0.94 | 0.88 | 0.81 | **0.75** | **0.70** |

### Executive conclusion (Model 2)

The most consequential simulation finding is not that a retrained screening model locks in a historical gap on its own. It is that, under these assumptions, the screen stage carried only a small part of the gap (screen impact ratio 0.97 at cycle 5 under the illustrative C2 calibration, and 0.99 under the benchmark C1 calibration, indistinguishable from parity), and whether the gap persisted depended on the human interview stage: with even-handed interviews the screen gap faded by cycle 5, and with a continuing interview penalty it persisted and the screener's reliance on the proxy grew, while the overall impact ratio stayed near 0.60 under C2 (0.86 under C1). Hire counts alone could not show which stage carried the gap; stage-level selection rates could. This is a statement about a mechanism with synthetic applicants, not about Anthropic's systems, applicants, or workforce, and it leaves the "Historical feedback loops" layer an exploratory hypothesis.

## Ethical considerations

- **Risk of misreading a simulation as evidence.** Every output carries the SIMULATION label; the dashboard keeps it in a separate, purple, tagged section and never in the same chart as observed data.
- **Binary sex.** The simulation generates women and men only. The observed source data records Male / Female / Unknown; Unknown has no analogue here.
- **No real people.** No individual's data was used. The observed inputs are two aggregate shares.
- **Sex as a weight (I2).** Reweighing uses sex to set training weights, never as a feature; any real deployment of this method would need legal review.

## Caveats and recommendations

- Synthetic applicants: every applicant is generated; no Anthropic applicant, screening, or interview data was used, and none is available.
- Equal-qualification assumption A1: qualification q is N(0, 1) for women and men; results would change if qualification distributions differed.
- A single linear proxy (x3) with standardized mean difference ρ; real application materials can encode sex through many correlated, nonlinear features.
- Logistic-regression screener (L2, C = 1.0) trained on hired / not-hired labels; real systems vary (ranking models, LLM-based scorers, recruiter overrides, other label definitions).
- The national benchmark (20.3% of U.S. software developers, 2025) is a workforce share, not a qualified applicant pool; C2's 30% pool share is illustrative.
- No workforce attrition, growth, internal mobility, or advancement is modeled; the simulation covers selection only.
- Results describe a mechanism under stated assumptions, not Anthropic: they say nothing about whether Anthropic uses any screening model, on what inputs, or with what effect.
- Selective labels: screened-out applicants are labeled 0 (Lakkaraju et al., 2017); other label choices (e.g., interview pass) were not explored.
- Pipeline rates (s = 0.10, h = 0.02) and noise levels (σx = 1.0, σi = 0.7) were fixed, not swept; how much the screen matters depends on how selective the shortlist is.
- Monte Carlo spread is wide for single runs (each cycle hires 200 people): 5th–95th percentile bands on the screen impact ratio span roughly ±0.13 around the median, so medians, not single runs, carry the findings.

**Recommendation.** The deciding evidence for the study's question is internal: applicant counts and pass rates by sex at each stage. This simulation shows why: hire counts alone could not show which stage carried a gap.

**Tests:** 11 of 11 test cases passed. Runtime of the full run: 287 s on 2 CPU cores.

## References

Dewey & People Data Labs. (2026). Observed Anthropic starts, April–July 2026 [Unpublished data set extract].

Kamiran, F., & Calders, T. (2012). Data preprocessing techniques for classification without discrimination. Knowledge and Information Systems, 33(1), 1–33.

Lakkaraju, H., Kleinberg, J., Leskovec, J., Ludwig, J., & Mullainathan, S. (2017). The selective labels problem: Evaluating algorithmic predictions in the presence of unobservables. In Proceedings of the 23rd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (pp. 275–284).

Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. In Proceedings of the Conference on Fairness, Accountability, and Transparency (pp. 220–229).

Perdomo, J. C., Zrnic, T., Mendler-Dünner, C., & Hardt, M. (2020). Performative prediction. In Proceedings of the 37th International Conference on Machine Learning (pp. 7599–7609). PMLR.

Raghavan, M., Barocas, S., Kleinberg, J., & Levy, K. (2020). Mitigating bias in algorithmic hiring: Evaluating claims and practices. In Proceedings of the 2020 Conference on Fairness, Accountability, and Transparency (pp. 469–481).

U.S. Bureau of Labor Statistics. (2026). Employed persons by detailed occupation, sex, race, and Hispanic or Latino ethnicity (Labor Force Statistics from the Current Population Survey, Table 11, 2025 annual averages). https://www.bls.gov/cps/cpsaat11.htm

Uniform Guidelines on Employee Selection Procedures, 29 C.F.R. § 1607.4(D) (1978).
