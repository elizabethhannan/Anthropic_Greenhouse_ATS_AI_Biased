"""Run Model 2 v1.1: regression check, X1–X5, P1 power table.

SIMULATION — synthetic applicants; not Anthropic data.

Usage (from this folder):
    python run_v11.py                # timing pilot, then the full run -> outputs/
    python run_v11.py --out DIR      # write elsewhere
    python run_v11.py --quick        # small smoke configuration (tests only; no pilot)
    python run_v11.py --text-only    # rebuild findings text from an existing results file
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

import run_experiments as rx  # noqa: E402  (v1.0 helpers, unchanged copy)
from calibrate import calibrate_delta0  # noqa: E402
from metrics import rnd, summarize  # noqa: E402
from power import power_table, simulate_cell  # noqa: E402
from simulate_v11 import run_one  # noqa: E402

OUT_METRICS = {  # output key -> simulate_v11 metric
    "screen_ir": "screen_impact_ratio",
    "interview_ir": "interview_impact_ratio",
    "overall_ir": "overall_impact_ratio",
    "hire_share_women": "hire_share_women",
    "proxy_signal": "proxy_signal",
    "screen_validity": "screen_validity",
}
V10_SCEN_METRICS = {  # v1.0 scenario key -> simulate_v11 metric
    "screen_impact_ratio": "screen_impact_ratio",
    "overall_impact_ratio": "overall_impact_ratio",
    "hire_share_women": "hire_share_women",
    "proxy_weight": "proxy_signal",
    "interview_impact_ratio": "interview_impact_ratio",
    "screen_validity": "screen_validity",
}

QUICK_OVERRIDES = {
    "base": {"N": 2000, "T": 3, "calibration": {"n_seeds": 8}},
    "v11": {"runs_default": 4, "runs_x3": 3, "runs_reduced": 3, "pilot_runs": 0,
            "power": {"applicants": [250, 1000], "replicates": 200}},
}

EXT_NAMES = {
    "X1": ("Interviewer reliance on the screen score", ["RQ2", "RQ3", "RQ4"], "w"),
    "X2": ("Exploration: interview a random share of screened-out applicants (I4)", ["RQ5"], "eps"),
    "X3": ("Gradient-boosted screener", ["RQ2"], "screener"),
    "X4": ("Partly job-relevant proxy; cost of each fix", ["RQ5"], "lam"),
    "X5": ("Cumulative training window", ["RQ4"], "window"),
}


def load_v11(path=None, overrides=None) -> dict:
    path = Path(path) if path else HERE / "config_v1_1.yaml"
    with open(path, encoding="utf-8") as fh:
        v = yaml.safe_load(fh)
    if overrides:
        v = rx.deep_update(copy.deepcopy(v), overrides)
    return v


def run_batch(cfg: dict, params: dict, n_runs: int) -> list[dict]:
    seeds = [cfg["base_seed"] + j for j in range(n_runs)]
    return Parallel(n_jobs=cfg.get("n_jobs", -1), backend="loky")(
        delayed(run_one)(s, params) for s in seeds)


def stack(results, metric, n=None):
    res = results if n is None else results[:n]
    return np.vstack([r[metric] for r in res])


# ---------------------------------------------------------------- configurations
def build_configs(cfg: dict, v: dict, cals: dict) -> list[dict]:
    scen = {s["id"]: s for s in cfg["scenarios"]}
    ivs = {i["id"]: i for i in cfg["interventions"]}
    cal_by = {c["id"]: c for c in cfg["calibrations"]}
    confs = []

    def params_for(arm, cal_id, **extra):
        cal = cal_by[cal_id]
        if arm in scen:
            params, _ = rx.scenario_params(cfg, scen[arm], cal, cals)
            base = arm
        else:
            iv = ivs[arm]
            params, _ = rx.scenario_params(cfg, scen[iv["base_scenario"]], cal, cals)
            params.update(features=iv.get("features", cfg["features"]), reweigh=iv.get("reweigh", False),
                          freeze_after=iv.get("freeze_after"))
            base = iv["base_scenario"]
        params.update(extra)
        return params, base

    # Regression check: v1.0 scenarios and interventions with v1.1 defaults
    for c in cfg["calibrations"]:
        for arm in list(scen) + list(ivs):
            params, base = params_for(arm, c["id"])
            confs.append({"ext": "REG", "calibration": c["id"], "scenario": base, "arm": arm,
                          "value": None, "params": params, "runs_kind": "regression"})
    for cal_id in v["x1"]["calibrations"]:
        for sid in v["x1"]["scenarios"]:
            for w in v["x1"]["w"]:
                params, base = params_for(sid, cal_id, w=w)
                confs.append({"ext": "X1", "calibration": cal_id, "scenario": base, "arm": sid,
                              "value": w, "params": params, "runs_kind": "default"})
    for cal_id in v["x2"]["calibrations"]:
        for sid in v["x2"]["scenarios"]:
            for eps in v["x2"]["eps"]:
                params, base = params_for(sid, cal_id, eps=eps)
                confs.append({"ext": "X2", "calibration": cal_id, "scenario": base, "arm": sid,
                              "value": eps, "params": params, "runs_kind": "default"})
    x3 = v["x3"]
    for cal_id in x3["calibrations"]:
        for arm in x3["scenarios"] + x3["interventions"]:
            params, base = params_for(arm, cal_id, screener="boosted",
                                      perm_subsample=x3["perm_subsample"], perm_repeats=x3["perm_repeats"])
            confs.append({"ext": "X3", "calibration": cal_id, "scenario": base, "arm": arm,
                          "value": "boosted", "params": params, "runs_kind": "x3"})
    for cal_id in v["x4"]["calibrations"]:
        for arm in v["x4"]["arms"]:
            for lam in v["x4"]["lam"]:
                params, base = params_for(arm, cal_id, lam=lam)
                confs.append({"ext": "X4", "calibration": cal_id, "scenario": base, "arm": arm,
                              "value": lam, "params": params, "runs_kind": "default"})
    for cal_id in v["x5"]["calibrations"]:
        for sid in v["x5"]["scenarios"]:
            params, base = params_for(sid, cal_id, window="cumulative")
            confs.append({"ext": "X5", "calibration": cal_id, "scenario": base, "arm": sid,
                          "value": "cumulative", "params": params, "runs_kind": "default"})
    return confs


def runs_for(kind: str, v: dict, reduced: bool) -> int:
    if kind == "regression":
        return v["runs_default"]          # must match v1.0's run count
    if kind == "x3":
        return v["runs_x3"]
    return v["runs_reduced"] if reduced else v["runs_default"]


# ---------------------------------------------------------------- pilot
def timing_pilot(cfg, v, confs) -> dict:
    """5 runs per configuration (results discarded) -> projected wall time."""
    n = v["pilot_runs"]
    per_ext, projected_full, projected_reduced = {}, 0.0, 0.0
    for c in confs:
        t0 = time.time()
        run_batch(cfg, c["params"], n)
        dt_ = time.time() - t0
        full = dt_ / n * runs_for(c["runs_kind"], v, False)
        red = dt_ / n * runs_for(c["runs_kind"], v, True)
        per_ext[c["ext"]] = per_ext.get(c["ext"], 0.0) + full
        projected_full += full
        projected_reduced += red
    # Power: time one cell per applicant count (screen stage, 100 replicates), scale up
    pc = v["power"]
    t_pow = 0.0
    for A in pc["applicants"]:
        t0 = time.time()
        simulate_cell(A, pc["pool_share"][0], pc["true_ir"][0], "screen", pc["screen_pass"], 100,
                      [0, 0, 0, 0, int(A)], pc["alpha"])
        t_pow += time.time() - t0
    t_pow *= (pc["replicates"] / 100) * len(pc["pool_share"]) * len(pc["true_ir"]) * 2
    per_ext["P1"] = t_pow
    return {"pilot_runs_per_config": n,
            "projected_minutes_full": round((projected_full + t_pow) / 60, 1),
            "projected_minutes_reduced": round((projected_reduced + t_pow) / 60, 1),
            "projected_minutes_by_part_full": {k: round(s / 60, 2) for k, s in per_ext.items()}}


# ---------------------------------------------------------------- summaries
def summarize_entry(c: dict, res: list[dict], d: int, cfg: dict, n=None) -> dict:
    e = {"calibration": c["calibration"], "scenario": c["scenario"], "arm": c["arm"],
         "value": c["value"], "runs": len(res) if n is None else n}
    for key, mname in OUT_METRICS.items():
        e[key] = summarize(stack(res, mname, n), d)
    eps = float(c["params"].get("eps", 0.0))
    e["extra_interviews_per_cycle"] = int(np.floor(eps * cfg["N"]))
    return e


def regression_check(cfg, reg_raw, v1_path, d, v1_label=None) -> dict:
    v1 = json.loads(Path(v1_path).read_text(encoding="utf-8"))
    mismatches, compared = [], 0
    for s in v1["scenarios"]:
        res = reg_raw.get((s["calibration"], s["id"]))
        if res is None:
            continue
        compared += 1
        for k10, m11 in V10_SCEN_METRICS.items():
            if summarize(stack(res, m11), d) != s[k10]:
                mismatches.append(f"{s['calibration']}/{s['id']}/{k10}")
    for iv in v1["interventions"]:
        res = reg_raw.get((iv["calibration"], iv["id"]))
        if res is None:
            continue
        compared += 1
        for k10, m11 in (("screen_impact_ratio", "screen_impact_ratio"),
                         ("hire_share_women", "hire_share_women"),
                         ("screen_validity", "screen_validity")):
            if summarize(stack(res, m11), d) != iv["by_cycle"][k10]:
                mismatches.append(f"{iv['calibration']}/{iv['id']}/{k10}")
        c5 = min(5, cfg["T"])
        for k10, m11 in (("screen_ir_cycle5", "screen_impact_ratio"),
                         ("hire_share_women_cycle5", "hire_share_women"),
                         ("overall_ir_cycle5", "overall_impact_ratio"),
                         ("screen_validity_cycle5", "screen_validity"),
                         ("proxy_weight_cycle5", "proxy_signal")):
            if rx.summarize_at(stack(res, m11), c5, d) != iv[k10]:
                mismatches.append(f"{iv['calibration']}/{iv['id']}/{k10}")
    return {"matches_v1_0": (compared > 0 and not mismatches), "configs_compared": compared,
            "mismatches": mismatches, "compared_against": v1_label or Path(v1_path).name}


def write_power_csv(rows, path, label):
    As = list(rows[0]["power_by_A"].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["label", "stage", "pool_share_women", "true_ir", "stage_pass_rate", "min_applicants_80pct"]
                   + [f"power_A{a}" for a in As] + [f"p_obs_below_080_A{a}" for a in As])
        for r in rows:
            w.writerow([label, r["stage"], r["pool_share_women"], r["true_ir"], r["stage_pass_rate"],
                        r["min_applicants_80pct"]] + [r["power_by_A"][a] for a in As]
                       + [r["p_observed_below_080_by_A"][a] for a in As])


# ---------------------------------------------------------------- main
def main(outdir=None, quick=False, v11_path=None) -> dict:
    t_start = time.time()
    base_over = QUICK_OVERRIDES["base"] if quick else None
    v_over = QUICK_OVERRIDES["v11"] if quick else None
    cfg = rx.load_config(None, base_over)
    v = load_v11(v11_path, v_over)
    d = cfg["decimals"]
    outdir = Path(outdir) if outdir else HERE / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)

    cals = {}
    for cal in cfg["calibrations"]:
        p = cal["pool_share_women"]
        for h0 in (cfg["h0_target"], p):
            cals[(p, h0)] = calibrate_delta0(cfg, p, h0)
    confs = build_configs(cfg, v, cals)

    pilot = None
    reduced = False
    if v["pilot_runs"] > 0:
        pilot = timing_pilot(cfg, v, confs)
        reduced = pilot["projected_minutes_full"] > v["runtime_target_minutes"]
    runs_used = {k: runs_for(k, v, reduced) for k in ("regression", "default", "x3")}

    timings, raw = {}, {}
    feature_checks, count_checks = [], []
    m = int(np.floor(cfg["shortlist_rate"] * cfg["N"]))
    k = int(np.floor(cfg["hire_rate"] * cfg["N"]))
    for c in confs:
        t0 = time.time()
        n_runs = runs_for(c["runs_kind"], v, reduced)
        res = run_batch(cfg, c["params"], n_runs)
        timings[c["ext"]] = timings.get(c["ext"], 0.0) + time.time() - t0
        raw[(c["ext"], c["calibration"], c["arm"], str(c["value"]))] = res
        tag = f"{c['ext']}/{c['calibration']}/{c['arm']}/{c['value']}"
        feats = tuple(c["params"]["features"])
        feature_checks.append({"run": tag, "ok": all(tuple(f) == feats and "female" not in f and "sex" not in f
                                                     for r in res for f in r["seen_features"])})
        n_exp = int(np.floor(float(c["params"].get("eps", 0.0)) * cfg["N"]))
        count_checks.append({"run": tag, "ok": bool(
            np.all(stack(res, "n_shortlisted") == m) and np.all(stack(res, "n_interviewed") == m + n_exp)
            and np.all(stack(res, "n_hired") == k))})

    reg_raw = {(c["calibration"], c["arm"]): raw[("REG", c["calibration"], c["arm"], "None")]
               for c in confs if c["ext"] == "REG"}
    v1_path = (HERE / v["v1_0_results"]).resolve()
    if quick:
        reg = {"matches_v1_0": None, "configs_compared": 0, "mismatches": [],
               "note": "quick configuration differs from v1.0; regression check runs only in the full configuration"}
    else:
        reg = regression_check(cfg, reg_raw, v1_path, d, v["v1_0_results"])  # repository-relative label

    # ---- extension entries
    extensions = []
    for ext, (name, rq, param) in EXT_NAMES.items():
        ec = [c for c in confs if c["ext"] == ext]
        values = list(dict.fromkeys(c["value"] for c in ec))
        entry = {"id": ext, "name": name, "rq": rq, "param": param, "values": values, "results": []}
        for c in ec:
            res = raw[(ext, c["calibration"], c["arm"], str(c["value"]))]
            e = summarize_entry(c, res, d, cfg)
            # Same-seed comparison with the v1.0 (logistic, last-window, no reliance) arm
            ref = reg_raw.get((c["calibration"], c["arm"]))
            if ref is not None and ext in ("X2", "X3", "X5"):
                e["reference_v1_0_same_seeds"] = {key: summarize(stack(ref, mn, len(res)), d)
                                                 for key, mn in OUT_METRICS.items()}
                e["reference_v1_0_same_seeds"]["runs"] = len(res)
            entry["results"].append(e)
        extensions.append(entry)

    # ---- P1 power
    t0 = time.time()
    rows = power_table(v["power"], cfg["shortlist_rate"])
    timings["P1"] = time.time() - t0
    pc = v["power"]
    power = {"alpha": pc["alpha"], "target_power": pc["target_power"], "replicates": pc["replicates"],
             "applicants": pc["applicants"], "screen_pass_rate": pc["screen_pass"],
             "interview_pass_rate": pc["interview_pass"],
             "interview_at_risk_rule": "floor(0.10 * A) shortlisted; women ~ Binomial(floor(0.10*A), p)",
             "rows": rows}

    results = {
        "label": v["label"], "version": v["version"], "base_version": v["base_version"],
        "run_date": dt.date.today().isoformat(),
        "config": {**{kk: cfg[kk] for kk in ("base_seed", "N", "shortlist_rate", "hire_rate", "T", "sigma_x",
                                             "sigma_i", "rho", "h0_target", "logreg_C", "features")},
                   "runs": runs_used, "runs_reduced_by_pilot_rule": reduced,
                   "pilot_projected_minutes_full": pilot["projected_minutes_full"] if pilot else None,
                   "calibrations": {c["id"]: {"pool_share_women": c["pool_share_women"],
                                              "delta0": rnd(cals[(c["pool_share_women"], cfg["h0_target"])]["delta0"], d),
                                              "illustrative": c["illustrative"]} for c in cfg["calibrations"]},
                   "x3_permutation_importance": {"subsample": v["x3"]["perm_subsample"],
                                                 "repeats": v["x3"]["perm_repeats"], "metric": "ROC AUC drop"}},
        "regression_check": reg,
        "extensions": extensions,
        "power": power,
        "checks": {"sex_never_a_feature": all(x["ok"] for x in feature_checks),
                   "counts_conserved": all(x["ok"] for x in count_checks),
                   "sex_checks": feature_checks, "count_checks": count_checks},
    }
    try:
        from findings_v11 import build_text
        results.update(build_text(results))
    except ImportError:
        results.update({"thesis_alignment": [], "findings": [], "limitations": [],
                        "executive_conclusion_model2_v1_1": ""})

    with open(outdir / "model2_v1_1_results.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    write_power_csv(rows, outdir / "power_table.csv", v["label"])

    timings["total"] = time.time() - t_start
    log = {"run_date": results["run_date"], "pilot": pilot, "runs_used": runs_used,
           "timings_minutes": {kk: round(s / 60, 2) for kk, s in timings.items()},
           "cpu_count": os.cpu_count(), "python": sys.version.split()[0], "numpy": np.__version__}
    import sklearn
    log["sklearn"] = sklearn.__version__
    with open(outdir / "run_log_v1_1.json", "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2)
        fh.write("\n")
    return results


def rebuild_text(outdir=None) -> dict:
    from findings_v11 import build_text
    outdir = Path(outdir) if outdir else HERE / "outputs"
    path = outdir / "model2_v1_1_results.json"
    results = json.loads(path.read_text(encoding="utf-8"))
    log_path = outdir / "run_log_v1_1.json"
    if "pilot_projected_minutes_full" not in results["config"] and log_path.exists():
        pilot = json.loads(log_path.read_text(encoding="utf-8")).get("pilot")
        results["config"]["pilot_projected_minutes_full"] = pilot["projected_minutes_full"] if pilot else None
    results.update(build_text(results))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--text-only", action="store_true")
    a = ap.parse_args()
    if a.text_only:
        rebuild_text(a.out)
        raise SystemExit(0)
    r = main(a.out, a.quick)
    print(json.dumps({"regression_check": r["regression_check"], "runs": r["config"]["runs"]}, indent=2))
