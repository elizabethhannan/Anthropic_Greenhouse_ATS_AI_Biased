"""Calibrate the historical penalty delta0 (Brent's method).

delta0 is set so the mean women's share of cycle-0 hires, over a fixed set of
calibration seeds, equals the target h0. The same seeds are used at every trial
delta (common random numbers), so the objective is deterministic.

Cycle 0 ranks applicants on q + eta - delta0 * female; it does not use the
proxy, so delta0 depends on the pool share p and h0 only (not on rho).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.optimize import brentq

from simulate import draw_pool, top_k_mask


def calibration_seeds(cfg: dict) -> list[int]:
    c = cfg["calibration"]
    return [cfg["base_seed"] + c["seed_offset"] + j for j in range(c["n_seeds"])]


def _pools(cfg: dict, p: float):
    pools = []
    for s in calibration_seeds(cfg):
        rng = np.random.default_rng(s)
        pool = draw_pool(rng, cfg["N"], p, cfg["rho"], cfg["sigma_x"])
        pools.append((pool.q + cfg["sigma_i"] * pool.eta_std, pool.female))
    return pools


def mean_cycle0_share(delta: float, pools, k: int) -> float:
    shares = []
    for base, female in pools:
        hired = top_k_mask(base - delta * female, k)
        shares.append(female[hired].mean())
    return float(np.mean(shares))


def calibrate_delta0(cfg: dict, p: float, h0: float) -> dict:
    """Return {'delta0', 'achieved', 'n_evals'} for pool share p and target h0."""
    return dict(_calibrate_cached(_cfg_key(cfg), float(p), float(h0)))


# --- caching keyed on the parameters that matter for cycle 0 -----------------
_CFG_STORE: dict = {}


def _cfg_key(cfg: dict):
    key = (cfg["base_seed"], cfg["calibration"]["seed_offset"], cfg["calibration"]["n_seeds"],
           cfg["N"], cfg["hire_rate"], cfg["sigma_x"], cfg["sigma_i"], cfg["rho"],
           cfg["calibration"]["xtol"], tuple(cfg["calibration"]["bracket"]))
    _CFG_STORE[key] = cfg
    return key


@lru_cache(maxsize=None)
def _calibrate_cached(key, p: float, h0: float):
    cfg = _CFG_STORE[key]
    k = int(np.floor(cfg["hire_rate"] * cfg["N"]))
    pools = _pools(cfg, p)
    evals = {"n": 0}

    def f(d):
        evals["n"] += 1
        return mean_cycle0_share(d, pools, k) - h0

    lo, hi = cfg["calibration"]["bracket"]
    delta0 = brentq(f, lo, hi, xtol=cfg["calibration"]["xtol"])
    achieved = mean_cycle0_share(delta0, pools, k)
    return (("delta0", float(delta0)), ("achieved", float(achieved)), ("n_evals", evals["n"]))
