"""Model 3 metrics (pre-registered in model3_plan.md section 5).

Score arrays per résumé family:
  S_named : (n_resumes, n_names + 1, n_postings)   last name slot = unnamed control
  S_word  : (n_resumes, n_items, 3 forms [plain, women, men], n_postings)
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from scipy.stats import rankdata, spearmanr
from sklearn.metrics import roc_auc_score

FORMS = ("plain", "women", "men")


# ---------------------------------------------------------------- validity
def tier_validity(S_unnamed: np.ndarray, tiers: np.ndarray) -> np.ndarray:
    """Spearman(tier, score) per posting. S_unnamed: (n_resumes, n_postings)."""
    return np.array([spearmanr(tiers, S_unnamed[:, j]).statistic for j in range(S_unnamed.shape[1])])


def family_auc(S_matched: np.ndarray, S_other: np.ndarray) -> np.ndarray:
    """ROC AUC per posting separating matched-family from other-family résumés."""
    out = []
    for j in range(S_matched.shape[1]):
        y = np.r_[np.ones(S_matched.shape[0]), np.zeros(S_other.shape[0])]
        out.append(roc_auc_score(y, np.r_[S_matched[:, j], S_other[:, j]]))
    return np.array(out)


# ---------------------------------------------------------------- M3-1
def posting_sd(S_named: np.ndarray) -> np.ndarray:
    """SD (ddof=1) of the unnamed scores across résumés, per posting."""
    return S_named[:, -1, :].std(axis=0, ddof=1)


def name_effects(S_named: np.ndarray) -> np.ndarray:
    """Standardized effect of each name vs the unnamed control, per posting.
    Returns (n_names, n_postings)."""
    sd = posting_sd(S_named)
    diff = S_named[:, :-1, :] - S_named[:, -1:, :]          # résumé x name x posting
    return diff.mean(axis=0) / sd                            # name x posting


def posting_gaps(S_named: np.ndarray, female_idx, male_idx) -> np.ndarray:
    """d_j = (mean women's-name score − mean men's-name score) / SD, per posting."""
    e = name_effects(S_named)
    return e[list(female_idx)].mean(axis=0) - e[list(male_idx)].mean(axis=0)


def all_splits(n_names: int = 20, k: int = 10) -> np.ndarray:
    return np.array(list(combinations(range(n_names), k)), dtype=np.int8)


def exact_permutation(E: np.ndarray, female_idx, splits: np.ndarray | None = None) -> dict:
    """Exact name-level permutation test of G = mean(E_women) − mean(E_men).
    E: per-name effect (posting-averaged). Two-sided."""
    E = np.asarray(E, dtype=float)
    n = E.shape[0]
    k = len(female_idx)
    splits = all_splits(n, k) if splits is None else splits
    total = E.sum()
    sums = E[splits].sum(axis=1)
    G_split = sums / k - (total - sums) / (n - k)
    G_obs = E[list(female_idx)].mean() - np.delete(E, list(female_idx)).mean()
    p = float(np.mean(np.abs(G_split) >= abs(G_obs) - 1e-12))
    return {"G": float(G_obs), "p_exact": p, "n_splits": int(len(splits)),
            "null_p025": float(np.percentile(G_split, 2.5)), "null_p975": float(np.percentile(G_split, 97.5))}


def holm(pvals: dict) -> dict:
    keys = sorted(pvals, key=lambda k: pvals[k])
    m = len(keys)
    out, running = {}, 0.0
    for i, k in enumerate(keys):
        running = max(running, min(1.0, (m - i) * pvals[k]))
        out[k] = running
    return out


# ---------------------------------------------------------------- M3-2 selection
def selection(S_cols: list[np.ndarray], group_a: list[int], group_b: list[int], pools: int,
              rate: float, seeds: list) -> dict:
    """Simulated pools per posting. S_cols[j]: (n_resumes, n_variants) scores for posting j.
    Half the résumés carry a random variant from group_a ("women"), half from group_b ("men");
    the top ``rate`` share is selected."""
    sel_a_tot = sel_b_tot = n_a_tot = n_b_tot = 0
    per_posting = []
    for S, seed in zip(S_cols, seeds):
        rng = np.random.default_rng(seed)
        n = S.shape[0]
        half = n // 2
        k = int(np.floor(rate * n))
        perm = np.argsort(rng.random((pools, n)), axis=1)          # pool x résumé order
        is_a = np.zeros((pools, n), dtype=bool)
        np.put_along_axis(is_a, perm[:, :half], True, axis=1)
        va = rng.integers(0, len(group_a), size=(pools, n))
        vb = rng.integers(0, len(group_b), size=(pools, n))
        variant = np.where(is_a, np.asarray(group_a)[va], np.asarray(group_b)[vb])
        scores = S[np.arange(n)[None, :], variant]                 # pool x résumé
        top = np.argpartition(-scores, k - 1, axis=1)[:, :k]
        sel_a = int(np.take_along_axis(is_a, top, axis=1).sum())
        sel_b = pools * k - sel_a
        n_a = int(is_a.sum())
        n_b = pools * n - n_a
        sel_a_tot += sel_a
        sel_b_tot += sel_b
        n_a_tot += n_a
        n_b_tot += n_b
        per_posting.append((sel_a / n_a) / (sel_b / n_b) if sel_b > 0 else float("nan"))
    pooled = (sel_a_tot / n_a_tot) / (sel_b_tot / n_b_tot)
    return {"pooled_ir": float(pooled), "per_posting_ir": np.array(per_posting)}


# ---------------------------------------------------------------- M3-3
def signflip(D: np.ndarray, n_perm: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    obs = abs(D.mean())
    signs = rng.choice([-1.0, 1.0], size=(n_perm, D.shape[0]))
    null = np.abs((signs * D[None, :]).mean(axis=1))
    return float((1 + np.sum(null >= obs - 1e-15)) / (n_perm + 1))


# ---------------------------------------------------------------- M3-4
def spearman_perm(x: np.ndarray, y: np.ndarray, n_perm: int, seed: int) -> dict:
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    rho = float(spearmanr(x, y).statistic)
    rng = np.random.default_rng(seed)
    rx, ry = rankdata(x), rankdata(y)
    rx = (rx - rx.mean()) / rx.std()
    ry = (ry - ry.mean()) / ry.std()
    null = np.array([np.mean(rx * rng.permutation(ry)) for _ in range(n_perm)])
    p = float((1 + np.sum(np.abs(null) >= abs(rho) - 1e-12)) / (n_perm + 1))
    return {"spearman": rho, "p_perm": p, "n": int(ok.sum())}
