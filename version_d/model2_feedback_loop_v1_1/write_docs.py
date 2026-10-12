"""Write outputs/model_card.md and outputs/methods_appendix.md from the results.

Every number comes from outputs/model2_results.json, outputs/run_log.json,
outputs/sensitivity_*.csv and the pytest JUnit files in outputs/tests/.
SIMULATION — synthetic applicants; not Anthropic data.
"""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"


def load():
    r = json.loads((OUT / "model2_results.json").read_text(encoding="utf-8"))
    log = json.loads((OUT / "run_log.json").read_text(encoding="utf-8"))
    cfg = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    grids = {}
    for sid in ("S1", "S2"):
        with open(OUT / f"sensitivity_{sid}.csv", newline="", encoding="utf-8") as fh:
            grids[sid] = list(csv.DictReader(fh))
    return r, log, cfg, grids


def tests():
    rows = []
    for xml in sorted((OUT / "tests").glob("*.xml")):
        root = ET.parse(xml).getroot()
        for tc in root.iter("testcase"):
            status = "passed"
            msg = ""
            for tag in ("failure", "error", "skipped"):
                el = tc.find(tag)
                if el is not None:
                    status = {"failure": "FAILED", "error": "ERROR", "skipped": "skipped"}[tag]
                    msg = (el.get("message") or "")[:160]
            rows.append({"suite": xml.stem, "name": tc.get("name"), "status": status,
                         "time_s": float(tc.get("time", 0)), "message": msg})
    return rows


def f2(x):
    return "n/a" if x is None else f"{x:.2f}"


def f3(x):
    return "n/a" if x is None else f"{x:.3f}"


def rng(m, i):
    return f"{f2(m['median'][i])} ({f2(m['p05'][i])}–{f2(m['p95'][i])})"


