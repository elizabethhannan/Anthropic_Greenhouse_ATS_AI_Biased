"""Post-hoc diagnostic for the test 2 failure (X1 null at w = 0.75). No parameter changes.

Re-runs S0 at w = 0.75 with 400 runs (seeds base_seed .. base_seed + 399) for C1 and C2 and
writes outputs/diagnostic_test2.json. Reported in the methods appendix; never used to edit a test.
SIMULATION — synthetic applicants; not Anthropic data.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
from pathlib import Path

import numpy as np

import run_experiments as rx
import run_v11
from calibrate import calibrate_delta0

HERE = Path(__file__).resolve().parent


def main(runs: int = 400, w: float = 0.75):
    cfg = rx.load_config()
    scen = {s["id"]: s for s in cfg["scenarios"]}
    out = {"label": cfg["label"], "purpose": "post-hoc diagnostic for test 2; no parameter changed",
           "scenario": "S0", "w": w, "runs": runs, "by_calibration": {}}
    for cal in cfg["calibrations"]:
        p = cal["pool_share_women"]
        cals = {(p, cfg["h0_target"]): calibrate_delta0(cfg, p, cfg["h0_target"]), (p, p): calibrate_delta0(cfg, p, p)}
        params, _ = rx.scenario_params(cfg, scen["S0"], cal, cals)
        params["w"] = w
        res = run_v11.run_batch(cfg, params, runs)
        o = run_v11.stack(res, "overall_impact_ratio")
        out["by_calibration"][cal["id"]] = {
            "median_overall_ir_first100": np.round(np.nanmedian(o[:100], 0), 4).tolist(),
            "median_overall_ir": np.round(np.nanmedian(o, 0), 4).tolist(),
            "mean_log_overall_ir": np.round(np.nanmean(np.log(o), 0), 4).tolist(),
            "sd_overall_ir": np.round(np.nanstd(o, 0), 4).tolist(),
            "all_medians_within_095_105": bool(np.all((np.nanmedian(o, 0) >= 0.95) & (np.nanmedian(o, 0) <= 1.05))),
        }
    (HERE / "outputs" / "diagnostic_test2.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
