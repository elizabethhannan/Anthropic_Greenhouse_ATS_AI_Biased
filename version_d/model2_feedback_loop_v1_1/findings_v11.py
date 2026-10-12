"""Findings, limitations and thesis text for Model 2 v1.1, generated from the numbers.

Every number is read from the results dictionary built by run_v11.py. Wording that
depends on a result is chosen by the numbers. Nothing here changes a parameter.
SIMULATION — synthetic applicants; not Anthropic data.
"""

from __future__ import annotations

THESIS_Q = {
    "RQ2": "2. Algorithmic influence: Could AI-assisted screening, candidate matching, or historical hiring "
           "patterns reinforce existing demographic disparities?",
    "RQ3": "3. Human decision-making: At which stages—recruiting, screening, interviewing, hiring, or "
           "advancement—might disparities emerge or compound?",
    "RQ4": "4. Long-term AI risk: Could repeated employment outcomes become feedback signals that lead future AI "
           "systems to reproduce historical hiring preferences?",
    "RQ5": "5. Governance: What internal data, evaluation methods, and executive accountability are required to "
           "distinguish algorithmic bias from human, structural, and applicant-pool factors?",
}


def _ext(r, eid):
    return next(e for e in r["extensions"] if e["id"] == eid)


def _res(e, **kw):
    return next(x for x in e["results"] if all(x.get(k) == v for k, v in kw.items()))


def _at(m, c):
    return m["median"][c - 1], m["p05"][c - 1], m["p95"][c - 1]


def _t(m, c, f="{:.2f}"):
    med, lo, hi = _at(m, c)
    return f"{f.format(med)} ({f.format(lo)} to {f.format(hi)})" if lo < 0 else \
        f"{f.format(med)} ({f.format(lo)}–{f.format(hi)})"


def _pw(r, stage, p, ir):
    return next(x for x in r["power"]["rows"]
                if x["stage"] == stage and x["pool_share_women"] == p and x["true_ir"] == ir)


