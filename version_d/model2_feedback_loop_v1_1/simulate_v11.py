"""Model 2 v1.1 simulation core.

SIMULATION — synthetic applicants; not Anthropic data.

Extends the v1.0 core (``simulate.py``, kept unchanged in this folder) with the
five pre-registered extensions in ``v1_1_plan.md``:

- X1  ``w``       interviewer reliance on the screen score
- X2  ``eps``     exploration: a random share of screened-out applicants is interviewed
- X3  ``screener``  "logistic" (v1.0) or "boosted" (HistGradientBoostingClassifier)
- X4  ``lam``     proxy partly job-relevant: x3 = rho*f + lam*q + e3
- X5  ``window``  "last" (v1.0) or "cumulative" (train on every earlier cycle)

With w = 0, eps = 0, screener = "logistic", lam = 0 and window = "last",
``run_one`` reproduces v1.0's ``simulate.run_one`` exactly for the same seed
(test 1). Extra random draws (exploration, permutation importance) come from
separate streams seeded from the run seed, so the applicant draws never change.

Sex (``female``) is never a screener input; ``feature_matrix`` enforces that for
both screener types.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from metrics import impact_ratio
from simulate import Pool, feature_matrix, reweigh, top_k_mask
from simulate import train_screener as train_logistic

SCREENERS = ("logistic", "boosted")
WINDOWS = ("last", "cumulative")

METRICS = (
    "screen_impact_ratio",
    "interview_impact_ratio",
    "overall_impact_ratio",
    "hire_share_women",
    "proxy_signal",
    "screen_validity",
    "n_shortlisted",
    "n_interviewed",
    "n_hired",
)


def draw_pool(rng: np.random.Generator, n: int, p: float, rho: float, sigma_x: float,
              lam: float = 0.0) -> Pool:
    """Same draw order as v1.0. ``lam`` adds job signal to the proxy (X4)."""
    u = rng.random(n)
    q = rng.standard_normal(n)
    e1 = rng.standard_normal(n)
    e2 = rng.standard_normal(n)
    e3 = rng.standard_normal(n)
    eta = rng.standard_normal(n)
    female = (u < p).astype(np.int8)
    x3 = rho * female + e3 if lam == 0 else rho * female + lam * q + e3
    feats = {"x1": q + sigma_x * e1, "x2": q + sigma_x * e2, "x3": x3}
    return Pool(female=female, q=q, eta_std=eta, features=feats)


def concat_pools(pools: list[Pool]) -> Pool:
    return Pool(
        female=np.concatenate([p.female for p in pools]),
        q=np.concatenate([p.q for p in pools]),
        eta_std=np.concatenate([p.eta_std for p in pools]),
        features={f: np.concatenate([p.features[f] for p in pools]) for f in pools[0].features},
    )


@dataclass
class BoostedScreener:
    features: tuple
    model: HistGradientBoostingClassifier

    def score(self, pool: Pool) -> np.ndarray:
        return self.model.decision_function(feature_matrix(pool, self.features))

    def coef(self, name: str) -> float:  # no single coefficient
        return float("nan")


def train_boosted(pool: Pool, y: np.ndarray, features, seed: int, weights=None) -> BoostedScreener:
    X = feature_matrix(pool, features)
    model = HistGradientBoostingClassifier(random_state=seed)  # scikit-learn defaults
    model.fit(X, y, sample_weight=weights)
    return BoostedScreener(features=tuple(features), model=model)


def permutation_importance_x3(screener: BoostedScreener, pool: Pool, y: np.ndarray,
                              rng: np.random.Generator, n_sub: int, n_rep: int) -> float:
    """Mean drop in ROC AUC when x3 is shuffled, on a seeded random subsample."""
    if "x3" not in screener.features:
        return float("nan")
    size = min(n_sub, pool.n)
    idx = np.sort(rng.choice(pool.n, size=size, replace=False))
    X = feature_matrix(pool, screener.features)[idx]
    yy = y[idx]
    if yy.min() == yy.max():
        return float("nan")
    base = roc_auc_score(yy, screener.model.decision_function(X))
    j = list(screener.features).index("x3")
    drops = []
    for _ in range(n_rep):
        Xp = X.copy()
        Xp[:, j] = rng.permutation(Xp[:, j])
        drops.append(base - roc_auc_score(yy, screener.model.decision_function(Xp)))
    return float(np.mean(drops))


def _z(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / sd if sd > 0 else np.zeros_like(x)


def run_one(seed: int, params: dict) -> dict:
    """One Monte Carlo run with the v1.1 options. Returns per-cycle arrays (cycles 1..T)."""
    rng = np.random.default_rng(seed)
    rng_explore = np.random.default_rng([seed, 1])   # X2 draws only
    rng_perm = np.random.default_rng([seed, 2])      # X3 permutation importance only

    n = params["N"]
    k = int(np.floor(params["hire_rate"] * n))
    m = int(np.floor(params["shortlist_rate"] * n))
    p, rho = params["p"], params["rho"]
    sx, si = params["sigma_x"], params["sigma_i"]
    d0, dh = params["delta0"], params["delta_h"]
    T = params["T"]
    feats = tuple(params["features"])
    reweigh_on = bool(params.get("reweigh", False))
    freeze_after = params.get("freeze_after")
    want_validity = bool(params.get("compute_validity", True))
    w = float(params.get("w", 0.0))
    eps = float(params.get("eps", 0.0))
    kind = params.get("screener", "logistic")
    lam = float(params.get("lam", 0.0))
    window = params.get("window", "last")
    n_sub = int(params.get("perm_subsample", 2000))
    n_rep = int(params.get("perm_repeats", 5))
    if kind not in SCREENERS:
        raise ValueError(f"unknown screener {kind!r}")
    if window not in WINDOWS:
        raise ValueError(f"unknown window {window!r}")
    n_explore = int(np.floor(eps * n))

    out = {name: np.full(T, np.nan) for name in METRICS}
    seen_features = []

    # Cycle 0: no screening model (as v1.0, with lam passed to the draw)
    pool0 = draw_pool(rng, n, p, rho, sx, lam)
    s0 = pool0.q + si * pool0.eta_std - d0 * pool0.female
    hired0 = top_k_mask(s0, k)
    history = [(pool0, hired0)]
    prev_pool, prev_y = pool0, hired0
    cycle0_share = float(pool0.female[hired0].mean())

    screener, proxy = None, float("nan")
    for t in range(1, T + 1):
        # 1. Train (screened-out applicants are labeled 0, as v1.0)
        if screener is None or freeze_after is None or t <= freeze_after:
            if window == "cumulative":
                tr_pool = concat_pools([h[0] for h in history])
                tr_y = np.concatenate([h[1] for h in history]).astype(int)
            else:
                tr_pool, tr_y = prev_pool, prev_y.astype(int)
            wts = reweigh(tr_pool.female, tr_y) if reweigh_on else None
            if kind == "logistic":
                screener = train_logistic(tr_pool, tr_y, feats, params["logreg_C"], wts)
                proxy = screener.coef("x3")
            else:
                screener = train_boosted(tr_pool, tr_y, feats, seed, wts)
                proxy = permutation_importance_x3(screener, tr_pool, tr_y, rng_perm, n_sub, n_rep)
        seen_features.append(screener.features)

        # 2. Screen a fresh pool
        pool = draw_pool(rng, n, p, rho, sx, lam)
        score = screener.score(pool)
        shortlist = top_k_mask(score, m)

        # 2b. X2 exploration: add a random share of the screened-out to the interview pool
        interviewed = shortlist.copy()
        if n_explore > 0:
            out_idx = np.flatnonzero(~shortlist)
            pick = rng_explore.choice(out_idx, size=n_explore, replace=False)
            interviewed[pick] = True

        # 3. Interview; X1 mixes in the standardized screen score
        human = pool.q + si * pool.eta_std - dh * pool.female
        if w == 0:
            iv_score = human
        else:
            iv = np.flatnonzero(interviewed)
            iv_score = np.full(n, -np.inf)
            iv_score[iv] = (1 - w) * _z(human[iv]) + w * _z(score[iv])
        hired = top_k_mask(iv_score, k, among=interviewed)

        # 4. Record
        fem = pool.female.astype(bool)
        n_f, n_m = int(fem.sum()), int((~fem).sum())
        sl_f, sl_m = int((shortlist & fem).sum()), int((shortlist & ~fem).sum())
        iv_f, iv_m = int((interviewed & fem).sum()), int((interviewed & ~fem).sum())
        h_f, h_m = int((hired & fem).sum()), int((hired & ~fem).sum())
        i = t - 1
        out["screen_impact_ratio"][i] = impact_ratio(sl_f, n_f, sl_m, n_m)
        out["interview_impact_ratio"][i] = impact_ratio(h_f, iv_f, h_m, iv_m)
        out["overall_impact_ratio"][i] = impact_ratio(h_f, n_f, h_m, n_m)
        out["hire_share_women"][i] = h_f / k
        out["proxy_signal"][i] = proxy
        if want_validity:
            out["screen_validity"][i] = spearmanr(score, pool.q).statistic
        out["n_shortlisted"][i] = int(shortlist.sum())
        out["n_interviewed"][i] = int(interviewed.sum())
        out["n_hired"][i] = int(hired.sum())

        history.append((pool, hired))
        prev_pool, prev_y = pool, hired

    out["cycle0_hire_share_women"] = cycle0_share
    out["seen_features"] = seen_features
    return out
