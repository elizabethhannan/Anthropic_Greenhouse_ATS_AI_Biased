"""Impact ratios and Monte Carlo summaries for Model 2.

Selection rate (SR) = selected / applicants at risk, for one group at one stage.
Impact ratio = SR(women) / SR(men). The four-fifths convention treats a ratio
below 0.80 as the reference threshold (Uniform Guidelines on Employee Selection
Procedures, 1978).
"""

from __future__ import annotations

import math

import numpy as np

FOUR_FIFTHS = 0.80


def selection_rate(selected: int, at_risk: int) -> float:
    return float("nan") if at_risk == 0 else selected / at_risk


def impact_ratio(sel_f: int, n_f: int, sel_m: int, n_m: int) -> float:
    """SR(women) / SR(men). NaN when undefined."""
    sr_f = selection_rate(sel_f, n_f)
    sr_m = selection_rate(sel_m, n_m)
    if math.isnan(sr_f) or math.isnan(sr_m) or sr_m == 0:
        return float("nan")
    return sr_f / sr_m


def rnd(x, d: int = 4):
    """Round for JSON; NaN becomes None (JSON null)."""
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [rnd(v, d) for v in x]
    x = float(x)
    if math.isnan(x):
        return None
    return round(x, d) + 0.0  # +0.0 turns -0.0 into 0.0


def summarize(stack: np.ndarray, d: int = 4) -> dict:
    """stack: runs x cycles. Median and 5th/95th percentiles per cycle."""
    stack = np.asarray(stack, dtype=float)
    if np.all(np.isnan(stack)):
        n = stack.shape[1]
        return {"median": [None] * n, "p05": [None] * n, "p95": [None] * n}
    return {
        "median": rnd(np.nanmedian(stack, axis=0), d),
        "p05": rnd(np.nanpercentile(stack, 5, axis=0), d),
        "p95": rnd(np.nanpercentile(stack, 95, axis=0), d),
    }


def summarize_at(stack: np.ndarray, cycle: int, d: int = 4) -> dict:
    """Summary of one cycle (1-based)."""
    col = np.asarray(stack, dtype=float)[:, cycle - 1]
    if np.all(np.isnan(col)):
        return {"median": None, "p05": None, "p95": None}
    return {
        "median": rnd(np.nanmedian(col), d),
        "p05": rnd(np.nanpercentile(col, 5), d),
        "p95": rnd(np.nanpercentile(col, 95), d),
    }
