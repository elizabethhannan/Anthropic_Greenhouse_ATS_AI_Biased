"""Model 2 v1.1 tests 1–7 (pre-registered in v1_1_plan.md). If a test fails,
report it; do not edit it to pass.

Run from version_d/model2_feedback_loop_v1_1/:  pytest -q tests/test_model2_v1_1.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import run_experiments as rx  # noqa: E402
import run_v11  # noqa: E402
from calibrate import calibrate_delta0  # noqa: E402
from metrics import summarize  # noqa: E402
from power import null_rejection_rate  # noqa: E402
from simulate import feature_matrix  # noqa: E402
from simulate_v11 import draw_pool, run_one, train_boosted  # noqa: E402

CFG = rx.load_config()
V11 = run_v11.load_v11()
SCEN = {s["id"]: s for s in CFG["scenarios"]}
CALS = {c["id"]: c for c in CFG["calibrations"]}
V10_JSON = (HERE / V11["v1_0_results"]).resolve()


def _cals_for(cal):
    p = cal["pool_share_women"]
    return {(p, CFG["h0_target"]): calibrate_delta0(CFG, p, CFG["h0_target"]),
            (p, p): calibrate_delta0(CFG, p, p)}


def _params(scen_id, cal_id, **upd):
    cal = CALS[cal_id]
    params, _ = rx.scenario_params(CFG, SCEN[scen_id], cal, _cals_for(cal))
    params.update(upd)
    return params


def _batch(params, runs):
    return run_v11.run_batch(CFG, params, runs)


# 1 -----------------------------------------------------------------------------
def test_1_regression_to_v1_0():
    """w=0, eps=0, logistic, lam=0, last window reproduce v1.0's S0–S3 (C1, C2) exactly."""
    v1 = json.loads(V10_JSON.read_text(encoding="utf-8"))
    d = CFG["decimals"]
    compared = 0
    for s in v1["scenarios"]:
        params = _params(s["id"], s["calibration"], w=0.0, eps=0.0, screener="logistic", lam=0.0,
                         window="last")
        res = _batch(params, CFG["runs"])
        for k10, m11 in run_v11.V10_SCEN_METRICS.items():
            got = summarize(run_v11.stack(res, m11), d)
            assert got == s[k10], f"{s['calibration']}/{s['id']}/{k10}"
        compared += 1
    assert compared == 8


# 2 -----------------------------------------------------------------------------
@pytest.mark.parametrize("cal_id", ["C1", "C2"])
def test_2_x1_null_under_S0(cal_id):
    for w in V11["x1"]["w"]:
        res = _batch(_params("S0", cal_id, w=w), 100)
        for metric in ("screen_impact_ratio", "overall_impact_ratio"):
            med = np.nanmedian(run_v11.stack(res, metric), axis=0)
            assert np.all((med >= 0.95) & (med <= 1.05)), (cal_id, w, metric, med)


# 3 -----------------------------------------------------------------------------
@pytest.mark.parametrize("cal_id", ["C1", "C2"])
@pytest.mark.parametrize("scen_id", ["S0", "S3"])
def test_3_x3_null(cal_id, scen_id):
    res = _batch(_params(scen_id, cal_id, screener="boosted"), 50)
    med = np.nanmedian(run_v11.stack(res, "screen_impact_ratio"), axis=0)
    assert np.all((med >= 0.95) & (med <= 1.05)), (cal_id, scen_id, med)


# 4 -----------------------------------------------------------------------------
@pytest.mark.parametrize("eps", [0.01, 0.05])
def test_4_x2_accounting(eps):
    m = int(np.floor(CFG["shortlist_rate"] * CFG["N"]))
    k = int(np.floor(CFG["hire_rate"] * CFG["N"]))
    extra = int(np.floor(eps * CFG["N"]))
    for scen_id in ("S1", "S2"):
        for j in range(3):
            out = run_one(CFG["base_seed"] + j, _params(scen_id, "C2", eps=eps))
            assert np.all(out["n_shortlisted"] == m)
            assert np.all(out["n_interviewed"] == m + extra)
            assert np.all(out["n_hired"] == k)


# 5 -----------------------------------------------------------------------------
@pytest.mark.parametrize("A", [1000, 5000])
@pytest.mark.parametrize("p", [0.203, 0.30])
def test_5_p1_calibration(A, p):
    pc = V11["power"]
    rate = null_rejection_rate(A, p, "screen", pc["screen_pass"], 2000, pc["seed"], pc["alpha"])
    assert 0.02 <= rate <= 0.05, rate


# 6 -----------------------------------------------------------------------------
def test_6_sex_never_a_feature():
    pool = draw_pool(np.random.default_rng(1), 500, 0.3, 0.5, 1.0, lam=0.3)
    assert set(pool.features) == {"x1", "x2", "x3"}
    for bad in (["x1", "female"], ["sex"]):
        with pytest.raises(ValueError):
            feature_matrix(pool, bad)
    y = (pool.features["x1"] > 1.5).astype(int)
    b = train_boosted(pool, y, ["x1", "x2", "x3"], seed=1)
    assert b.model.n_features_in_ == 3
    variants = [dict(w=0.5), dict(eps=0.05), dict(screener="boosted"), dict(lam=0.6),
                dict(window="cumulative"), dict(screener="boosted", features=["x1", "x2"]),
                dict(screener="boosted", reweigh=True)]
    for upd in variants:
        params = _params("S2", "C2", T=2, **upd)
        out = run_one(CFG["base_seed"], params)
        for seen in out["seen_features"]:
            assert tuple(seen) == tuple(params["features"]), upd
            assert "female" not in seen and "sex" not in seen, upd


# 7 -----------------------------------------------------------------------------
def _strip(b: bytes) -> bytes:
    return re.sub(rb'"run_date": "[0-9-]+"', b'"run_date": ""', b)


def test_7_reproducible(tmp_path):
    run_v11.main(tmp_path / "a", quick=True)
    run_v11.main(tmp_path / "b", quick=True)
    a = (tmp_path / "a" / "model2_v1_1_results.json").read_bytes()
    b = (tmp_path / "b" / "model2_v1_1_results.json").read_bytes()
    assert _strip(a) == _strip(b)
