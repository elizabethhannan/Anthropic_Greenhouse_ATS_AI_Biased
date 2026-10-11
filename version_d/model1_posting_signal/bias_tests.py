"""Step 6 (T7): family differences in gender-coded wording.

For masc_per_1k and fem_per_1k, each family is compared with Other:
permutation test on the mean difference (two-sided), bootstrap 95% CI
(resampling each group independently), Cliff's delta, and Holm correction
across all comparisons. Run on raw and sense-filtered scores.

A p-value above .05 for a small family (Fellows, n about 9) is not evidence of
no difference; report effect sizes and intervals.
"""

from __future__ import annotations

import numpy as np


def mean_diff(a, b) -> float:
    return float(np.mean(a) - np.mean(b))


def permutation_p(a, b, n_perm: int, rng: np.random.Generator) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    obs = abs(mean_diff(a, b))
    pooled = np.concatenate([a, b])
    na = a.size
    hits = 0
    for _ in range(n_perm):
        perm = rng.permutation(pooled)
        if abs(perm[:na].mean() - perm[na:].mean()) >= obs - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def bootstrap_ci(a, b, n_boot: int, rng: np.random.Generator, level: float = 0.95):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ia = rng.integers(0, a.size, size=(n_boot, a.size))
    ib = rng.integers(0, b.size, size=(n_boot, b.size))
    diffs = a[ia].mean(axis=1) - b[ib].mean(axis=1)
    lo, hi = np.percentile(diffs, [100 * (1 - level) / 2, 100 * (1 + level) / 2])
    return float(lo), float(hi)


def bootstrap_mean_ci(a, n_boot: int, rng: np.random.Generator, level: float = 0.95):
    a = np.asarray(a, float)
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    m = a[idx].mean(axis=1)
    lo, hi = np.percentile(m, [100 * (1 - level) / 2, 100 * (1 + level) / 2])
    return float(lo), float(hi)


def cliffs_delta(a, b) -> float:
    """P(A > B) - P(A < B) (Cliff, 1993)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    gt = (a[:, None] > b[None, :]).sum()
    lt = (a[:, None] < b[None, :]).sum()
    return float((gt - lt) / (a.size * b.size))


def holm(pvals: list[float]) -> list[float]:
    """Holm (1979) step-down adjusted p-values, monotone, capped at 1."""
    p = np.asarray(pvals, float)
    m = p.size
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        val = min(1.0, (m - rank) * p[idx])
        running = max(running, val)
        adj[idx] = running
    return adj.tolist()


def family_comparisons(scores: dict, families: list[str], reference: str, metrics: list[str],
                       variants: list[str], n_perm: int, n_boot: int, seed: int) -> list[dict]:
    """scores[variant][metric][family] -> array. Returns rows with Holm-adjusted p."""
    rng = np.random.default_rng(seed)
    rows = []
    for variant in variants:
        for metric in metrics:
            ref = scores[variant][metric][reference]
            for fam in families:
                if fam == reference:
                    continue
                x = scores[variant][metric][fam]
                if len(x) == 0 or len(ref) == 0:
                    continue
                rows.append({
                    "comparison": f"{fam} vs {reference}", "metric": metric, "variant": variant,
                    "n": len(x), "n_ref": len(ref),
                    "diff": mean_diff(x, ref),
                    "ci": list(bootstrap_ci(x, ref, n_boot, rng)),
                    "p_perm": permutation_p(x, ref, n_perm, rng),
                    "cliffs_delta": cliffs_delta(x, ref),
                })
    adj = holm([r["p_perm"] for r in rows])
    for r, a in zip(rows, adj):
        r["p_holm"] = a
    return rows
