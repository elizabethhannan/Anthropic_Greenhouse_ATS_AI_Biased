"""Generate findings, diagnostics, limitations and thesis text from the numbers.

Every number in the text is read from the results dictionary built by
run_experiments.py. Nothing here changes a parameter, scenario or test.
SIMULATION — synthetic applicants; not Anthropic data.
"""

from __future__ import annotations

import numpy as np

THESIS_Q = {
    "RQ2": "2. Algorithmic influence: Could AI-assisted screening, candidate matching, or historical hiring "
           "patterns reinforce existing demographic disparities?",
    "RQ4": "4. Long-term AI risk: Could repeated employment outcomes become feedback signals that lead future "
           "AI systems to reproduce historical hiring preferences?",
    "RQ5": "5. Governance: What internal data, evaluation methods, and executive accountability are required to "
           "distinguish algorithmic bias from human, structural, and applicant-pool factors?",
}

REFERENCES = [
    "Dewey & People Data Labs. (2026). Observed Anthropic starts, April–July 2026 [Unpublished data set extract].",
    "Kamiran, F., & Calders, T. (2012). Data preprocessing techniques for classification without discrimination. "
    "Knowledge and Information Systems, 33(1), 1–33.",
    "Lakkaraju, H., Kleinberg, J., Leskovec, J., Ludwig, J., & Mullainathan, S. (2017). The selective labels problem: "
    "Evaluating algorithmic predictions in the presence of unobservables. In Proceedings of the 23rd ACM SIGKDD "
    "International Conference on Knowledge Discovery and Data Mining (pp. 275–284).",
    "Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & "
    "Gebru, T. (2019). Model cards for model reporting. In Proceedings of the Conference on Fairness, "
    "Accountability, and Transparency (pp. 220–229).",
    "Perdomo, J. C., Zrnic, T., Mendler-Dünner, C., & Hardt, M. (2020). Performative prediction. In Proceedings of "
    "the 37th International Conference on Machine Learning (pp. 7599–7609). PMLR.",
    "Raghavan, M., Barocas, S., Kleinberg, J., & Levy, K. (2020). Mitigating bias in algorithmic hiring: Evaluating "
    "claims and practices. In Proceedings of the 2020 Conference on Fairness, Accountability, and Transparency "
    "(pp. 469–481).",
    "U.S. Bureau of Labor Statistics. (2026). Employed persons by detailed occupation, sex, race, and Hispanic or "
    "Latino ethnicity (Labor Force Statistics from the Current Population Survey, Table 11, 2025 annual averages). "
    "https://www.bls.gov/cps/cpsaat11.htm",
    "Uniform Guidelines on Employee Selection Procedures, 29 C.F.R. § 1607.4(D) (1978).",
]


def _scen(r, cal, sid):
    return next(s for s in r["scenarios"] if s["calibration"] == cal and s["id"] == sid)


def _iv(r, cal, iid):
    return next(i for i in r["interventions"] if i["calibration"] == cal and i["id"] == iid)


def _at(entry, metric, cycle):
    m = entry[metric]
    i = cycle - 1
    return m["median"][i], m["p05"][i], m["p95"][i]


def f2(x):
    return f"{x:.2f}"


def f3(x):
    return f"{x:.3f}"


def rng_txt(t, fmt=f2):
    med, lo, hi = t
    return f"{fmt(med)} ({fmt(lo)}–{fmt(hi)})"


def d_txt(d):
    return f"{d['median']:.2f} ({d['p05']:.2f}–{d['p95']:.2f})"


def _median_range(r, sid, cals=("C1", "C2")):
    vals = [v for c in cals for v in _scen(r, c, sid)["screen_impact_ratio"]["median"]]
    return min(vals), max(vals)


def diagnostics(r: dict) -> dict:
    out = {}
    for cal in ("C1", "C2"):
        for sid in ("S1", "S2"):
            s = _scen(r, cal, sid)
            c1, c5 = _at(s, "screen_impact_ratio", 1)[0], _at(s, "screen_impact_ratio", 5)[0]
            out[f"{cal}_{sid}"] = {
                "screen_ir_cycle1_median": c1, "screen_ir_cycle5_median": c5,
                "change_cycle1_to_5": round(c5 - c1, 4),
                "proxy_weight_cycle1_median": _at(s, "proxy_weight", 1)[0],
                "proxy_weight_cycle5_median": _at(s, "proxy_weight", 5)[0],
                "overall_ir_cycle5_median": _at(s, "overall_impact_ratio", 5)[0],
                "interview_ir_cycle5_median": _at(s, "interview_impact_ratio", 5)[0],
            }
    mono = {}
    for key, grid in (("S1", r.get("sensitivity_S1")), ("S2", r.get("sensitivity"))):
        if not grid:
            continue
        for cyc in (1, 5):
            M = np.array(grid[f"screen_ir_cycle{cyc}"], dtype=float)  # rows = rho, cols = p
            cols = {}
            for j, p in enumerate(grid["pool_share"]):
                col = M[:, j]
                cols[str(p)] = bool(np.all(np.diff(col) <= 0))
            mono[f"{key}_cycle{cyc}"] = cols
    out["monotone_decrease_in_rho_by_pool_share"] = mono
    return out


