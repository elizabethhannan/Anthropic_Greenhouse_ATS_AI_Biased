"""P1: detection power for a four-fifths style audit of one role family.

SIMULATION — synthetic counts; not Anthropic data.

For a role family with A applicants in a reporting period, a stage with pass
rate s and a true impact ratio r, men's selection rate is
    s_m = s / (p*r + 1 - p)
and women's is r*s_m, so the overall pass rate equals s. Each replicate draws
the number of women at risk ~ Binomial(at_risk, p), then the selected women and
men as binomials. Reported per cell:
  (a) power of a two-sided Fisher's exact test at alpha;
  (b) P(observed impact ratio < 0.80); an undefined ratio counts as "not below"
      and is counted separately.
Stages (pre-registered):
  screen     at_risk = A,               pass rate = screen_pass
  interview  at_risk = floor(0.10 * A), pass rate = interview_pass
             (women at risk ~ Binomial(floor(0.10*A), p): an even-handed screen)
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy.stats import fisher_exact

FOUR_FIFTHS = 0.80


@lru_cache(maxsize=None)
def fisher_p(a: int, b: int, c: int, d: int) -> float:
    return float(fisher_exact([[a, b], [c, d]], alternative="two-sided").pvalue)


def stage_rates(s: float, p: float, r: float) -> tuple[float, float]:
    s_m = s / (p * r + 1 - p)
    return r * s_m, s_m


def at_risk_for(stage: str, A: int, shortlist_rate: float) -> int:
    if stage == "screen":
        return int(A)
    if stage == "interview":
        return int(math.floor(shortlist_rate * A))
    raise ValueError(stage)


def simulate_cell(A: int, p: float, r: float, stage: str, s: float, reps: int,
                  seed_key: list[int], alpha: float, shortlist_rate: float = 0.10) -> dict:
    rng = np.random.default_rng(seed_key)
    n = at_risk_for(stage, A, shortlist_rate)
    s_f, s_m = stage_rates(s, p, r)
    n_f = rng.binomial(n, p, size=reps)
    n_m = n - n_f
    x_f = rng.binomial(n_f, s_f)
    x_m = rng.binomial(n_m, s_m)
    reject = 0
    below = 0
    undefined = 0
    for a, nf, c, nm in zip(x_f.tolist(), n_f.tolist(), x_m.tolist(), n_m.tolist()):
        if fisher_p(a, nf - a, c, nm - c) < alpha:
            reject += 1
        if nf == 0 or nm == 0 or c == 0:
            undefined += 1
        elif (a / nf) / (c / nm) < FOUR_FIFTHS:
            below += 1
    return {"power": reject / reps, "p_below_080": below / reps, "undefined": undefined,
            "at_risk": n, "s_f": s_f, "s_m": s_m}


def power_table(pcfg: dict, shortlist_rate: float) -> list[dict]:
    rows = []
    stages = [("screen", pcfg["screen_pass"]), ("interview", pcfg["interview_pass"])]
    for si, (stage, s) in enumerate(stages):
        for pi, p in enumerate(pcfg["pool_share"]):
            for ri, r in enumerate(pcfg["true_ir"]):
                power_by_A, below_by_A, undef_by_A = {}, {}, {}
                for ai, A in enumerate(pcfg["applicants"]):
                    cell = simulate_cell(A, p, r, stage, s, pcfg["replicates"],
                                         [pcfg["seed"], si, pi, ri, ai], pcfg["alpha"], shortlist_rate)
                    power_by_A[str(A)] = round(cell["power"], 4)
                    below_by_A[str(A)] = round(cell["p_below_080"], 4)
                    undef_by_A[str(A)] = cell["undefined"]
                hits = [A for A in pcfg["applicants"] if power_by_A[str(A)] >= pcfg["target_power"]]
                rows.append({
                    "stage": stage, "pool_share_women": p, "true_ir": r, "stage_pass_rate": s,
                    "min_applicants_80pct": (min(hits) if hits else f"> {max(pcfg['applicants']):,}"),
                    "power_by_A": power_by_A,
                    "p_observed_below_080_by_A": below_by_A,
                    "undefined_ratio_count_by_A": undef_by_A,
                })
    return rows


def null_rejection_rate(A: int, p: float, stage: str, s: float, reps: int, seed: int,
                        alpha: float, shortlist_rate: float = 0.10) -> float:
    """Test 5 helper: rejection rate when the true impact ratio is 1.0."""
    return simulate_cell(A, p, 1.0, stage, s, reps, [seed, 99, int(A), int(p * 1000)], alpha,
                         shortlist_rate)["power"]
