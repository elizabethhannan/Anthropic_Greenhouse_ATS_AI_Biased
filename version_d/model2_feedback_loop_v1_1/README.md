# Model 2 — Screening feedback-loop simulation

**SIMULATION — synthetic applicants; not Anthropic data.** Not a forecast.

If a sex-blind screening model is trained on past hiring outcomes and retrained every hiring cycle on the outcomes it helped produce, does a historical gap in women's hiring persist, grow, or fade, and under which assumptions? This folder builds, tests and runs that simulation for Research Thesis Version C 3.0 (RQ2, RQ4, RQ5).

- Results: [`outputs/model2_results.json`](outputs/model2_results.json) (dashboard schema)
- Model card: [`outputs/model_card.md`](outputs/model_card.md)
- Methods appendix (equations, parameters, calibration, tests, runtime, references): [`outputs/methods_appendix.md`](outputs/methods_appendix.md)
- Figures: [`outputs/figures/`](outputs/figures/) (SVG and 300-dpi PNG)

## Files

| File | Role |
|---|---|
| `config.yaml` | Every parameter; the only place parameters live. Fixed before any run. |
| `simulate.py` | Applicant generation, history cycle, screener training, screening, interview, per-cycle metrics |
| `calibrate.py` | Brent root-finding for the historical penalty δ₀ (common random numbers over 50 seeds) |
| `metrics.py` | Selection rates, impact ratios, Monte Carlo summaries |
| `run_experiments.py` | Calibrations, scenarios S0–S3, interventions I1–I3, sensitivity grid → `outputs/` |
| `findings.py` | Findings, diagnostics, limitations, thesis alignment, generated from the numbers |
| `make_figures.py` | Figures from `outputs/` only |
| `write_docs.py` | Model card and methods appendix from `outputs/` and the test reports |
| `tests/test_model2.py` | The seven pre-specified tests |

## Run it

```bash
cd version_d/model2_feedback_loop
python -m pip install numpy scipy scikit-learn pandas matplotlib joblib pyyaml pytest

# tests 1-7 (test 7 uses a small smoke configuration by default)
python -m pytest -q --junitxml=outputs/tests/pytest_default.xml

# full experiment (about 5 minutes on 2 cores)
python run_experiments.py

# optional: test 7 against the full configuration (re-runs everything, compares byte for byte)
MODEL2_FULL_REPRO=1 python -m pytest -q tests/test_model2.py -k test_7 --junitxml=outputs/tests/pytest_full_repro.xml

python make_figures.py
python write_docs.py
```

## Put the results in the Replit dashboard

1. Copy `outputs/model2_results.json` into the root of the Replit project, next to `index.html` and `data.js`.
2. Reload the page. Section 07 fetches `model2_results.json`; if it loads, charts E1–E3 and the findings render; if not, the pending panel shows.
3. The dashboard ignores the extra keys (`config`, `interview_impact_ratio`, `screen_validity`, `diagnostics`, `checks`, `sensitivity_S1`, …).

## Integrity rules followed

- Synthetic only; every output carries the SIMULATION label.
- Defaults were fixed before running and not changed after seeing outputs.
- Sex is never a screener input (checked in every scenario and intervention, test 5).
- Null and negative results are reported with the same prominence as effects.
- Failing tests are reported, not edited.