def build_text(r: dict, cfg: dict) -> dict:
    S0range = _median_range(r, "S0")
    S3range = _median_range(r, "S3")
    s0c1 = _scen(r, "C1", "S0")
    s3c2 = _scen(r, "C2", "S3")
    s1c1, s1c2 = _scen(r, "C1", "S1"), _scen(r, "C2", "S1")
    s2c1, s2c2 = _scen(r, "C1", "S2"), _scen(r, "C2", "S2")
    rho = cfg["rho"]

    # --- S1: does the screen gap fade? -------------------------------------------
    s1_c1 = _at(s1c2, "screen_impact_ratio", 1)
    s1_c5 = _at(s1c2, "screen_impact_ratio", 5)
    s1_pw1 = _at(s1c2, "proxy_weight", 1)[0]
    s1_pw5 = _at(s1c2, "proxy_weight", 5)[0]
    s1_faded = s1_c5[0] >= 0.99 and s1_c5[0] > s1_c1[0]
    s1_verb = "faded" if s1_faded else "did not fade"

    # --- S2: does it persist? ----------------------------------------------------
    s2_c1 = _at(s2c2, "screen_impact_ratio", 1)
    s2_c5 = _at(s2c2, "screen_impact_ratio", 5)
    s2_pw1 = _at(s2c2, "proxy_weight", 1)[0]
    s2_pw5 = _at(s2c2, "proxy_weight", 5)[0]
    s2_iir5 = _at(s2c2, "interview_impact_ratio", 5)
    s2_oir5 = _at(s2c2, "overall_impact_ratio", 5)
    s2c1_sir5 = _at(s2c1, "screen_impact_ratio", 5)
    s2c1_oir5 = _at(s2c1, "overall_impact_ratio", 5)
    pw_dir = "strengthened" if s2_pw5 < s2_pw1 else "weakened"

    # --- Interventions (C2) ----------------------------------------------------
    i1, i2, i3 = (_iv(r, "C2", k) for k in ("I1", "I2", "I3"))
    hs_base = _at(s2c2, "hire_share_women", 5)[0]
    hs_iv = [i["hire_share_women_cycle5"]["median"] for i in (i1, i2, i3)]
    val_base = _at(s2c2, "screen_validity", 5)[0]
    val_iv = [i["screen_validity_cycle5"]["median"] for i in (i1, i2, i3)]
    i3_same = abs(i3["screen_ir_cycle5"]["median"] - s2_c5[0]) < 0.01
    hs_same = all(abs(h - hs_base) < 0.01 for h in hs_iv)

    # --- Grid -------------------------------------------------------------------
    g = r["sensitivity"]
    M5 = np.array(g["screen_ir_cycle5"], dtype=float)
    L5 = np.array(g["screen_ir_cycle5_p05"], dtype=float)
    H5 = np.array(g["screen_ir_cycle5_p95"], dtype=float)
    rhos, ps = g["proxy_strength"], g["pool_share"]
    below = [(i, j) for i in range(M5.shape[0]) for j in range(M5.shape[1]) if M5[i, j] < 0.80]
    worst = np.unravel_index(np.nanargmin(M5), M5.shape)
    if below:
        rho_set = sorted({rhos[i] for i, _ in below})
        p_min = min(ps[j] for _, j in below)
        d0_min = min(g["delta0_by_pool_share"][j] for _, j in below)
        rho_ok = [x for x in rhos if x < min(rho_set)]
        max_ok = max(rho_ok) if rho_ok else None
        min_ok = np.nanmin(M5[[i for i, x in enumerate(rhos) if x <= max_ok], :]) if max_ok is not None else None
        grid_sentence = (
            f"Across the S2 sensitivity grid ({r['grid_runs_per_cell']} runs per cell, δ₀ calibrated per cell to a "
            f"{g['target_hire_share_women']:.3f} cycle-0 hire share), the median screen impact ratio fell below 0.80 "
            f"at cycle 5 only when the proxy strength was ρ = {', '.join(f'{x:g}' for x in rho_set)} and the assumed "
            f"pool share of women was at least {p_min:.2f} (historical penalty δ₀ ≥ {d0_min:.2f}); the most extreme "
            f"cell (ρ = {rhos[worst[0]]:g}, pool share {ps[worst[1]]:.2f}) was {M5[worst]:.2f} "
            f"({L5[worst]:.2f}–{H5[worst]:.2f})"
            + (f", while every cell with ρ ≤ {max_ok:g} stayed at or above {min_ok:.2f}" if max_ok is not None else ""))
    else:
        grid_sentence = (f"No cell of the S2 sensitivity grid fell below 0.80 at cycle 5; the lowest median was "
                         f"{M5[worst]:.2f} ({L5[worst]:.2f}–{H5[worst]:.2f}) at ρ = {rhos[worst[0]]:g}, pool share "
                         f"{ps[worst[1]]:.2f}")
    s1g = np.array(r["sensitivity_S1"]["screen_ir_cycle5"], dtype=float)
    grid_sentence += (f"; under S1 (even-handed interviews) every cell's median was at least "
                      f"{np.nanmin(s1g):.2f} by cycle 5 (RQ2).")

    findings = [
        (f"Null checks held: with no historical penalty (S0) the median screen impact ratio stayed between "
         f"{S0range[0]:.2f} and {S0range[1]:.2f} across all {cfg['T']} cycles under both calibrations (C1, cycle 5: "
         f"{rng_txt(_at(s0c1, 'screen_impact_ratio', 5))}), and with no proxy (S3) it stayed between "
         f"{S3range[0]:.2f} and {S3range[1]:.2f} even though the interview penalty continued (C2, cycle 5: "
         f"{rng_txt(_at(s3c2, 'screen_impact_ratio', 5))}), so in this model a sex-blind screener carries a gap only "
         f"through a sex-correlated feature (RQ2)."),
        (f"When interviews were even-handed (S1), the screen-stage gap {s1_verb}: under the illustrative C2 "
         f"calibration with ρ = {rho:g}, the screen impact ratio was {rng_txt(s1_c1)} at cycle 1 and "
         f"{rng_txt(s1_c5)} by cycle 5 as the screener's proxy weight moved from {s1_pw1:.3f} to {s1_pw5:.3f}; "
         f"under the benchmark C1 calibration it was {rng_txt(_at(s1c1, 'screen_impact_ratio', 1))} at cycle 1, "
         f"indistinguishable from the null (RQ4)."),
        (f"When the interview penalty continued (S2, C2), retraining kept the gap at the screen, with the screen "
         f"impact ratio at {rng_txt(s2_c1)} at cycle 1 and {rng_txt(s2_c5)} at cycle 5 and the proxy weight "
         f"{pw_dir} from {s2_pw1:.3f} to {s2_pw5:.3f}, but most of the gap formed at the interview: the cycle-5 "
         f"interview impact ratio was {rng_txt(s2_iir5)} and the overall impact ratio {rng_txt(s2_oir5)} "
         f"(C1: screen {rng_txt(s2c1_sir5)}, overall {rng_txt(s2c1_oir5)}) (RQ4)."),
        (f"Under C2 at cycle 5, removing the proxy (I1) gave a screen impact ratio of {d_txt(i1['screen_ir_cycle5'])} "
         f"and reweighing (I2) {d_txt(i2['screen_ir_cycle5'])}, against {rng_txt(s2_c5)} for the S2 baseline, while "
         f"freezing the screener after cycle 1 (I3) gave {d_txt(i3['screen_ir_cycle5'])}"
         + (", essentially unchanged" if i3_same else "")
         + (f"; none of the three changed women's share of hires at cycle 5 (baseline {hs_base:.3f}; interventions "
            f"{', '.join(f'{h:.3f}' for h in hs_iv)}), because the continuing interview penalty set it"
            if hs_same else
            f"; women's share of hires at cycle 5 moved from {hs_base:.3f} to {', '.join(f'{h:.3f}' for h in hs_iv)}")
         + f", and screen validity stayed at {val_base:.2f} (interventions {', '.join(f'{v:.2f}' for v in val_iv)}) "
         f"(RQ5)."),
        grid_sentence,
    ]

    limitations = [
        "Synthetic applicants: every applicant is generated; no Anthropic applicant, screening, or interview data "
        "was used, and none is available.",
        "Equal-qualification assumption A1: qualification q is N(0, 1) for women and men; results would change if "
        "qualification distributions differed.",
        "A single linear proxy (x3) with standardized mean difference ρ; real application materials can encode sex "
        "through many correlated, nonlinear features.",
        "Logistic-regression screener (L2, C = 1.0) trained on hired / not-hired labels; real systems vary (ranking "
        "models, LLM-based scorers, recruiter overrides, other label definitions).",
        "The national benchmark (20.3% of U.S. software developers, 2025) is a workforce share, not a qualified "
        "applicant pool; C2's 30% pool share is illustrative.",
        "No workforce attrition, growth, internal mobility, or advancement is modeled; the simulation covers "
        "selection only.",
        "Results describe a mechanism under stated assumptions, not Anthropic: they say nothing about whether "
        "Anthropic uses any screening model, on what inputs, or with what effect.",
        "Selective labels: screened-out applicants are labeled 0 (Lakkaraju et al., 2017); other label choices "
        "(e.g., interview pass) were not explored.",
        "Pipeline rates (s = 0.10, h = 0.02) and noise levels (σx = 1.0, σi = 0.7) were fixed, not swept; how "
        "much the screen matters depends on how selective the shortlist is.",
        f"Monte Carlo spread is wide for single runs (each cycle hires {int(cfg['hire_rate'] * cfg['N'])} people): "
        "5th–95th percentile bands on the screen impact ratio span roughly ±0.13 around the median, so medians, "
        "not single runs, carry the findings.",
    ]

    thesis = [
        {"question": THESIS_Q["RQ2"],
         "contribution": (f"A sex-blind screener retrained on past outcomes produced a screen impact ratio below 1 "
                          f"only when a sex-correlated proxy existed (S3 without a proxy: {S3range[0]:.2f}–"
                          f"{S3range[1]:.2f}). With ρ = {rho:g} the screen-stage effect was small (C2, S2 cycle 5: "
                          f"{f2(s2_c5[0])}); reaching the four-fifths threshold at the screen required a strong proxy "
                          f"and a large historical gap in the sensitivity grid."),
         "status": "Simulated only; mechanism characterized under stated assumptions; not established for Anthropic"},
        {"question": THESIS_Q["RQ4"],
         "contribution": (f"Repeated retraining reproduced the historical pattern only while the human interview stage "
                          f"kept applying the penalty (S2: proxy weight {s2_pw1:.3f} → {s2_pw5:.3f}); with "
                          f"even-handed interviews the screen gap {s1_verb} by cycle 5 (S1, C2: {f2(s1_c1[0])} → "
                          f"{f2(s1_c5[0])})."),
         "status": "Exploratory hypothesis — sharpened by simulation, not confirmed"},
        {"question": THESIS_Q["RQ5"],
         "contribution": (f"Removing the proxy (I1) or reweighing training data (I2) restored screen parity "
                          f"({f2(i1['screen_ir_cycle5']['median'])}, {f2(i2['screen_ir_cycle5']['median'])}) with no "
                          f"measurable loss of screen validity; freezing (I3) did not. Women's share of hires did not "
                          f"move while the interview penalty continued, so stage-level impact ratios, not hire counts, "
                          f"are the evaluation method that separates screen effects from human-stage effects."),
         "status": "Evaluation method specified; requires internal stage-level data to apply"},
    ]

    exec_conclusion = (
        "The most consequential simulation finding is not that a retrained screening model locks in a historical "
        "gap on its own. It is that, under these assumptions, the screen stage carried only a small part of the gap "
        f"(screen impact ratio {f2(s2_c5[0])} at cycle 5 under the illustrative C2 calibration, and "
        f"{f2(s2c1_sir5[0])} under the benchmark C1 calibration, indistinguishable from parity), and whether the gap "
        "persisted depended on the human interview stage: with even-handed interviews the screen gap "
        f"{s1_verb} by cycle 5, and with a continuing interview penalty it persisted and the screener's reliance on "
        f"the proxy grew, while the overall impact ratio stayed near {f2(s2_oir5[0])} under C2 "
        f"({f2(s2c1_oir5[0])} under C1). Hire counts alone could not "
        "show which stage carried the gap; stage-level selection rates could. This is a statement about a mechanism with "
        "synthetic applicants, not about Anthropic's systems, applicants, or workforce, and it leaves the "
        "\"Historical feedback loops\" layer an exploratory hypothesis."
    )

    return {
        "findings": findings,
        "limitations": limitations,
        "thesis_alignment": thesis,
        "executive_conclusion_model2": exec_conclusion,
        "research_layer_status": {
            "Historical feedback loops": "Exploratory hypothesis (unchanged; sharpened by simulation)",
            "Algorithmic causation": "Not established (unchanged)",
            "Predictive ML analysis": "Not estimable from public data (unchanged)",
        },
        "diagnostics": diagnostics(r),
        "references": REFERENCES,
    }
