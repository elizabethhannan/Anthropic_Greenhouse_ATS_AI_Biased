# Model 2 v1.1 — Human-AI reliance and robustness pack

**SIMULATION — synthetic applicants; not Anthropic data.** Never a forecast.

v1.1 extends the v1.0 screening feedback-loop simulation (`../model2_feedback_loop/`, unchanged) with five reviewer challenges and a detection-power table. Everything was pre-registered in [`v1_1_plan.md`](v1_1_plan.md) before any v1.1 run.

| ID | Extension | Questions |
|---|---|---|
| X1 | Interviewer reliance on the AI screen score | RQ2, RQ3, RQ4 |
| X2 | Exploration: interview a random share of screened-out applicants | RQ5 |
| X3 | Gradient-boosted screener (`HistGradientBoostingClassifier`) vs. logistic regression | RQ2 |
| X4 | Proxy that partly carries job signal; cost of each fix | RQ5 |
| X5 | Training on all past cycles | RQ4 |
| P1 | Applicants needed to detect a gap (minimum instrumentation) | RQ5 |

- Results: [`outputs/model2_v1_1_results.json`](outputs/model2_v1_1_results.json), [`outputs/power_table.csv`](outputs/power_table.csv)
- Model card addendum: [`outputs/model_card_v1_1.md`](outputs/model_card_v1_1.md)
- Methods appendix: [`outputs/methods_appendix_v1_1.md`](outputs/methods_appendix_v1_1.md)
- Figures g1–g6: [`outputs/figures/`](outputs/figures/)
- Dashboard patch (written, **not applied**; Replit updates paused): [`outputs/dashboard_patch_v1_1.md`](outputs/dashboard_patch_v1_1.md)

## Files

| File | Role |
|---|---|
| `config.yaml`, `simulate.py`, `calibrate.py`, `metrics.py`, `run_experiments.py`, `findings.py`, `make_figures.py`, `write_docs.py`, `tests/test_model2.py` | Unchanged copy of v1.0 (v1.0 tests pass on the copy) |
| `config_v1_1.yaml` | v1.1 parameters, fixed in the plan |
| `simulate_v11.py` | v1.1 core: reliance, exploration, boosted screener, proxy relevance, cumulative window |
| `power.py` | P1 detection-power Monte Carlo (Fisher's exact test) |
| `run_v11.py` | Timing pilot, regression check against v1.0, X1–X5, P1 → `outputs/` |
| `findings_v11.py` | Findings, thesis alignment, limitations, executive conclusion from the numbers |
| `make_figures_v11.py`, `write_docs_v11.py` | Figures and documents from `outputs/` only |
| `tests/test_model2_v1_1.py` | Pre-registered tests 1–7 |

## Run it

```bash
cd version_d/model2_feedback_loop_v1_1
python -m pip install numpy scipy scikit-learn pandas matplotlib joblib pyyaml pytest
python -m pytest -q tests/test_model2_v1_1.py   # about 6 minutes on 2 cores
python run_v11.py                                 # timing pilot + full run, about 30 minutes on 2 cores
python make_figures_v11.py && python write_docs_v11.py
```

Run it in a cloud workspace or a machine with spare memory, not on a laptop that is short on memory.
