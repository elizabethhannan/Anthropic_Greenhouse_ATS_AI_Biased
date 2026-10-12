# Model card addendum: Model 2 v1.1 (human-AI reliance and robustness pack)

**SIMULATION — synthetic applicants; not Anthropic data.** Never a forecast. Version 1.1 (base 1.0), run 2026-10-11. Pre-registration: `v1_1_plan.md`. This addendum extends the v1.0 card (`../model2_feedback_loop/outputs/model_card.md`); everything there still applies.

## What changed in v1.1

| ID | Extension | Question |
|---|---|---|
| X1 | Interviewer reliance on the screen score | RQ2, RQ3, RQ4 |
| X2 | Exploration: interview a random share of screened-out applicants (I4) | RQ5 |
| X3 | Gradient-boosted screener | RQ2 |
| X4 | Partly job-relevant proxy; cost of each fix | RQ5 |
| X5 | Cumulative training window | RQ4 |
| P1 | Detection power (minimum instrumentation spec) | RQ5 |

- Screeners: L2 logistic regression (C = 1.0) as in v1.0; X3 adds scikit-learn `HistGradientBoostingClassifier` with defaults. Sex is never a feature in either (checked on every run: True).
- Regression check: with every extension switched off, v1.1 reproduced v1.0 exactly in 14 of 14 configurations (matches: True).
- Runs per configuration: regression 200, X3 100, X1/X2/X4/X5 100 (reduced from 200 by the pre-registered runtime rule; pilot projected 36.2 minutes).

## Findings

- (RQ3, RQ4) With even-handed interviewers (S1, C2), leaning on the AI score did not keep the screen gap alive: the cycle-8 screen impact ratio was 1.00 (0.88–1.15) with no reliance and 0.98 (0.88–1.11) at w = 0.75 (a null result); reliance did keep the model's learned proxy weight from fading (-0.18 (-0.51 to 0.35) vs. 0.00 (-0.13 to 0.16) without reliance), but too little to move the screen ratio.
- (RQ2, RQ3) With a continuing interview penalty (S2, C2), reliance moved the bias from people into the model: the cycle-8 overall impact ratio rose from 0.57 (0.42–0.84) at w = 0 to 0.90 (0.67–1.17) at w = 0.75 because the interviewer's penalty was diluted, while the screener's proxy weight grew from -0.10 (-0.30 to 0.04) to -0.38 (-0.74 to 0.20).
- (RQ5) Detecting an interview-stage gap of the simulated size (true ratio 0.62) with 80% power took 10,000 applicants per role family per reporting period when women were 30% of applicants (power 0.89 at 10,000) and > 10,000 at 20.3% (power 0.76 at 10,000); the same gap at the screen needed 2,000–5,000, and at 250 applicants an observed ratio fell below 0.80 in 34%–36% of periods even when the true ratio was 0.97; interview-stage audits therefore need pooling across periods or role families.
- (RQ2) A gradient-boosted screener carried the same small screen gap as logistic regression (C2, S2, cycle 5: 0.98 (0.88–1.10) vs. 0.97 (0.87–1.06), same seeds) and the same large overall gap (0.61 vs. 0.60), kept the S0 null within 0.95–1.05, and ranked applicants less accurately (validity 0.58 vs. 0.80), so the v1.0 result does not depend on the screener being linear.
- (RQ5) Interviewing 1% or 5% of screened-out applicants (100 or 500 extra interviews per cycle) left the proxy weight unchanged under S2 (cycle 8: -0.11 (-0.31 to 0.04) and -0.10 (-0.27 to 0.06) vs. -0.10 (-0.30 to 0.04) without exploration); a null result: exploration fills in missing labels but not labels made by a biased interview.
- (RQ5) When the proxy also carried job signal (λ = 0.6), the uncorrected screener favored the group with higher proxy scores (screen ratio 1.16 (1.03–1.26), validity 0.823); removing the proxy restored 1.00 (0.90–1.10) at a validity cost of 0.020, reweighing kept validity but not parity (1.19), and no fix moved women's hire share outside 0.20–0.21 while the interview penalty continued.
- (RQ4) Training on all past cycles slowed the fading modestly: under S1 (C2) the proxy weight at cycle 8 was -0.03 (-0.10 to 0.04) versus 0.00 (-0.13 to 0.16) with the last cycle only, and the screen ratio 0.99 versus 1.00.

