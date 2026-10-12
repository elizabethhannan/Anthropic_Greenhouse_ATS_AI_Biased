"""Model 1b: the applicant-level mechanism test, built now and run later on internal data.

Binomial GLM on applicant counts per posting j:
    logit P(applicant is a woman) = alpha_family + beta * masc_per_1k
                                    + gamma * fem_per_1k + delta * named_women_share
with standard errors clustered by posting ID. Applicants of unknown sex are
excluded from the binomial denominator and counted separately.
named_women_share is 0 for postings that name no one (only Fellows postings name
people, so delta is identified within Fellows; the family intercept absorbs the
Fellows level).

validate() is an ESTIMATOR TEST ON SIMULATED DATA with a known beta. It is not a
result about Anthropic.

Input template: templates/applicants_by_posting.csv with columns
posting_id, role_family, applicants_women, applicants_men, applicants_unknown
(plus masc_per_1k, fem_per_1k, named_women_share joined from Model 1 outputs).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

TERMS = ["masc_per_1k", "fem_per_1k", "named_women_share"]


def design(df: pd.DataFrame, families: list[str]) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for f in families:  # full set of family intercepts, no global constant
        X[f"alpha[{f}]"] = (df["role_family"] == f).astype(float)
    for t in TERMS:
        X[t] = df[t].astype(float)
    return X


def fit(df: pd.DataFrame, families: list[str] | None = None):
    families = families or sorted(df["role_family"].unique())
    X = design(df, families)
    y = np.column_stack([df["applicants_women"].to_numpy(float), df["applicants_men"].to_numpy(float)])
    groups = pd.factorize(df["posting_id"])[0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sm.GLM(y, X, family=sm.families.Binomial()).fit(
            cov_type="cluster", cov_kwds={"groups": groups})
    return res


def simulate(cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    """One simulated data set with beta-binomial overdispersion; the marginal
    mean is exactly logit-linear, so the GLM estimand equals the true beta."""
    m = cfg["model1b"]
    n = m["postings"]
    fams = m["families"]
    fam = rng.choice(len(fams), size=n, p=m["family_shares"])
    masc = np.clip(rng.normal(8.0, 3.0, n), 0, None)
    fem = np.clip(rng.normal(6.0, 2.5, n), 0, None)
    nws = np.where(np.array(fams)[fam] == "Fellows", rng.uniform(0, 0.6, n), 0.0)
    eta = (np.array(m["alpha_by_family"])[fam] + m["true_beta"] * masc
           + m["true_gamma"] * fem + m["true_delta"] * nws)
    mu = 1 / (1 + np.exp(-eta))
    known = rng.poisson(m["mean_applicants"], n) + 5
    r = m["overdispersion_rho"]
    a, b = mu * (1 - r) / r, (1 - mu) * (1 - r) / r
    p = rng.beta(a, b)
    women = rng.binomial(known, p)
    unknown = rng.binomial(known, 0.1)
    return pd.DataFrame({
        "posting_id": [f"sim-{i:04d}" for i in range(n)],
        "role_family": np.array(fams)[fam],
        "applicants_women": women, "applicants_men": known - women, "applicants_unknown": unknown,
        "masc_per_1k": masc, "fem_per_1k": fem, "named_women_share": nws,
    })


def validate(cfg: dict) -> dict:
    """Coverage of the 95% CI for beta across simulated data sets."""
    m = cfg["model1b"]
    rng = np.random.default_rng(cfg["seed"])
    cover, est, ses = 0, [], []
    for _ in range(m["simulations"]):
        df = simulate(cfg, rng)
        res = fit(df, m["families"])
        b = float(res.params["masc_per_1k"])
        lo, hi = (float(v) for v in res.conf_int().loc["masc_per_1k"])
        cover += lo <= m["true_beta"] <= hi
        est.append(b)
        ses.append(float(res.bse["masc_per_1k"]))
    cov = cover / m["simulations"]
    return {
        "label": "ESTIMATOR TEST ON SIMULATED DATA — not a result",
        "simulations": m["simulations"], "true_beta": m["true_beta"],
        "coverage_in_simulation": cov, "coverage_target": m["coverage_target"],
        "passes": cov >= m["coverage_target"],
        "mean_estimate": float(np.mean(est)), "empirical_sd": float(np.std(est, ddof=1)),
        "mean_cluster_se": float(np.mean(ses)),
    }


if __name__ == "__main__":
    import json
    from pathlib import Path

    import yaml
    here = Path(__file__).resolve().parent
    cfg = yaml.safe_load((here / "config.yaml").read_text())
    print(json.dumps(validate(cfg), indent=2))
