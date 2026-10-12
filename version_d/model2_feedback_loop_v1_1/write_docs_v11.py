"""Write model_card_v1_1.md, methods_appendix_v1_1.md and dashboard_patch_v1_1.md from outputs/."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"

REFS = [
    "Goddard, K., Roudsari, A., & Wyatt, J. C. (2012). Automation bias: A systematic review of frequency, effect "
    "mediators, and mitigators. *Journal of the American Medical Informatics Association, 19*(1), 121–127.",
    "Kamiran, F., & Calders, T. (2012). Data preprocessing techniques for classification without discrimination. "
    "*Knowledge and Information Systems, 33*(1), 1–33.",
    "Kilbertus, N., Gomez-Rodriguez, M., Schölkopf, B., Muandet, K., & Valera, I. (2020). Fair decisions despite "
    "imperfect predictions. In *Proceedings of the 23rd International Conference on Artificial Intelligence and "
    "Statistics* (pp. 277–287). PMLR.",
    "Lakkaraju, H., Kleinberg, J., Leskovec, J., Ludwig, J., & Mullainathan, S. (2017). The selective labels problem: "
    "Evaluating algorithmic predictions in the presence of unobservables. In *Proceedings of the 23rd ACM SIGKDD "
    "International Conference on Knowledge Discovery and Data Mining* (pp. 275–284).",
    "Parasuraman, R., & Manzey, D. H. (2010). Complacency and bias in human use of automation: An attentional "
    "integration. *Human Factors, 52*(3), 381–410.",
    "Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., "
    "Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. "
    "(2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research, 12*, 2825–2830.",
    "Uniform Guidelines on Employee Selection Procedures, 29 C.F.R. § 1607.4(D) (1978).",
]


def test_rows():
    rows, n_pass, n = [], 0, 0
    for name in ("v1_1_tests_1_6.xml", "v1_1_test_7.xml"):
        p = OUT / "tests" / name
        if not p.exists():
            continue
        for tc in ET.parse(p).iter("testcase"):
            if tc.find("skipped") is not None:
                continue
            n += 1
            fail = tc.find("failure")
            n_pass += fail is None
            msg = ""
            if fail is not None:
                msg = (fail.get("message") or "").split("\n")[0][:160].replace("|", "/")
            rows.append(f"| {tc.get('name')} | {'passed' if fail is None else 'FAILED'} | {msg} |")
    return "| Test | Result | Message |\n|---|---|---|\n" + "\n".join(rows), n_pass, n


def main():
    r = json.loads((OUT / "model2_v1_1_results.json").read_text(encoding="utf-8"))
    log = json.loads((OUT / "run_log_v1_1.json").read_text(encoding="utf-8"))
    diag = json.loads((OUT / "diagnostic_test2.json").read_text(encoding="utf-8"))
    cfg = r["config"]
    reg = r["regression_check"]
    tt, n_pass, n = test_rows()
    T = cfg["T"]

    def ext(eid):
        return next(e for e in r["extensions"] if e["id"] == eid)

    x1 = ext("X1")
    x1rows = []
    for x in x1["results"]:
        o = x["overall_ir"]
        p = x["proxy_signal"]
        x1rows.append(f"| {x['calibration']} | {x['scenario']} | {x['value']} | {o['median'][T-1]:.2f} "
                      f"({o['p05'][T-1]:.2f}–{o['p95'][T-1]:.2f}) | {x['screen_ir']['median'][T-1]:.2f} | "
                      f"{x['hire_share_women']['median'][T-1]:.3f} | {p['median'][T-1]:+.3f} |")
    prow = []
    for row in r["power"]["rows"]:
        prow.append(f"| {row['stage']} | {row['pool_share_women']} | {row['true_ir']} | {row['min_applicants_80pct']} | "
                    + " | ".join(f"{v:.2f}" for v in row["power_by_A"].values()) + " |")
    As = list(r["power"]["rows"][0]["power_by_A"].keys())

    card = f"""# Model card addendum: Model 2 v1.1 (human-AI reliance and robustness pack)

**{r['label']}.** Never a forecast. Version {r['version']} (base {r['base_version']}), run {r['run_date']}. Pre-registration: `v1_1_plan.md`. This addendum extends the v1.0 card (`../model2_feedback_loop/outputs/model_card.md`); everything there still applies.

## What changed in v1.1

| ID | Extension | Question |
|---|---|---|
""" + "\n".join(f"| {e['id']} | {e['name']} | {', '.join(e['rq'])} |" for e in r["extensions"]) + f"""
| P1 | Detection power (minimum instrumentation spec) | RQ5 |