## Executive conclusion

The most consequential finding is not that the screening model carries the historical gap; in every variant it carried only a small part of it. It is that how people use the model decides where the gap lives. When interviewers lean on the AI score, a continuing human penalty is diluted in today's hires but absorbed into the model's weights for tomorrow's, and a four-fifths check of one role family in one reporting period is too small to see an interview-stage gap of this size. Responsible governance therefore needs stage-level data pooled across periods, a record of how much decision-makers rely on model scores, and audits of the model's learned weights over time, not hire counts alone. None of this establishes algorithmic causation at Anthropic; the "Historical feedback loops" layer remains an exploratory hypothesis.

## Thesis alignment

- **RQ2** — The screen carried only a small part of the gap with a linear or a boosted screener; reliance on the screen score made the model learn more of the historical gap. *Status: Simulated only; algorithmic causation not established.*
- **RQ3** — The interview stage still decided whether the gap persisted; how much interviewers lean on the AI score changed where the gap lived, not whether it existed. *Status: Sharpened (simulation).*
- **RQ4** — Retraining on all history and reliance on model scores both slowed or deepened the model's learned proxy weight; outcomes fed back only while a human penalty continued. *Status: Exploratory hypothesis, sharpened, not confirmed.*
- **RQ5** — Minimum instrumentation: stage-level counts per role family, pooled across periods for interview-stage audits; a record of reliance on model scores; exploration alone is not a fix. *Status: Specified; requires internal data.*

Research layers unchanged: "Historical feedback loops: Exploratory hypothesis"; "Algorithmic causation: Not established"; "Predictive ML analysis: Not estimable from public data".

## Limitations

- Synthetic applicants; nothing here describes Anthropic.
- Equal-qualification assumption kept: women and men have the same qualification distribution. A qualification-shift sensitivity was deliberately not run.
- Reliance is a fixed weight w, not learned or varying behavior.
- One proxy, with a fixed correlation with sex; real screeners see many correlated signals.
- No attrition, promotion or workforce stock is modeled; outcomes are hires per cycle.
- The boosted screener uses scikit-learn defaults without tuning; permutation importance is measured on a 2,000-row subsample.
- By the pre-registered runtime rule (the timing pilot projected 36.2 minutes, over the 30-minute target), X1, X2, X4 and X5 used 100 runs per configuration; X3 used 100; the regression check used 200.
- Tests 2 and 5 each failed in one cell by Monte Carlo margins (see the methods appendix); they were not edited.

## Tests

12 of 15 passed. Failures are reported, not edited; see the methods appendix.

## References (APA 7)

Goddard, K., Roudsari, A., & Wyatt, J. C. (2012). Automation bias: A systematic review of frequency, effect mediators, and mitigators. *Journal of the American Medical Informatics Association, 19*(1), 121–127.

Kamiran, F., & Calders, T. (2012). Data preprocessing techniques for classification without discrimination. *Knowledge and Information Systems, 33*(1), 1–33.

Kilbertus, N., Gomez-Rodriguez, M., Schölkopf, B., Muandet, K., & Valera, I. (2020). Fair decisions despite imperfect predictions. In *Proceedings of the 23rd International Conference on Artificial Intelligence and Statistics* (pp. 277–287). PMLR.

Lakkaraju, H., Kleinberg, J., Leskovec, J., Ludwig, J., & Mullainathan, S. (2017). The selective labels problem: Evaluating algorithmic predictions in the presence of unobservables. In *Proceedings of the 23rd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (pp. 275–284).

Parasuraman, R., & Manzey, D. H. (2010). Complacency and bias in human use of automation: An attentional integration. *Human Factors, 52*(3), 381–410.

Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research, 12*, 2825–2830.

Uniform Guidelines on Employee Selection Procedures, 29 C.F.R. § 1607.4(D) (1978).