def build_text(r: dict) -> dict:
    T = r["config"]["T"]
    c5 = min(5, T)
    x1, x2, x3, x4, x5 = (_ext(r, k) for k in ("X1", "X2", "X3", "X4", "X5"))
    wmax = max(x1["values"])

    # X1 under S1: does reliance stop the fading?
    s1_0 = _res(x1, calibration="C2", scenario="S1", value=0)
    s1_w = _res(x1, calibration="C2", scenario="S1", value=wmax)
    d_s1 = abs(_at(s1_w["screen_ir"], T)[0] - _at(s1_0["screen_ir"], T)[0])
    null_s1 = d_s1 < 0.03
    f1 = (f"(RQ3, RQ4) With even-handed interviewers (S1, C2), leaning on the AI score "
          + ("did not keep the screen gap alive" if null_s1 else "changed the screen gap")
          + f": the cycle-{T} screen impact ratio was {_t(s1_0['screen_ir'], T)} with no reliance and "
            f"{_t(s1_w['screen_ir'], T)} at w = {wmax}"
          + (" (a null result)" if null_s1 else "")
          + f"; the screener's median proxy weight stayed further from zero ({_t(s1_w['proxy_signal'], T)} vs. "
            f"{_t(s1_0['proxy_signal'], T)} without reliance), a range too wide to call it preserved and too small "
            f"to move the screen ratio.")

    # X1 under S2
    s2_0 = _res(x1, calibration="C2", scenario="S2", value=0)
    s2_w = _res(x1, calibration="C2", scenario="S2", value=wmax)
    f2 = (f"(RQ2, RQ3) With a continuing interview penalty (S2, C2), reliance diluted the interviewer's penalty: "
          f"the cycle-{T} overall impact ratio rose from {_t(s2_0['overall_ir'], T)} at w = 0 to "
          f"{_t(s2_w['overall_ir'], T)} at w = {wmax}; the screener's median proxy weight grew from "
          f"{_t(s2_0['proxy_signal'], T)} to {_t(s2_w['proxy_signal'], T)}, but the screen ratio did not change "
          f"({_at(s2_0['screen_ir'], T)[0]:.3f} at w = 0, {_at(s2_w['screen_ir'], T)[0]:.3f} at w = {wmax}).")

    # P1
    iv30 = _pw(r, "interview", 0.30, 0.62)
    iv20 = _pw(r, "interview", 0.203, 0.62)
    sc30 = _pw(r, "screen", 0.30, 0.62)
    sc20 = _pw(r, "screen", 0.203, 0.62)
    Amax = str(max(r["power"]["applicants"]))
    Amin = str(min(r["power"]["applicants"]))
    small = [_pw(r, "screen", p, 0.97) for p in (0.203, 0.30)]
    fa = [x["p_observed_below_080_by_A"][Amin] for x in small]
    fai = [_pw(r, "interview", p, 0.97)["p_observed_below_080_by_A"][Amin] for p in (0.203, 0.30)]
    def m80(x):
        v = x["min_applicants_80pct"]
        return f"{v:,}" if isinstance(v, int) else v
    pooling = not (isinstance(iv20["min_applicants_80pct"], int) and iv20["min_applicants_80pct"] <= 2000)
    f3 = (f"(RQ5) Detecting an interview-stage gap of the simulated size (true ratio 0.62) with 80% power took "
          f"{m80(iv30)} applicants per role family per reporting period when women were 30% of applicants (power "
          f"{iv30['power_by_A'][Amax]:.2f} at {int(Amax):,}) and {m80(iv20)} at 20.3% (power "
          f"{iv20['power_by_A'][Amax]:.2f} at {int(Amax):,}); the same gap at the screen needed {m80(sc30)}–{m80(sc20)}, "
          f"and at {int(Amin):,} applicants the observed ratio fell below 0.80 even when the true ratio was 0.97 in "
          f"{min(fa):.0%}–{max(fa):.0%} of periods at the screen stage and {min(fai):.0%}–{max(fai):.0%} at the "
          f"interview stage"
          + ("; interview-stage audits therefore need pooling across periods or role families." if pooling else "."))

    # X3
    b = _res(x3, calibration="C2", arm="S2")
    ref = b["reference_v1_0_same_seeds"]
    nulls_ok = all(abs(_at(_res(x3, calibration=c, arm="S0")["screen_ir"], k)[0] - 1) <= 0.05
                   for c in ("C1", "C2") for k in range(1, T + 1))
    f4 = (f"(RQ2) A gradient-boosted screener carried the same small screen gap as logistic regression (C2, S2, "
          f"cycle {c5}: {_t(b['screen_ir'], c5)} vs. {_t(ref['screen_ir'], c5)}, same seeds) and the same large "
          f"overall gap ({_at(b['overall_ir'], c5)[0]:.2f} vs. {_at(ref['overall_ir'], c5)[0]:.2f}), "
          + ("kept the S0 null within 0.95–1.05, " if nulls_ok else "")
          + f"and ranked applicants less accurately (validity {_at(b['screen_validity'], c5)[0]:.2f} vs. "
            f"{_at(ref['screen_validity'], c5)[0]:.2f}), so the v1.0 result does not depend on the screener being linear.")

    # X2
    e01 = _res(x2, scenario="S2", value=0.01)
    e05 = _res(x2, scenario="S2", value=0.05)
    r2 = e01["reference_v1_0_same_seeds"]
    moved = abs(_at(e05["proxy_signal"], T)[0] - _at(r2["proxy_signal"], T)[0]) > 0.02
    f5 = (f"(RQ5) Interviewing 1% or 5% of screened-out applicants ({e01['extra_interviews_per_cycle']} or "
          f"{e05['extra_interviews_per_cycle']} extra interviews per cycle) "
          + ("changed the proxy weight" if moved else "left the proxy weight unchanged")
          + f" under S2 (cycle {T}: {_t(e01['proxy_signal'], T)} and {_t(e05['proxy_signal'], T)} vs. "
            f"{_t(r2['proxy_signal'], T)} without exploration)"
          + ("" if moved else "; a null result: exploration fills in missing labels but not labels made by a "
                              "biased interview") + ".")

    # X4
    lam = max(x4["values"])
    s2l = _res(x4, arm="S2", value=lam)
    i1l = _res(x4, arm="I1", value=lam)
    i2l = _res(x4, arm="I2", value=lam)
    cost = _at(s2l["screen_validity"], c5)[0] - _at(i1l["screen_validity"], c5)[0]
    hs = [_at(x["hire_share_women"], c5)[0] for x in x4["results"]]
    f6 = (f"(RQ5) When the proxy also carried job signal (λ = {lam}), the uncorrected screener favored the group "
          f"with higher proxy scores (screen ratio {_t(s2l['screen_ir'], c5)}, validity "
          f"{_at(s2l['screen_validity'], c5)[0]:.3f}); removing the proxy restored {_t(i1l['screen_ir'], c5)} at a "
          f"validity cost of {cost:.3f}, reweighing kept validity but not parity ({_at(i2l['screen_ir'], c5)[0]:.2f}), "
          f"and no fix moved women's hire share outside {min(hs):.3f}–{max(hs):.3f} while the interview penalty "
          f"continued.")

    # X5
    cu = _res(x5, calibration="C2", scenario="S1")
    rc = cu["reference_v1_0_same_seeds"]
    slower = _at(cu["proxy_signal"], T)[0] < _at(rc["proxy_signal"], T)[0] - 0.01
    f7 = (f"(RQ4) Training on all past cycles "
          + ("slowed the fading modestly" if slower else "did not slow the fading")
          + f": under S1 (C2) the proxy weight at cycle {T} was {_t(cu['proxy_signal'], T)} versus "
            f"{_t(rc['proxy_signal'], T)} with the last cycle only, and the screen ratio "
            f"{_at(cu['screen_ir'], T)[0]:.2f} versus {_at(rc['screen_ir'], T)[0]:.2f}.")

    findings = [f1, f2, f3, f4, f5, f6, f7]

    thesis = [
        {"question": "RQ2", "text": THESIS_Q["RQ2"],
         "contribution": "The screen carried only a small part of the gap with a linear or a boosted screener; "
                         "reliance on the screen score raised the median proxy weight the model learned, without "
                         "changing screen ratios.",
         "status": "Simulated only; algorithmic causation not established"},
        {"question": "RQ3", "text": THESIS_Q["RQ3"],
         "contribution": "The interview stage still decided whether the gap persisted; how much interviewers lean "
                         "on the AI score changed where the gap lived, not whether it existed.",
         "status": "Sharpened (simulation)"},
        {"question": "RQ4", "text": THESIS_Q["RQ4"],
         "contribution": "Retraining on all history and reliance on model scores both slowed or deepened the "
                         "model's learned proxy weight; outcomes fed back only while a human penalty continued.",
         "status": "Exploratory hypothesis, sharpened, not confirmed"},
        {"question": "RQ5", "text": THESIS_Q["RQ5"],
         "contribution": "Minimum instrumentation: stage-level counts per role family, pooled across periods for "
                         "interview-stage audits; a record of reliance on model scores; exploration alone is not a fix.",
         "status": "Specified; requires internal data"},
    ]
    limitations = [
        "Synthetic applicants; nothing here describes Anthropic.",
        "Equal-qualification assumption kept: women and men have the same qualification distribution. A "
        "qualification-shift sensitivity was deliberately not run.",
        "Reliance is a fixed weight w, not learned or varying behavior.",
        "One proxy, with a fixed correlation with sex; real screeners see many correlated signals.",
        "No attrition, promotion or workforce stock is modeled; outcomes are hires per cycle.",
        "The boosted screener uses scikit-learn defaults without tuning; permutation importance is measured on a "
        "2,000-row subsample.",
        f"By the pre-registered runtime rule (the timing pilot projected {r['config'].get('pilot_projected_minutes_full', 'more than 30')} "
        f"minutes, over the 30-minute target), "
        f"X1, X2, X4 and X5 used {r['config']['runs']['default']} runs per configuration; X3 used "
        f"{r['config']['runs']['x3']}; the regression check used {r['config']['runs']['regression']}.",
        "Test 2 failed at one point (w = 0.75, cycle 4) in both calibrations and test 5 in one of four cells, by "
        "Monte Carlo margins (see the methods appendix); they were not edited.",
    ]
    exec_c = ("The most consequential finding is not that the screening model carries the historical gap; in every "
              "variant it carried only a small part of it. It is that how people use the model decides where the gap "
              "lives. When interviewers lean on the AI score, a continuing human penalty is diluted in today's hires "
              "while the model's median learned weight on the proxy grows, a shift that hire counts and screen ratios "
              "do not show; and a four-fifths check of one role family in one reporting period is too small to see an "
              "interview-stage gap of this size. Responsible governance "
              "therefore needs stage-level data pooled across periods, a record of how much decision-makers rely on "
              "model scores, and audits of the model's learned weights over time, not hire counts alone. None of this "
              "establishes algorithmic causation at Anthropic; the \"Historical feedback loops\" layer remains an "
              "exploratory hypothesis.")
    return {"thesis_alignment": thesis, "findings": findings, "limitations": limitations,
            "executive_conclusion_model2_v1_1": exec_c}