def scen_table(r):
    lines = ["| Calib. | Scenario | δ₀ | δₕ | ρ | Screen IR c1 | Screen IR c5 | Overall IR c5 | Interview IR c5 | "
             "Women's hire share c5 | Proxy weight c1 → c5 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in r["scenarios"]:
        lines.append(
            f"| {s['calibration']} | {s['id']} {s['name']} | {f3(s['delta0'])} | {f3(s['delta_h'])} | "
            f"{s['proxy_strength']:g} | {rng(s['screen_impact_ratio'], 0)} | {rng(s['screen_impact_ratio'], 4)} | "
            f"{rng(s['overall_impact_ratio'], 4)} | {rng(s['interview_impact_ratio'], 4)} | "
            f"{rng(s['hire_share_women'], 4)} | {f3(s['proxy_weight']['median'][0])} → "
            f"{f3(s['proxy_weight']['median'][4])} |")
    return "\n".join(lines)


def iv_table(r):
    lines = ["| Calib. | Intervention | Screen IR c5 | Women's hire share c5 | Overall IR c5 | Screen validity c5 |",
             "|---|---|---|---|---|---|"]
    for cal in ("C1", "C2"):
        b = next(s for s in r["scenarios"] if s["calibration"] == cal and s["id"] == "S2")
        lines.append(f"| {cal} | S2 baseline | {rng(b['screen_impact_ratio'], 4)} | {rng(b['hire_share_women'], 4)} | "
                     f"{rng(b['overall_impact_ratio'], 4)} | {rng(b['screen_validity'], 4)} |")
        for iv in (i for i in r["interventions"] if i["calibration"] == cal):
            def d(k):
                x = iv[k]
                return f"{f2(x['median'])} ({f2(x['p05'])}–{f2(x['p95'])})"
            lines.append(f"| {cal} | {iv['id']} {iv['name']} | {d('screen_ir_cycle5')} | "
                         f"{d('hire_share_women_cycle5')} | {d('overall_ir_cycle5')} | {d('screen_validity_cycle5')} |")
    return "\n".join(lines)


def grid_md(g, key):
    head = "| ρ \\ p | " + " | ".join(f"{p:g}" for p in g["pool_share"]) + " |"
    sep = "|---|" + "---|" * len(g["pool_share"])
    rows = [head, sep]
    for rho, row in zip(g["proxy_strength"], g[key]):
        rows.append(f"| {rho:g} | " + " | ".join(("**" + f2(v) + "**") if v is not None and v < 0.80 else f2(v)
                                                 for v in row) + " |")
    return "\n".join(rows)


def references(r):
    return "\n\n".join(r["references"])


def model_card(r, log, cfg, trows):
    c1, c2 = (next(c for c in r["calibrations"] if c["id"] == k) for k in ("C1", "C2"))
    passed = sum(t["status"] == "passed" for t in trows)
    failed = [t for t in trows if t["status"] in ("FAILED", "ERROR")]
    return f"""# Model card: Model 2, screening feedback-loop simulation

**{r['label']}.** Not a forecast. Format follows Mitchell et al. (2019). Generated from `model2_results.json` (run date {r['run_date']}).

## Model details

- **What it is:** a Monte Carlo simulation of a hiring pipeline with a sex-blind logistic-regression screener (L2, C = {cfg['logreg_C']}) that is retrained every hiring cycle on the outcomes it helped produce, followed by a human interview stage.
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
- **Calibrations:** C1 benchmark pool, p = {c1['pool_share_women']} (U.S. Bureau of Labor Statistics, 2026); C2 larger historical gap, p = {c2['pool_share_women']} (illustrative). Both target a {c1['target_hire_share_women']} women's share of cycle-0 hires, the observed engineering share (Dewey & People Data Labs, 2026).

## Metrics

- **Screen impact ratio:** SR(women, shortlist) ÷ SR(men, shortlist). **Interview impact ratio:** [hired women ÷ shortlisted women] ÷ [hired men ÷ shortlisted men]. **Overall impact ratio:** SR(women, hired) ÷ SR(men, hired). Reference threshold 0.80 (Uniform Guidelines on Employee Selection Procedures, 1978).
- **Women's hire share**, **proxy weight** (screener coefficient on standardized x₃), **screen validity** (Spearman correlation of screener score with true qualification).
- Each is summarized over {cfg['runs']} runs per scenario as the median with the 5th–95th percentile range.

## Data

Synthetic only. Each cycle draws {cfg['N']:,} applicants: sex fᵢ ~ Bernoulli(p); qualification qᵢ ~ N(0, 1), independent of sex; job-relevant signals x₁ = q + ε₁ and x₂ = q + ε₂ (ε ~ N(0, {cfg['sigma_x']}²)); proxy x₃ = ρ·f + ε₃ (ε₃ ~ N(0, 1)), unrelated to qualification. Cycle 0 hires the top {int(cfg['hire_rate'] * cfg['N'])} by q + η − δ₀·f (η ~ N(0, {cfg['sigma_i']}²)). Later cycles shortlist the top {int(cfg['shortlist_rate'] * cfg['N'])} by the screener's score and hire the top {int(cfg['hire_rate'] * cfg['N'])} of the shortlist by q + η − δₕ·f. Screened-out applicants are labeled 0 (selective labels; Lakkaraju et al., 2017).

Calibrated historical penalties: C1 δ₀ = {f3(c1['delta0'])} (achieved {c1['achieved_hire_share_women']}); C2 δ₀ = {f3(c2['delta0'])} (achieved {c2['achieved_hire_share_women']}).

## Quantitative results

### Findings

{chr(10).join('- ' + f for f in r['findings'])}

### Scenarios (median, 5th–95th percentile; c1 = cycle 1, c5 = cycle 5)

{scen_table(r)}

### Interventions on S2, cycle 5

{iv_table(r)}

### Sensitivity grid, S2, median screen impact ratio at cycle 5 ({r['grid_runs_per_cell']} runs per cell; bold < 0.80)

{grid_md(r['sensitivity'], 'screen_ir_cycle5')}

### Executive conclusion (Model 2)

{r['executive_conclusion_model2']}

## Ethical considerations

- **Risk of misreading a simulation as evidence.** Every output carries the SIMULATION label; the dashboard keeps it in a separate, purple, tagged section and never in the same chart as observed data.
- **Binary sex.** The simulation generates women and men only. The observed source data records Male / Female / Unknown; Unknown has no analogue here.
- **No real people.** No individual's data was used. The observed inputs are two aggregate shares.
- **Sex as a weight (I2).** Reweighing uses sex to set training weights, never as a feature; any real deployment of this method would need legal review.

## Caveats and recommendations

{chr(10).join('- ' + x for x in r['limitations'])}

**Recommendation.** The deciding evidence for the study's question is internal: applicant counts and pass rates by sex at each stage. This simulation shows why: hire counts alone could not show which stage carried a gap.

**Tests:** {passed} of {len(trows)} test cases passed{'; failures: ' + ', '.join(t['name'] for t in failed) if failed else ''}. Runtime of the full run: {log['timings_seconds']['total_s']:.0f} s on {log['cpu_count']} CPU cores.

## References

{references(r)}
"""


def appendix(r, log, cfg, grids, trows):
    c_rows = ["| Calibration | Pool share p | Target h₀ | δ₀ | Achieved (calibration seeds) | Brent evaluations | "
              "S0 target | S0 δ₀ | S0 achieved |", "|---|---|---|---|---|---|---|---|---|"]
    for c in r["calibrations"]:
        n = c["null_check_S0"]
        c_rows.append(f"| {c['id']} {c['name']} | {c['pool_share_women']} | {c['target_hire_share_women']} | "
                      f"{f3(c['delta0'])} | {c['achieved_hire_share_women']} | {c['brent_evaluations']} | "
                      f"{n['target_hire_share_women']} | {f3(n['delta0'])} | {n['achieved_hire_share_women']} |")
    oos = ["| Calibration | Scenario | Mean cycle-0 women's hire share over the run seeds |", "|---|---|---|"]
    for s in r["scenarios"]:
        oos.append(f"| {s['calibration']} | {s['id']} | {s['cycle0_hire_share_women_mean_runs']} |")
    gcal = ["| Pool share p | δ₀ (h₀ = 0.178) | Achieved cycle-0 share |", "|---|---|---|"]
    seen = set()
    for row in grids["S2"]:
        if row["pool_share"] in seen:
            continue
        seen.add(row["pool_share"])
        gcal.append(f"| {row['pool_share']} | {float(row['delta0']):.4f} | {row['achieved_cycle0_share']} |")
    t_rows = ["| Suite | Test | Result | Time (s) | Note |", "|---|---|---|---|---|"]
    for t in trows:
        t_rows.append(f"| {t['suite']} | `{t['name']}` | {t['status']} | {t['time_s']:.1f} | {t['message']} |")
    diag = r["diagnostics"]
    mono = diag["monotone_decrease_in_rho_by_pool_share"]
    mono_lines = "\n".join(f"- {k}: " + ", ".join(f"p = {p}: {'yes' if v else 'no'}" for p, v in cols.items())
                           for k, cols in mono.items())
    d_lines = "\n".join(
        f"- {k}: screen IR c1 {f3(v['screen_ir_cycle1_median'])} → c5 {f3(v['screen_ir_cycle5_median'])} "
        f"(change {v['change_cycle1_to_5']:+.3f}); proxy weight {f3(v['proxy_weight_cycle1_median'])} → "
        f"{f3(v['proxy_weight_cycle5_median'])}; overall IR c5 {f3(v['overall_ir_cycle5_median'])}; "
        f"interview IR c5 {f3(v['interview_ir_cycle5_median'])}"
        for k, v in diag.items() if k.startswith("C"))
    params = [
        ("Applicants per cycle", "N", cfg["N"], "assumption"),
        ("Shortlist rate", "s", cfg["shortlist_rate"], "assumption"),
        ("Hire rate", "h", cfg["hire_rate"], "assumption (20% of shortlist hired)"),
        ("Hiring cycles", "T", cfg["T"], "assumption"),
        ("Signal noise", "σₓ", cfg["sigma_x"], "assumption"),
        ("Interview noise", "σᵢ", cfg["sigma_i"], "assumption"),
        ("Proxy strength (main scenarios)", "ρ", cfg["rho"], "assumption; swept 0–1.5"),
        ("Target cycle-0 hire share (women)", "h₀", cfg["h0_target"],
         "observed engineering share (Dewey & People Data Labs, 2026)"),
        ("Pool share, C1", "p", 0.203, "U.S. Bureau of Labor Statistics (2026), software developers, 2025"),
        ("Pool share, C2", "p", 0.30, "illustrative assumption"),
        ("Screener regularization", "C", cfg["logreg_C"], "assumption (scikit-learn convention, L2)"),
        ("Monte Carlo runs per scenario", "—", cfg["runs"], "—"),
        ("Grid runs per cell", "—", cfg["grid"]["runs"], "—"),
        ("Calibration seeds", "—", cfg["calibration"]["n_seeds"], "common random numbers"),
        ("Calibration tolerance (Brent xtol on δ₀)", "—", cfg["calibration"]["xtol"], "—"),
        ("Base seed", "—", cfg["base_seed"], "run j uses base seed + j"),
    ]
    p_rows = ["| Parameter | Symbol | Value | Basis |", "|---|---|---|---|"] + [
        f"| {a} | {b} | {c} | {d} |" for a, b, c, d in params]
    t = log["timings_seconds"]
    return f"""# Methods appendix: Model 2, screening feedback-loop simulation

**{r['label']}.** Generated from the result files of the run dated {r['run_date']}.

## 1. Model

Hiring cycles t = 0, 1, …, T; each cycle draws a fresh pool of N applicants.

**Applicants.** fᵢ ~ Bernoulli(p) (fᵢ = 1 is a woman); qᵢ ~ N(0, 1) independent of sex (assumption A1); x₁ = q + ε₁, x₂ = q + ε₂, ε ~ N(0, σₓ²); x₃ = ρ·f + ε₃, ε₃ ~ N(0, 1).

**Cycle 0 (history).** Hire the top k = ⌊h·N⌋ by qᵢ + ηᵢ − δ₀·fᵢ, η ~ N(0, σᵢ²). δ₀ is found by Brent's method so that the mean women's share of cycle-0 hires over 50 calibration seeds equals h₀; the same seeds are used at every trial δ (common random numbers), so the objective is deterministic.

**Cycles t ≥ 1.** (1) Train Mₜ: L2-regularized logistic regression (C = {cfg['logreg_C']}) on standardized [x₁, x₂, x₃] from cycle t − 1, with y = 1 if hired, else 0; screened-out applicants are labeled 0. (2) Screen a new pool: shortlist the top ⌊s·N⌋ by Mₜ's score. (3) Interview: hire the top k of the shortlist by qᵢ + ηᵢ − δₕ·fᵢ. (4) Record metrics.

**Metrics.** SR = selected ÷ applicants for a group at a stage. Screen IR = SR(women, shortlist) ÷ SR(men, shortlist); interview IR = [hired women ÷ shortlisted women] ÷ [hired men ÷ shortlisted men]; overall IR = SR(women, hired) ÷ SR(men, hired); hire share = women among hires; proxy weight = Mₜ's coefficient on standardized x₃; screen validity = Spearman correlation between Mₜ's score and q.

**Interventions (on S2).** I1 removes x₃ from the screener's features. I2 reweighs each cycle's training data with w(s, y) = P(s)·P(y) ÷ P(s, y) so sex and label are independent (Kamiran & Calders, 2012); sex sets weights only. I3 trains the screener once, after cycle 0, and uses it unchanged from cycle 1 on.

## 2. Parameters (fixed before any run)

{chr(10).join(p_rows)}

## 3. Implementation notes

- Python {log['python']}, NumPy {log['numpy']}; `numpy.random.default_rng(seed)` only; joblib (loky) parallelism over runs; one BLAS thread per worker.
- Pools are drawn in a fixed order (u, q, ε₁, ε₂, ε₃, η), so runs with the same seed share random numbers across scenarios.
- Calibration seeds are base seed + 1,000,000 + j (j = 0…49), kept apart from run seeds. The tolerance of 0.002 is applied to δ₀ (Brent's `xtol`).
- Cycle 0 does not use the proxy, so δ₀ depends only on p and h₀: within a grid column, δ₀ is the same for every ρ and for S1 and S2.
- Grid cells run 5 cycles (cycles 6–8 cannot affect cycles 1 and 5). Screen validity is not computed in grid runs.
- The grid ran at the full {cfg['grid']['runs']} runs per cell; no reduction to 50 was needed.

## 4. Calibration results

{chr(10).join(c_rows)}

Out-of-sample check (mean cycle-0 women's hire share over the {cfg['runs']} run seeds, which are not the calibration seeds):

{chr(10).join(oos)}

Grid calibration (h₀ = {cfg['grid']['h0']}; identical across ρ within a column):

{chr(10).join(gcal)}

## 5. Results

### Findings (generated from the numbers)

{chr(10).join('- ' + f for f in r['findings'])}

### Scenarios

{scen_table(r)}

### Interventions

{iv_table(r)}

### Sensitivity grids: median screen impact ratio (bold < 0.80)

S2, cycle 1:

{grid_md(r['sensitivity'], 'screen_ir_cycle1')}

S2, cycle 5:

{grid_md(r['sensitivity'], 'screen_ir_cycle5')}

S1, cycle 1:

{grid_md(r['sensitivity_S1'], 'screen_ir_cycle1')}

S1, cycle 5:

{grid_md(r['sensitivity_S1'], 'screen_ir_cycle5')}

5th and 95th percentiles for every cell are in `sensitivity_S1.csv` and `sensitivity_S2.csv`.

### Diagnostics (reported, not asserted)

Direction and size of the S1 and S2 effects:

{d_lines}

Does the median screen impact ratio fall monotonically as ρ rises (within each pool-share column)?

{mono_lines}

In the p = 0.178 column the historical penalty is about zero (δ₀ = {f3(r['sensitivity']['delta0_by_pool_share'][0])}), so the values fluctuate around 1 and are not expected to be monotone. Under S1 at cycle 5 the gap has faded in every column, so the same applies.

## 6. Tests

{chr(10).join(t_rows)}

Test 7 runs in two modes: by default a small smoke configuration run twice into temporary folders; with `MODEL2_FULL_REPRO=1`, the full configuration is re-run and compared byte for byte (apart from `run_date`) with `outputs/model2_results.json`.

## 7. Runtime

Full run {t['total_s']:.0f} s on {log['cpu_count']} CPU cores: calibration {t['calibration_s']:.1f} s, scenarios {t['scenarios_s']:.0f} s, interventions {t['interventions_s']:.0f} s, grid {t['grid_s']:.0f} s.

## 8. Thesis alignment

| Question | Contribution | Status |
|---|---|---|
{chr(10).join(f"| {x['question']} | {x['contribution']} | {x['status']} |" for x in r['thesis_alignment'])}

## References

{references(r)}
"""


def main():
    r, log, cfg, grids = load()
    trows = tests()
    (OUT / "model_card.md").write_text(model_card(r, log, cfg, trows), encoding="utf-8")
    (OUT / "methods_appendix.md").write_text(appendix(r, log, cfg, grids, trows), encoding="utf-8")
    print("wrote model_card.md and methods_appendix.md;", len(trows), "test cases")


if __name__ == "__main__":
    main()