- Screeners: L2 logistic regression (C = {cfg['logreg_C']}) as in v1.0; X3 adds scikit-learn `HistGradientBoostingClassifier` with defaults. Sex is never a feature in either (checked on every run: {r['checks']['sex_never_a_feature']}).
- Regression check: with every extension switched off, v1.1 reproduced v1.0 exactly in {reg['configs_compared']} of {reg['configs_compared']} configurations (matches: {reg['matches_v1_0']}).
- Runs per configuration: regression {cfg['runs']['regression']}, X3 {cfg['runs']['x3']}, X1/X2/X4/X5 {cfg['runs']['default']} (reduced from 200 by the pre-registered runtime rule; pilot projected {cfg.get('pilot_projected_minutes_full')} minutes).

## Findings

""" + "\n".join(f"- {f}" for f in r["findings"]) + f"""

## Executive conclusion

{r['executive_conclusion_model2_v1_1']}

## Thesis alignment

""" + "\n".join(f"- **{t['question']}** — {t['contribution']} *Status: {t['status']}.*" for t in r["thesis_alignment"]) + """

Research layers unchanged: "Historical feedback loops: Exploratory hypothesis"; "Algorithmic causation: Not established"; "Predictive ML analysis: Not estimable from public data".

## Limitations

""" + "\n".join(f"- {x}" for x in r["limitations"]) + f"""

## Tests

{n_pass} of {n} passed. Failures are reported, not edited; see the methods appendix.

## References (APA 7)

""" + "\n\n".join(REFS) + "\n"
    (OUT / "model_card_v1_1.md").write_text(card, encoding="utf-8")

    appendix = f"""# Methods appendix: Model 2 v1.1

**{r['label']}.** Run {r['run_date']}.

## 1. Equations

All v1.0 equations hold (`../model2_feedback_loop/outputs/methods_appendix.md`). Additions:

- **X1 reliance.** Interview score = (1 − w)·z(q + η − δₕ·f) + w·z(s), z standardized within the interviewed set, s = the screener's decision function; w ∈ {x1['values']}. At w = 0 the raw v1.0 score is used, so the ranking is identical.
- **X2 exploration.** Each cycle ⌊ε·N⌋ screened-out applicants (ε ∈ {ext('X2')['values']}) are drawn at random from a separate stream seeded from the run seed and interviewed with the shortlist; k hires are made from the union. Labels keep the v1.0 definition (hired = 1 among all applicants of the previous cycle). Interview impact ratio uses the interviewed set as denominator.
- **X3 boosted screener.** `HistGradientBoostingClassifier(random_state = run seed)`, defaults otherwise (100 iterations, no early stopping at N = 10,000). Proxy signal = mean drop in ROC AUC over {cfg['x3_permutation_importance']['repeats']} shuffles of x₃ on a seeded {cfg['x3_permutation_importance']['subsample']:,}-row subsample of that cycle's training data. Logistic comparisons use the regression runs with the same seeds.
- **X4 proxy relevance.** x₃ = ρ·f + λ·q + ε₃, λ ∈ {ext('X4')['values']}, same ε₃ draw as v1.0.
- **X5 cumulative window.** Training data = all cycles 0 … t − 1 concatenated; standardization refit each cycle.
- **P1 power.** Stage pass rate s, pool share p, true ratio r: men's rate s/(p·r + 1 − p), women's r times that. Women at risk ~ Binomial(at-risk, p); selections binomial. Screen at-risk = A (s = {r['power']['screen_pass_rate']}); interview at-risk = ⌊0.10·A⌋ (s = {r['power']['interview_pass_rate']}). {r['power']['replicates']:,} replicates per cell; two-sided Fisher's exact test at α = {r['power']['alpha']}; an undefined observed ratio counts as "not below 0.80".

## 2. Parameters

N = {cfg['N']:,}; shortlist {cfg['shortlist_rate']:.0%}; hire {cfg['hire_rate']:.0%}; T = {T}; σₓ = {cfg['sigma_x']}; σᵢ = {cfg['sigma_i']}; ρ = {cfg['rho']}; h₀ = {cfg['h0_target']}; base seed {cfg['base_seed']}. C1 pool {cfg['calibrations']['C1']['pool_share_women']} (δ₀ = {cfg['calibrations']['C1']['delta0']}); C2 pool {cfg['calibrations']['C2']['pool_share_women']}, illustrative (δ₀ = {cfg['calibrations']['C2']['delta0']}).

## 3. X1 at cycle {T} (median, 5th–95th for overall ratio)

| Calibration | Scenario | w | Overall impact ratio | Screen impact ratio | Women's hire share | Proxy weight |
|---|---|---|---|---|---|---|
""" + "\n".join(x1rows) + f"""

## 4. P1 power table

| Stage | Pool share | True ratio | Min. applicants for 80% | """ + " | ".join(f"A = {int(a):,}" for a in As) + " |\n|---|---|---|---|" + "---|" * len(As) + "\n" + "\n".join(prow) + f"""

