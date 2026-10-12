"""Model 2 simulation core: applicant generation, history, screening, interview.

SIMULATION — synthetic applicants; not Anthropic data.

Sex (``female``) is used only to generate applicants, to compute metrics, and
(in intervention I2 only) to compute training weights. It is never a column of
the screener's feature matrix; ``feature_matrix`` enforces that.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from metrics import impact_ratio

ALLOWED_FEATURES = ("x1", "x2", "x3")


@dataclass
class Pool:
    """One cycle's applicants. ``features`` never contains sex."""

    female: np.ndarray            # 1 = woman, 0 = man (metrics / generation / I2 weights only)
    q: np.ndarray                 # latent qualification (never observed by the screener)
    eta_std: np.ndarray           # standard-normal interview noise, scaled by sigma_i at use
    features: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return int(self.female.shape[0])


def draw_pool(rng: np.random.Generator, n: int, p: float, rho: float, sigma_x: float) -> Pool:
    """Draw a pool. The draw order is fixed so that runs with the same seed share
    random numbers across scenarios (common random numbers)."""
    u = rng.random(n)
    q = rng.standard_normal(n)
    e1 = rng.standard_normal(n)
    e2 = rng.standard_normal(n)
    e3 = rng.standard_normal(n)
    eta = rng.standard_normal(n)
    female = (u < p).astype(np.int8)
    feats = {
        "x1": q + sigma_x * e1,
        "x2": q + sigma_x * e2,
        "x3": rho * female + e3,
    }
    return Pool(female=female, q=q, eta_std=eta, features=feats)


def top_k_mask(scores: np.ndarray, k: int, among: np.ndarray | None = None) -> np.ndarray:
    """Boolean mask of the k highest scores (optionally only among ``among``)."""
    mask = np.zeros(scores.shape[0], dtype=bool)
    if among is None:
        idx = np.argpartition(-scores, k - 1)[:k]
        mask[idx] = True
        return mask
    cand = np.flatnonzero(among)
    sub = scores[cand]
    idx = cand[np.argpartition(-sub, k - 1)[:k]]
    mask[idx] = True
    return mask


def feature_matrix(pool: Pool, features: list[str] | tuple[str, ...]) -> np.ndarray:
    """Build the screener input. Only configured, allowed columns; never sex."""
    feats = list(features)
    for f in feats:
        if f not in ALLOWED_FEATURES:
            raise ValueError(f"feature {f!r} is not an allowed screener input")
    if "female" in feats or "sex" in feats:
        raise ValueError("sex must never be a screener feature")
    return np.column_stack([pool.features[f] for f in feats])


def reweigh(female: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Kamiran & Calders (2012) reweighing: w(s, y) = P(s) P(y) / P(s, y)."""
    w = np.empty(y.shape[0], dtype=float)
    n = y.shape[0]
    for s in (0, 1):
        ps = np.mean(female == s)
        for lab in (0, 1):
            cell = (female == s) & (y == lab)
            pyl = np.mean(y == lab)
            psy = cell.sum() / n
            w[cell] = (ps * pyl / psy) if psy > 0 else 0.0
    return w


@dataclass
class Screener:
    features: tuple
    scaler: StandardScaler
    model: LogisticRegression

    def score(self, pool: Pool) -> np.ndarray:
        X = self.scaler.transform(feature_matrix(pool, self.features))
        return self.model.decision_function(X)

    def coef(self, name: str) -> float:
        if name not in self.features:
            return float("nan")
        return float(self.model.coef_[0][list(self.features).index(name)])


def train_screener(pool: Pool, y: np.ndarray, features, C: float, weights=None) -> Screener:
    X = feature_matrix(pool, features)
    scaler = StandardScaler().fit(X)
    model = LogisticRegression(C=C, solver="lbfgs", max_iter=1000)  # L2 penalty (default)
    model.fit(scaler.transform(X), y, sample_weight=weights)
    return Screener(features=tuple(features), scaler=scaler, model=model)


def history_cycle(rng, n, p, rho, sigma_x, sigma_i, k, delta0):
    """Cycle 0: no screening model. Hire top k by q + eta - delta0 * female."""
    pool = draw_pool(rng, n, p, rho, sigma_x)
    s = pool.q + sigma_i * pool.eta_std - delta0 * pool.female
    hired = top_k_mask(s, k)
    return pool, hired


METRICS = (
    "screen_impact_ratio",
    "interview_impact_ratio",
    "overall_impact_ratio",
    "hire_share_women",
    "proxy_weight",
    "screen_validity",
    "n_shortlisted",
    "n_hired",
)


def run_one(seed: int, params: dict) -> dict:
    """One Monte Carlo run. Returns per-cycle metric arrays (cycles 1..T) plus
    cycle-0 diagnostics and the feature lists the screener actually saw."""
    rng = np.random.default_rng(seed)
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

    out = {name: np.full(T, np.nan) for name in METRICS}
    seen_features = []

    prev_pool, prev_y = history_cycle(rng, n, p, rho, sx, si, k, d0)
    cycle0_share = float(prev_pool.female[prev_y].mean())

    screener = None
    for t in range(1, T + 1):
        # 1. Train on cycle t-1 outcomes (screened-out applicants are labeled 0)
        if screener is None or freeze_after is None or t <= freeze_after:
            y = prev_y.astype(int)
            w = reweigh(prev_pool.female, y) if reweigh_on else None
            screener = train_screener(prev_pool, y, feats, params["logreg_C"], w)
        seen_features.append(screener.features)

        # 2. Screen a fresh pool
        pool = draw_pool(rng, n, p, rho, sx)
        score = screener.score(pool)
        shortlist = top_k_mask(score, m)

        # 3. Interview the shortlist
        interview = pool.q + si * pool.eta_std - dh * pool.female
        hired = top_k_mask(interview, k, among=shortlist)

        # 4. Record
        fem = pool.female.astype(bool)
        n_f, n_m = int(fem.sum()), int((~fem).sum())
        sl_f, sl_m = int((shortlist & fem).sum()), int((shortlist & ~fem).sum())
        h_f, h_m = int((hired & fem).sum()), int((hired & ~fem).sum())
        i = t - 1
        out["screen_impact_ratio"][i] = impact_ratio(sl_f, n_f, sl_m, n_m)
        out["interview_impact_ratio"][i] = impact_ratio(h_f, sl_f, h_m, sl_m)
        out["overall_impact_ratio"][i] = impact_ratio(h_f, n_f, h_m, n_m)
        out["hire_share_women"][i] = h_f / k
        out["proxy_weight"][i] = screener.coef("x3")
        if want_validity:
            out["screen_validity"][i] = spearmanr(score, pool.q).statistic
        out["n_shortlisted"][i] = int(shortlist.sum())
        out["n_hired"][i] = int(hired.sum())

        prev_pool, prev_y = pool, hired

    out["cycle0_hire_share_women"] = cycle0_share
    out["seen_features"] = seen_features
    return out
