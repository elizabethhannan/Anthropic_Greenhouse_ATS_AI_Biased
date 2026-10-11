"""Model 2 tests (pytest). If a test fails, report it; do not edit it to pass.

Run from version_d/model2_feedback_loop/:  pytest -q
Set MODEL2_FULL_REPRO=1 to make test 7 re-run the FULL configuration and compare
with outputs/model2_results.json (takes as long as a full run).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import run_experiments as rx  # noqa: E402
from calibrate import calibrate_delta0  # noqa: E402
from metrics import impact_ratio  # noqa: E402
from simulate import draw_pool, feature_matrix, run_one  # noqa: E402

CFG = rx.load_config()
SCEN = {s["id"]: s for s in CFG["scenarios"]}
CALS = {c["id"]: c for c in CFG["calibrations"]}


def _cals_for(cal):
    p = cal["pool_share_women"]
    return {(p, CFG["h0_target"]): calibrate_delta0(CFG, p, CFG["h0_target"]),
            (p, p): calibrate_delta0(CFG, p, p)}


def _params(scen_id, cal_id, **upd):
    cal = CALS[cal_id]
    params, _ = rx.scenario_params(CFG, SCEN[scen_id], cal, _cals_for(cal))
    params.update(upd)
    return params


# 1 -----------------------------------------------------------------------------
def test_1_impact_ratio_arithmetic():
    # 10 women, 2 selected; 20 men, 8 selected -> 0.20 / 0.40 = 0.50
    assert impact_ratio(2, 10, 8, 20) == pytest.approx(0.50, abs=1e-12)


# 2 -----------------------------------------------------------------------------
@pytest.mark.parametrize("cal_id", ["C1", "C2"])
def test_2_calibration_hits_target(cal_id):
    p = CALS[cal_id]["pool_share_women"]
    c = calibrate_delta0(CFG, p, CFG["h0_target"])
    assert abs(c["achieved"] - CFG["h0_target"]) <= 0.005, c


# 3 -----------------------------------------------------------------------------
def _median_screen_ir(scen_id, cal_id, runs=100):
    params = _params(scen_id, cal_id)
    res = rx.run_batch(CFG, params, runs)
    return np.nanmedian(rx.stack(res, "screen_impact_ratio"), axis=0)


@pytest.mark.parametrize("cal_id", ["C1", "C2"])
def test_3_null_scenario_S0(cal_id):
    med = _median_screen_ir("S0", cal_id)
    assert np.all((med >= 0.95) & (med <= 1.05)), med


# 4 -----------------------------------------------------------------------------
@pytest.mark.parametrize("cal_id", ["C1", "C2"])
def test_4_no_proxy_S3(cal_id):
    med = _median_screen_ir("S3", cal_id)
    assert np.all((med >= 0.95) & (med <= 1.05)), med


# 5 -----------------------------------------------------------------------------
def _all_runs():
    for cal_id in CALS:
        for sid in SCEN:
            yield f"{cal_id}/{sid}", _params(sid, cal_id, T=3), CFG["features"]
        for iv in CFG["interventions"]:
            feats = iv.get("features", CFG["features"])
            yield (f"{cal_id}/{iv['id']}",
                   _params(iv["base_scenario"], cal_id, T=3, features=feats,
                           reweigh=iv.get("reweigh", False), freeze_after=iv.get("freeze_after")),
                   feats)


def test_5_sex_never_a_feature():
    pool = draw_pool(np.random.default_rng(1), 100, 0.3, 0.5, 1.0)
    assert set(pool.features) == {"x1", "x2", "x3"}
    for bad in (["x1", "female"], ["sex"]):
        with pytest.raises(ValueError):
            feature_matrix(pool, bad)
    for name, params, feats in _all_runs():
        out = run_one(CFG["base_seed"], params)
        for seen in out["seen_features"]:
            assert tuple(seen) == tuple(feats), name
            assert "female" not in seen and "sex" not in seen, name
        assert feature_matrix(pool, feats).shape[1] == len(feats)


# 6 -----------------------------------------------------------------------------
def test_6_counts_conserved():
    m = int(np.floor(CFG["shortlist_rate"] * CFG["N"]))
    k = int(np.floor(CFG["hire_rate"] * CFG["N"]))
    for name, params, _ in _all_runs():
        for j in range(2):
            out = run_one(CFG["base_seed"] + j, params)
            assert np.all(out["n_shortlisted"] == m), name
            assert np.all(out["n_hired"] == k), name


# 7 -----------------------------------------------------------------------------
def _strip_run_date(b: bytes) -> bytes:
    return re.sub(rb'"run_date": "[0-9-]+"', b'"run_date": ""', b)


def test_7_reproducible(tmp_path):
    full = os.environ.get("MODEL2_FULL_REPRO") == "1"
    overrides = None if full else rx.QUICK_OVERRIDES
    a, b = tmp_path / "a", tmp_path / "b"
    rx.main(None, a, overrides)
    if full:
        b_bytes = (HERE / "outputs" / "model2_results.json").read_bytes()
    else:
        rx.main(None, b, overrides)
        b_bytes = (b / "model2_results.json").read_bytes()
    a_bytes = (a / "model2_results.json").read_bytes()
    assert _strip_run_date(a_bytes) == _strip_run_date(b_bytes)