Interview-stage gaps of the simulated size need pooling across periods or role families unless a role family has about 10,000 applicants per period. Full table, including P(observed ratio < 0.80): `power_table.csv`.

## 5. Tests

{tt}

**Test 2 (X1 null) failed at one point, in both calibrations.** Under S0 at w = 0.75, the median overall impact ratio at cycle 4 was 0.928 (C1) and 0.938 (C2) against a band of 0.95–1.05; every other cycle and every other w passed. A post-hoc diagnostic with {diag['runs']} runs (`diagnostic_test2.py`, output `diagnostic_test2.json`; no parameter changed) gave cycle-4 medians of {diag['by_calibration']['C1']['median_overall_ir'][3]:.3f} (C1) and {diag['by_calibration']['C2']['median_overall_ir'][3]:.3f} (C2); all medians were within the band ({diag['by_calibration']['C1']['all_medians_within_095_105'] and diag['by_calibration']['C2']['all_medians_within_095_105']}), the mean log ratio ranged from {min(min(v['mean_log_overall_ir']) for v in diag['by_calibration'].values()):.3f} to {max(max(v['mean_log_overall_ir']) for v in diag['by_calibration'].values()):.3f}, and the run-to-run SD of the overall ratio was {min(min(v['sd_overall_ir']) for v in diag['by_calibration'].values()):.2f}–{max(max(v['sd_overall_ir']) for v in diag['by_calibration'].values()):.2f}. Reading: Monte Carlo noise, widened by reliance. The C1 and C2 failures share seeds, so they are not independent.

**Test 5 (P1 calibration) failed in one of four cells.** With r = 1.0, the screen-stage rejection rate at A = 5,000, p = 0.203 was 0.051 against a cap of 0.05. The Monte Carlo standard error at 2,000 replicates is about 0.005, so this is within noise of the nominal rate; Fisher's exact test is close to nominal at large A.

Neither test was edited.

**Pre-registration scope.** `v1_1_plan.md` was committed (27a28e9) before any v1.1 code existed. `config_v1_1.yaml`, the v1.1 code and the test file were written after the plan and before the runs, and were committed together with the results; their values match the plan.

## 6. Runtime

Pilot projected {log['pilot']['projected_minutes_full']} minutes at full runs (by part: {', '.join(f'{k} {v}' for k, v in log['pilot']['projected_minutes_by_part_full'].items())}), over the {30}-minute target, so X1, X2, X4 and X5 dropped to {cfg['runs']['default']} runs as pre-registered. Actual: {log['timings_minutes']['total']} minutes on {log['cpu_count']} cores (by part: {', '.join(f'{k} {v}' for k, v in log['timings_minutes'].items() if k != 'total')}). Python {log['python']}, NumPy {log['numpy']}, scikit-learn {log['sklearn']}.

## References (APA 7)

""" + "\n\n".join(REFS) + "\n"
    (OUT / "methods_appendix_v1_1.md").write_text(appendix, encoding="utf-8")

    patch = f"""# Replit Agent prompt: Model 2 v1.1 dashboard patch (NOT YET APPLIED)

**Status:** written {r['run_date']}; Elizabeth paused Replit updates. Paste this into the Replit Agent only when she says to.

---

Load `model2_v1_1_results.json` (from `version_d/model2_feedback_loop_v1_1/outputs/`). In **section 07 (Simulation)**, add two panels after E3. Both use the purple family only (#5b3f8c, #8a6fbf, #c9b8e6, neutral gray), carry a **SIMULATION** tag, and repeat the label "{r['label']}". Never call anything a forecast.

**E4 Reliance.** Small multiples, one per scenario (S1 even-handed interviews, S2 interview penalty continues) and calibration (C1, C2). x-axis: w (interviewer reliance on the AI score: 0, 0.25, 0.5, 0.75). y-axis: overall impact ratio at cycle {T} (`extensions[id="X1"].results[*].overall_ir.median[{T - 1}]`, with p05/p95 as a band). Dashed line at 0.80. Caption: the first two sentences of `findings`.

**E5 Minimum instrumentation.** A readable grid from `power.rows`: rows = stage × true ratio, columns = applicants per role family per period ({', '.join(f'{int(a):,}' for a in As)}); cell = power, shaded light to dark purple; highlight cells ≥ 0.80. Above the grid, one line per stage and pool share: "Applicants per role family needed to detect a gap of 0.62 with 80% power: {{min_applicants_80pct}}". Caption: the third sentence of `findings`.

Do not change any other section. Keep the existing "Algorithmic causation: Not established" and "Historical feedback loops: Exploratory hypothesis" labels as they are.
"""
    (OUT / "dashboard_patch_v1_1.md").write_text(patch, encoding="utf-8")


if __name__ == "__main__":
    main()
