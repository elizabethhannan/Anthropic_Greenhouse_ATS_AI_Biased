"""Run Model 2: calibrations, scenarios S0-S3, interventions I1-I3, sensitivity grid.

SIMULATION — synthetic applicants; not Anthropic data.

Usage:
    python run_experiments.py                 # full run, writes outputs/
    python run_experiments.py --out DIR       # write elsewhere
    python run_experiments.py --quick         # small smoke config (for tests only)
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import copy
import csv
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from joblib import Parallel, delayed

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from calibrate import calibrate_delta0  # noqa: E402
from metrics import FOUR_FIFTHS, rnd, summarize, summarize_at  # noqa: E402
from simulate import run_one  # noqa: E402

SUMMARY_METRICS = ("screen_impact_ratio", "overall_impact_ratio", "hire_share_women",
                   "proxy_weight", "interview_impact_ratio", "screen_validity")

QUICK_OVERRIDES = {"N": 2000, "T": 5, "runs": 6,
                   "calibration": {"n_seeds": 8},
                   "grid": {"pool_share": [0.203, 0.30], "proxy_strength": [0.0, 0.5], "runs": 3}}


def deep_update(base: dict, upd: dict) -> dict:
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict:
    path = Path(path) if path else HERE / "config.yaml"
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if overrides:
        cfg = deep_update(copy.deepcopy(cfg), overrides)
    return cfg


def base_params(cfg: dict) -> dict:
    return {k: cfg[k] for k in ("N", "shortlist_rate", "hire_rate", "T", "sigma_x", "sigma_i",
                                "logreg_C", "features")}


def scenario_params(cfg, scen, cal, cals) -> tuple[dict, dict]:
    """Return (params, calibration-record) for scenario ``scen`` under ``cal``."""
    p = cal["pool_share_women"]
    h0 = p if scen["h0"] == "pool" else cfg["h0_target"]
    c = cals[(p, h0)]
    params = base_params(cfg)
    params.update(p=p, rho=scen["rho"], delta0=c["delta0"],
                  delta_h=(c["delta0"] if scen["delta_h"] == "delta0" else 0.0))
    return params, {"h0": h0, **c}


def run_batch(cfg: dict, params: dict, n_runs: int) -> list[dict]:
    seeds = [cfg["base_seed"] + j for j in range(n_runs)]
    return Parallel(n_jobs=cfg.get("n_jobs", -1), backend="loky")(
        delayed(run_one)(s, params) for s in seeds)


def stack(results: list[dict], metric: str) -> np.ndarray:
    return np.vstack([r[metric] for r in results])


def check_features(results: list[dict], expected: list[str]) -> bool:
    exp = tuple(expected)
    return all(tuple(f) == exp for r in results for f in r["seen_features"])


def main(config_path=None, outdir=None, overrides=None, write_figures_data=True) -> dict:
    t_start = time.time()
    cfg = load_config(config_path, overrides)
    d = cfg["decimals"]
    outdir = Path(outdir) if outdir else HERE / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    scen_by_id = {s["id"]: s for s in cfg["scenarios"]}
    timings = {}

    # ---- 1. Calibrations (delta0) ------------------------------------------------
    t0 = time.time()
    cals = {}
    for cal in cfg["calibrations"]:
        p = cal["pool_share_women"]
        for h0 in (cfg["h0_target"], p):
            cals[(p, h0)] = calibrate_delta0(cfg, p, h0)
    grid = cfg["grid"]
    grid_delta = {}
    for p in grid["pool_share"]:
        cals.setdefault((p, grid["h0"]), calibrate_delta0(cfg, p, grid["h0"]))
        grid_delta[p] = cals[(p, grid["h0"])]
    timings["calibration_s"] = time.time() - t0

    # ---- 2. Scenarios ------------------------------------------------------------
    t0 = time.time()
    scenarios_out, feature_checks, count_checks, cycle0_runs = [], [], [], {}
    raw = {}
    for cal in cfg["calibrations"]:
        for scen in cfg["scenarios"]:
            params, crec = scenario_params(cfg, scen, cal, cals)
            res = run_batch(cfg, params, cfg["runs"])
            raw[(cal["id"], scen["id"])] = res
            feature_checks.append({"run": f"{cal['id']}/{scen['id']}",
                                   "ok": check_features(res, cfg["features"])})
            count_checks.append({"run": f"{cal['id']}/{scen['id']}",
                                 "ok": bool(np.all(stack(res, "n_shortlisted") == int(cfg["shortlist_rate"] * cfg["N"]))
                                            and np.all(stack(res, "n_hired") == int(cfg["hire_rate"] * cfg["N"])))})
            cycle0_runs[(cal["id"], scen["id"])] = float(np.mean([r["cycle0_hire_share_women"] for r in res]))
            entry = {
                "id": scen["id"], "calibration": cal["id"], "name": scen["name"],
                "description": scen["description"],
                "pool_share_women": cal["pool_share_women"],
                "target_hire_share_women": rnd(crec["h0"], d),
                "delta0": rnd(crec["delta0"], d),
                "delta_h": rnd(params["delta_h"], d),
                "proxy_strength": scen["rho"],
                "cycles": list(range(1, cfg["T"] + 1)),
            }
            for mname in SUMMARY_METRICS:
                entry[mname] = summarize(stack(res, mname), d)
            entry["cycle0_hire_share_women_mean_runs"] = rnd(cycle0_runs[(cal["id"], scen["id"])], d)
            scenarios_out.append(entry)
    timings["scenarios_s"] = time.time() - t0

    # ---- 3. Interventions (on S2) ----------------------------------------------------
    t0 = time.time()
    interventions_out = []
    for cal in cfg["calibrations"]:
        for iv in cfg["interventions"]:
            scen = scen_by_id[iv["base_scenario"]]
            params, crec = scenario_params(cfg, scen, cal, cals)
            feats = iv.get("features", cfg["features"])
            params.update(features=feats, reweigh=iv.get("reweigh", False),
                          freeze_after=iv.get("freeze_after"))
            res = run_batch(cfg, params, cfg["runs"])
            raw[(cal["id"], iv["id"])] = res
            feature_checks.append({"run": f"{cal['id']}/{iv['id']}", "ok": check_features(res, feats)})
            count_checks.append({"run": f"{cal['id']}/{iv['id']}",
                                 "ok": bool(np.all(stack(res, "n_shortlisted") == int(cfg["shortlist_rate"] * cfg["N"]))
                                            and np.all(stack(res, "n_hired") == int(cfg["hire_rate"] * cfg["N"])))})
            c5 = min(5, cfg["T"])
            interventions_out.append({
                "id": iv["id"], "name": iv["name"], "description": iv["description"],
                "base_scenario": iv["base_scenario"], "calibration": cal["id"],
                "features": list(feats),
                "screen_ir_cycle5": summarize_at(stack(res, "screen_impact_ratio"), c5, d),
                "hire_share_women_cycle5": summarize_at(stack(res, "hire_share_women"), c5, d),
                "overall_ir_cycle5": summarize_at(stack(res, "overall_impact_ratio"), c5, d),
                "screen_validity_cycle5": summarize_at(stack(res, "screen_validity"), c5, d),
                "proxy_weight_cycle5": summarize_at(stack(res, "proxy_weight"), c5, d),
                "by_cycle": {m: summarize(stack(res, m), d) for m in
                             ("screen_impact_ratio", "hire_share_women", "screen_validity")},
            })
    timings["interventions_s"] = time.time() - t0

    # ---- 4. Sensitivity grid ---------------------------------------------------
    t0 = time.time()
    rec_cycles = grid["cycles_recorded"]
    t_grid = max(rec_cycles)
    grid_out, grid_rows = {}, {}
    for sid in grid["scenarios"]:
        scen = scen_by_id[sid]
        shape = (len(grid["proxy_strength"]), len(grid["pool_share"]))
        mats = {c: np.full(shape, np.nan) for c in rec_cycles}
        mats_lo = {c: np.full(shape, np.nan) for c in rec_cycles}
        mats_hi = {c: np.full(shape, np.nan) for c in rec_cycles}
        rows = []
        for j, p in enumerate(grid["pool_share"]):
            c = grid_delta[p]
            for i, rho in enumerate(grid["proxy_strength"]):
                params = base_params(cfg)
                params.update(T=t_grid, p=p, rho=rho, delta0=c["delta0"],
                              delta_h=(c["delta0"] if scen["delta_h"] == "delta0" else 0.0),
                              compute_validity=False)
                res = run_batch(cfg, params, grid["runs"])
                sir = stack(res, "screen_impact_ratio")
                row = {"scenario": sid, "pool_share": p, "proxy_strength": rho,
                       "delta0": rnd(c["delta0"], d), "achieved_cycle0_share": rnd(c["achieved"], d),
                       "runs": grid["runs"]}
                for cyc in rec_cycles:
                    s = summarize_at(sir, cyc, d)
                    mats[cyc][i, j] = s["median"]
                    mats_lo[cyc][i, j] = s["p05"]
                    mats_hi[cyc][i, j] = s["p95"]
                    row.update({f"screen_ir_c{cyc}_median": s["median"],
                                f"screen_ir_c{cyc}_p05": s["p05"], f"screen_ir_c{cyc}_p95": s["p95"]})
                rows.append(row)
        grid_rows[sid] = rows
        grid_out[sid] = {
            "scenario": sid, "pool_share": grid["pool_share"], "proxy_strength": grid["proxy_strength"],
            "rows": "proxy_strength", "columns": "pool_share",
            **{f"screen_ir_cycle{c}": [rnd(r, d) for r in mats[c].tolist()] for c in rec_cycles},
            **{f"screen_ir_cycle{c}_p05": [rnd(r, d) for r in mats_lo[c].tolist()] for c in rec_cycles},
            **{f"screen_ir_cycle{c}_p95": [rnd(r, d) for r in mats_hi[c].tolist()] for c in rec_cycles},
            "delta0_by_pool_share": [rnd(grid_delta[p]["delta0"], d) for p in grid["pool_share"]],
            "target_hire_share_women": grid["h0"],
        }
        with open(outdir / f"sensitivity_{sid}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    timings["grid_s"] = time.time() - t0

    # ---- 5. Assemble results ---------------------------------------------------
    calib_out = []
    for cal in cfg["calibrations"]:
        p = cal["pool_share_women"]
        c = cals[(p, cfg["h0_target"])]
        cn = cals[(p, p)]
        calib_out.append({
            "id": cal["id"], "name": cal["name"], "pool_share_women": p,
            "target_hire_share_women": cfg["h0_target"],
            "delta0": rnd(c["delta0"], d), "achieved_hire_share_women": rnd(c["achieved"], d),
            "illustrative": cal["illustrative"], "basis": cal["basis"],
            "brent_evaluations": c["n_evals"],
            "null_check_S0": {"target_hire_share_women": p, "delta0": rnd(cn["delta0"], d),
                              "achieved_hire_share_women": rnd(cn["achieved"], d)},
        })

    results = {
        "label": cfg["label"],
        "run_date": dt.date.today().isoformat(),
        "config": {k: cfg[k] for k in ("base_seed", "N", "shortlist_rate", "hire_rate", "T", "sigma_x",
                                       "sigma_i", "rho", "h0_target", "runs", "logreg_C", "features")},
        "calibrations": calib_out,
        "scenarios": scenarios_out,
        "sensitivity": grid_out.get("S2"),
        "sensitivity_S1": grid_out.get("S1"),
        "grid_runs_per_cell": grid["runs"],
        "interventions": interventions_out,
        "checks": {"sex_never_a_feature": feature_checks, "counts_conserved": count_checks},
    }

    # ---- 6. Findings, limitations, thesis alignment (generated from the numbers) ----
    from findings import build_text  # local import keeps simulation code independent
    results.update(build_text(results, cfg))

    with open(outdir / "model2_results.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # Long-format per-cycle table for dashboards / CSV buttons
    with open(outdir / "scenario_summaries.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["label", "calibration", "scenario", "metric", "cycle", "median", "p05", "p95"])
        for s in scenarios_out:
            for m in SUMMARY_METRICS:
                for i, cyc in enumerate(s["cycles"]):
                    w.writerow([cfg["label"], s["calibration"], s["id"], m, cyc,
                                s[m]["median"][i], s[m]["p05"][i], s[m]["p95"][i]])
        for iv in interventions_out:
            for m, summ in iv["by_cycle"].items():
                for i in range(cfg["T"]):
                    w.writerow([cfg["label"], iv["calibration"], iv["id"], m, i + 1,
                                summ["median"][i], summ["p05"][i], summ["p95"][i]])

    timings["total_s"] = time.time() - t_start
    log = {"run_date": results["run_date"], "timings_seconds": {k: round(v, 1) for k, v in timings.items()},
           "n_jobs": cfg.get("n_jobs"), "cpu_count": os.cpu_count(),
           "python": sys.version.split()[0], "numpy": np.__version__}
    with open(outdir / "run_log.json", "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2)
        fh.write("\n")
    return results


def rebuild_text(outdir=None, config_path=None) -> dict:
    """Regenerate the text keys of an existing results file without re-simulating."""
    from findings import build_text
    cfg = load_config(config_path)
    outdir = Path(outdir) if outdir else HERE / "outputs"
    path = outdir / "model2_results.json"
    results = json.loads(path.read_text(encoding="utf-8"))
    results.update(build_text(results, cfg))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true", help="small smoke configuration (tests only)")
    ap.add_argument("--text-only", action="store_true", help="regenerate findings text from existing results")
    a = ap.parse_args()
    if a.text_only:
        rebuild_text(a.out, a.config)
        raise SystemExit(0)
    res = main(a.config, a.out, QUICK_OVERRIDES if a.quick else None)
    print(json.dumps({"calibrations": res["calibrations"]}, indent=2))
