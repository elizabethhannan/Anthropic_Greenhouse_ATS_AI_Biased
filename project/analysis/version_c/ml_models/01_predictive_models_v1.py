"""Version C — Version 3.0, ML Workstream v1.0.

The unit is one exact role-family x established posting month. Outcomes are
aggregate Male/Female known-sex counts; Unknown is reported separately and
excluded from the binary/binomial outcome. No candidate-to-posting linkage is
created. If the role/month sample cannot support grouped validation, outputs
record NOT_ESTIMABLE and no model is fit.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parents[1]  # analysis/version_c
WORK = BASE / "ml_models"
SOURCE_OUT = BASE / "outputs"
OUT = WORK / "outputs"
AUDIT = WORK / "audit"
MODELS = WORK / "models"
MASTER = SOURCE_OUT / "version_c_master.parquet"
HIRING = SOURCE_OUT / "version_c_hiring_outcomes.parquet"
BRIDGE = SOURCE_OUT / "version_c_role_month_bridge.parquet"
SIGNALS = SOURCE_OUT / "signal_features.parquet"
SEED = 42
N_FOLDS = 5
MIN_ROLE_MONTHS = 20
MIN_CLASS_CELLS = 5

OUTPUT_COLUMNS = {
    "predictive_model_metrics.csv": ["model", "status", "n_role_month_cells", "n_male_cells", "n_female_cells", "known_sex_hires", "unknown_hires", "roc_auc", "pr_auc", "brier_score", "log_loss", "composition_mae", "calibration_intercept", "calibration_slope", "reason"],
    "predictive_oof_predictions.csv": ["model", "role_family", "posting_month", "group_id", "male_count", "female_count", "unknown_count", "known_sex_count", "observed_male_share", "predicted_male_share", "fold"],
    "predictive_coefficients.csv": ["model", "feature", "coefficient", "odds_ratio", "ci_low", "ci_high", "scale"],
    "predictive_permutation_importance.csv": ["model", "feature", "mean_brier_increase", "std_brier_increase", "folds_evaluated"],
    "predictive_feature_stability.csv": ["model", "feature", "fold_coefficients", "positive_fold_fraction", "negative_fold_fraction", "direction_stable"],
    "predictive_sensitivity.csv": ["comparison", "baseline_model", "comparison_model", "baseline_roc_auc", "comparison_roc_auc", "delta_roc_auc", "baseline_composition_mae", "comparison_composition_mae", "delta_composition_mae", "status"],
    "predictive_model_agreement.csv": ["role_month_key", "logistic_probability", "gradient_boosting_probability", "absolute_difference", "class_agreement"],
    "predictive_findings.csv": ["finding", "status", "value", "interpretation"],
}
FAMILY_FIELDS = {
    "signal_research": ["researcher_reference_count", "research_exemplar_count", "signal_research_count", "signal_research_pedigree_count", "publication_paper_reference_count", "signal_publication_emphasis_count"],
    "signal_technical": ["signal_ai_ml_count", "signal_technical_specialization_count"],
    "signal_leadership": ["signal_leadership_count", "signal_seniority_count"],
    "signal_collaboration": ["signal_collaboration_count"],
    "signal_accomplishment": ["signal_accomplishment_framing_count"],
    "signal_candidate_expectations": ["signal_candidate_expectations_count"],
    "signal_gender_language": ["language_gendered_reference_flag", "language_masculine_pronoun_count", "language_feminine_pronoun_count", "language_explicit_male_reference_count", "language_explicit_female_reference_count"],
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_rows(path: Path) -> tuple[list[dict[str, Any]], bytes]:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    raw = path.read_bytes()
    return pq.read_table(path).to_pylist(), raw


def month_of(value: Any) -> str | None:
    if value is None:
        return None
    match = re.match(r"^(\d{4})-(\d{2})", str(value).strip())
    if not match:
        return None
    month = int(match.group(2))
    return f"{match.group(1)}-{month:02d}" if 1 <= month <= 12 else None


def posting_date(row: dict[str, Any]) -> Any:
    return row.get("first_published_at") or row.get("posting_date_if_known")


def num(value: Any) -> float:
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return 0.0


def reconstruct_outcomes(people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Aggregate frozen source employment rows by distinct person x month x role.
    unique: dict[tuple[str, str, str], str] = {}
    for person in people:
        pid = str(person.get("PERSON_ID") or "")
        sex = str(person.get("outcome_sex") or "UNKNOWN").upper()
        raw = person.get("employment_records")
        records = json.loads(raw) if isinstance(raw, str) else (raw or [])
        for rec in records:
            month = month_of(rec.get("START_DATE"))
            if not month or not "2026-04" <= month <= "2026-09":
                continue
            role = str(rec.get("ROLE_CATEGORY") or rec.get("TITLE_ROLE") or rec.get("TITLE_NAME") or "Unknown role").strip()
            unique[(pid, month, role)] = sex
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for (pid, month, role), sex in unique.items():
        cell = cells.setdefault((month, role), {"month": month, "role_family": role, "male_count": 0, "female_count": 0, "unknown_count": 0})
        key = sex.lower()
        cell[f"{key}_count" if key in {"male", "female"} else "unknown_count"] += 1
    return list(cells.values())


def build_role_month_dataset(master: list[dict[str, Any]], people: list[dict[str, Any]], signals: list[dict[str, Any]], frozen_bridge: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    signal_by_id = {str(r.get("version_c_posting_id")): r for r in signals}
    postings_by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for post in master:
        if post.get("date_evidence_class") != "GREENHOUSE_POSTING_DATE":
            continue
        month = month_of(posting_date(post))
        if not month or not "2026-04" <= month <= "2026-09":
            continue
        role = str(post.get("posting_role_family") or "Review Needed")
        feature = signal_by_id.get(str(post.get("version_c_posting_id")))
        if feature is None:
            continue
        postings_by_cell[(month, role)].append(feature)

    bridge_with_counts = sum(num(r.get("observed_hire_male")) + num(r.get("observed_hire_female")) + num(r.get("observed_hire_unknown")) > 0 for r in frozen_bridge)
    if bridge_with_counts:
        outcome_rows = [{
            "month": str(r.get("month")), "role_family": str(r.get("role_family")),
            "male_count": int(num(r.get("observed_hire_male"))), "female_count": int(num(r.get("observed_hire_female"))),
            "unknown_count": int(num(r.get("observed_hire_unknown"))),
        } for r in frozen_bridge]
        bridge_source = "frozen_phase2_bridge"
    else:
        outcome_rows = reconstruct_outcomes(people)
        bridge_source = "in_memory_aggregate_from_frozen_hiring_rows"
    outcomes = {(r["month"], r["role_family"]): r for r in outcome_rows}

    cells = []
    for (month, role), post_rows in sorted(postings_by_cell.items()):
        outcome = outcomes.get((month, role))
        if not outcome:
            continue
        male, female, unknown = (int(outcome[k]) for k in ("male_count", "female_count", "unknown_count"))
        known = male + female
        if known <= 0:
            continue
        row = {"posting_month": month, "role_family": role, "group_id": f"{role}|{month}",
               "male_count": male, "female_count": female, "unknown_count": unknown,
               "known_sex_count": known, "observed_male_share": male / known,
               "posting_count": len(post_rows), "bridge_source": bridge_source}
        # Signal family values are per-posting means within the role/month cell.
        # Raw descriptions remain in the Phase 3 master; they are never targets.
        for family, fields in FAMILY_FIELDS.items():
            vals = []
            for post in post_rows:
                word_count = max(1.0, num(post.get("description_word_count")))
                value = sum(num(post.get(f)) for f in fields if f in post)
                vals.append(value / word_count * 1000.0)
            row[family] = float(np.mean(vals)) if vals else 0.0
        cells.append(row)
    diagnostics = {"dated_postings": sum(len(v) for v in postings_by_cell.values()),
                   "posting_role_month_cells": len(postings_by_cell),
                   "outcome_role_month_cells": len(outcome_rows),
                   "matched_known_sex_cells": len(cells),
                   "frozen_bridge_cells_with_hires": int(bridge_with_counts)}
    return cells, diagnostics, bridge_source


def csv_write(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> int:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    with path.open("r", newline="", encoding="utf-8") as stream:
        return max(0, sum(1 for _ in csv.reader(stream)) - 1)


def not_estimable_outputs(cells: list[dict[str, Any]], reason: str) -> dict[str, list[dict[str, Any]]]:
    n = len(cells)
    male_cells = sum(r["male_count"] > 0 for r in cells)
    female_cells = sum(r["female_count"] > 0 for r in cells)
    unknown = sum(r["unknown_count"] for r in cells)
    model_names = ["Logistic baseline", "Logistic signal", "Logistic signal without gender-language",
                   "Gradient Boosting baseline", "Gradient Boosting signal", "Gradient Boosting signal without gender-language"]
    metrics = [{"model": name, "status": "NOT_ESTIMABLE", "n_role_month_cells": n,
                "n_male_cells": male_cells, "n_female_cells": female_cells,
                "known_sex_hires": sum(r["known_sex_count"] for r in cells), "unknown_hires": unknown,
                "reason": reason} for name in model_names]
    findings = [
        {"finding": "model_status", "status": "NOT_ESTIMABLE", "value": reason, "interpretation": "No cross-validated model result is reported."},
        {"finding": "unit", "status": "PASS", "value": "role_family x established posting month", "interpretation": "Aggregate ecological unit only."},
        {"finding": "unknown_outcomes", "status": "PASS", "value": unknown, "interpretation": "Unknown retained separately and excluded from Male/Female outcome."},
        {"finding": "candidate_level_linkage", "status": "PASS", "value": False, "interpretation": "No individual hire was linked to a posting."},
        {"finding": "causality", "status": "PASS", "value": False, "interpretation": "No causal claim is made."},
    ]
    return {
        "predictive_model_metrics.csv": metrics,
        "predictive_oof_predictions.csv": [],
        "predictive_coefficients.csv": [],
        "predictive_permutation_importance.csv": [],
        "predictive_feature_stability.csv": [],
        "predictive_sensitivity.csv": [],
        "predictive_model_agreement.csv": [],
        "predictive_findings.csv": findings,
    }


def grouped_binomial_training(cells: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    # Imports are delayed until the data adequacy gate passes.
    import statsmodels.api as sm
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    from sklearn.ensemble import GradientBoostingClassifier

    import joblib

    role_cols = ["role_family", "posting_month"]
    signal_cols = list(FAMILY_FIELDS)
    all_cols = role_cols + signal_cols
    frame = __import__("pandas").DataFrame(cells)
    groups = frame["group_id"].to_numpy()
    split_n = min(N_FOLDS, len(frame))
    cv = GroupKFold(n_splits=split_n)

    def pipeline(model_kind: str, cols: list[str]):
        cat = [c for c in cols if c in role_cols]
        numeric = [c for c in cols if c in signal_cols]
        transformers = []
        if cat:
            transformers.append(("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), cat))
        if numeric:
            transformers.append(("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric))
        prep = ColumnTransformer(transformers)
        estimator = LogisticRegression(C=0.5, max_iter=3000, random_state=SEED) if model_kind == "logistic" else GradientBoostingClassifier(n_estimators=100, max_depth=2, learning_rate=.04, subsample=.9, random_state=SEED)
        return Pipeline([("prep", prep), ("model", estimator)])

    specs = {
        "Logistic baseline": ("logistic", role_cols),
        "Logistic signal": ("logistic", all_cols),
        "Logistic signal without gender-language": ("logistic", role_cols + [c for c in signal_cols if c != "signal_gender_language"]),
        "Gradient Boosting baseline": ("gb", role_cols),
        "Gradient Boosting signal": ("gb", all_cols),
        "Gradient Boosting signal without gender-language": ("gb", role_cols + [c for c in signal_cols if c != "signal_gender_language"]),
    }
    oof: dict[str, dict[int, tuple[float, int]]] = {name: {} for name in specs}
    fold_metrics = []
    coefficient_records = []
    stability: dict[str, list[float]] = defaultdict(list)
    importance: dict[str, list[float]] = defaultdict(list)

    for fold, (train_idx, test_idx) in enumerate(cv.split(frame, groups=groups), 1):
        train_cells, test_cells = frame.iloc[train_idx], frame.iloc[test_idx]
        train_X_parts, train_y, train_w, train_g = [], [], [], []
        for _, r in train_cells.iterrows():
            for label, count in ((1, int(r.male_count)), (0, int(r.female_count))):
                if count > 0:
                    train_X_parts.append(r[all_cols])
                    train_y.append(label); train_w.append(count); train_g.append(r.group_id)
        if len(set(train_y)) < 2:
            continue
        train_X = __import__("pandas").DataFrame(train_X_parts).reset_index(drop=True)
        for name, (kind, cols) in specs.items():
            model = pipeline(kind, cols)
            model.fit(train_X[cols], np.asarray(train_y), model__sample_weight=np.asarray(train_w))
            pred = model.predict_proba(test_cells[cols])[:, 1]
            for i, (_, r) in enumerate(test_cells.iterrows()):
                oof[name][int(test_idx[i])] = (float(pred[i]), fold)
            # Fold feature coefficients: standardized signal coefficients only.
            if kind == "logistic" and name == "Logistic signal":
                try:
                    names = model.named_steps["prep"].get_feature_names_out()
                    coefs = model.named_steps["model"].coef_[0]
                    transformed = model.named_steps["prep"].transform(train_X[cols])
                    if hasattr(transformed, "toarray"):
                        transformed = transformed.toarray()
                    ci_by_name = {}
                    try:
                        glm = sm.GLM(np.asarray(train_y), sm.add_constant(transformed),
                                     family=sm.families.Binomial(), freq_weights=np.asarray(train_w)).fit()
                        ci = glm.conf_int()
                        ci_by_name = {fname: (float(ci[j + 1, 0]), float(ci[j + 1, 1])) for j, fname in enumerate(names)}
                    except Exception:
                        # Keep coefficients and disclose unavailable intervals if the
                        # fold design is singular or separated.
                        ci_by_name = {}
                    for fname, coef in zip(names, coefs):
                        bounds = ci_by_name.get(fname, (None, None))
                        coefficient_records.append({"model": name, "fold": fold, "feature": fname, "coefficient": float(coef), "odds_ratio": float(np.exp(np.clip(coef, -30, 30))), "ci_low": bounds[0], "ci_high": bounds[1], "scale": "one SD for numeric signals; one-hot unit for role/month"})
                        stability[fname].append(float(coef))
                except Exception:
                    pass
            # Permute signal families across held-out role-month groups.
            if kind == "gb" and name == "Gradient Boosting signal":
                base = pred
                base_brier = np.average((np.asarray([r.observed_male_share for _, r in test_cells.iterrows()]) - base) ** 2, weights=test_cells.known_sex_count)
                rng = np.random.default_rng(SEED + fold)
                for col in signal_cols:
                    delta = []
                    for _ in range(5):
                        perm = test_cells[cols].copy()
                        perm[col] = rng.permutation(perm[col].to_numpy())
                        pp = model.predict_proba(perm)[:, 1]
                        brier = np.average((test_cells.observed_male_share.to_numpy() - pp) ** 2, weights=test_cells.known_sex_count.to_numpy())
                        delta.append(float(brier - base_brier))
                    importance[col].append(float(np.mean(delta)))

    metric_rows = []
    for name in specs:
        ids = sorted(oof[name])
        pred = np.asarray([oof[name][i][0] for i in ids])
        yy, ww, share = [], [], []
        for i in ids:
            cell = cells[i]
            yy.extend([1] * int(cell["male_count"]) + [0] * int(cell["female_count"]))
            ww.extend([1.0] * (int(cell["male_count"]) + int(cell["female_count"])))
            share.extend([oof[name][i][0]] * (int(cell["male_count"]) + int(cell["female_count"])))
        # These weighted pseudo outcomes represent grouped-binomial likelihood;
        # no candidate-level rows are saved or claimed.
        if len(set(yy)) < 2:
            auc = ap = None
        else:
            auc = float(roc_auc_score(yy, share, sample_weight=ww))
            ap = float(average_precision_score(yy, share, sample_weight=ww))
        ycell = np.asarray([cells[i]["observed_male_share"] for i in ids])
        wcell = np.asarray([cells[i]["known_sex_count"] for i in ids], dtype=float)
        pcell = pred
        mae = float(np.average(np.abs(ycell - pcell), weights=wcell)) if len(ids) else None
        brier = float(np.average((ycell - pcell) ** 2, weights=wcell)) if len(ids) else None
        ll = None
        if len(ids):
            eps = 1e-8
            ll = float(np.average(-(ycell * np.log(np.clip(pcell, eps, 1-eps)) + (1-ycell) * np.log(np.clip(1-pcell, eps, 1-eps))), weights=wcell))
        calibration_intercept = calibration_slope = None
        if len(ids):
            try:
                clipped = np.clip(pcell, 1e-6, 1 - 1e-6)
                logits = np.log(clipped / (1 - clipped))
                calibration = sm.GLM(ycell, sm.add_constant(logits), family=sm.families.Binomial(), var_weights=wcell).fit()
                calibration_intercept, calibration_slope = map(float, calibration.params)
            except Exception:
                pass
        metric_rows.append({"model": name, "status": "ESTIMATED", "n_role_month_cells": len(ids),
                            "n_male_cells": sum(cells[i]["male_count"] > 0 for i in ids),
                            "n_female_cells": sum(cells[i]["female_count"] > 0 for i in ids),
                            "known_sex_hires": int(sum(cells[i]["known_sex_count"] for i in ids)),
                            "unknown_hires": int(sum(cells[i]["unknown_count"] for i in ids)),
                            "roc_auc": auc, "pr_auc": ap, "brier_score": brier, "log_loss": ll, "composition_mae": mae,
                            "calibration_intercept": calibration_intercept, "calibration_slope": calibration_slope, "reason": "Weighted role-month grouped-binomial OOF diagnostic."})

    # OOF predictions at ecological cell level.
    oof_rows = []
    for i, cell in enumerate(cells):
        row = {"role_family": cell["role_family"], "posting_month": cell["posting_month"], "group_id": cell["group_id"],
               "male_count": cell["male_count"], "female_count": cell["female_count"], "unknown_count": cell["unknown_count"],
               "known_sex_count": cell["known_sex_count"], "observed_male_share": cell["observed_male_share"]}
        for name in specs:
            row[name] = oof[name].get(i, (None, None))[0]
        row["fold"] = oof["Logistic signal"].get(i, (None, None))[1]
        oof_rows.append(row)
    # Return fit products; model artifacts can be trained on full cells after CV.
    return {
        "predictive_model_metrics.csv": metric_rows,
        "predictive_oof_predictions.csv": oof_rows,
        "predictive_coefficients.csv": coefficient_records,
        "predictive_permutation_importance.csv": [{"model": "Gradient Boosting signal", "feature": k, "mean_brier_increase": float(np.mean(v)), "std_brier_increase": float(np.std(v, ddof=1)) if len(v)>1 else 0.0, "folds_evaluated": len(v)} for k,v in importance.items()],
        "predictive_feature_stability.csv": [{"model": "Logistic signal", "feature": k, "fold_coefficients": json.dumps(v), "positive_fold_fraction": float(np.mean(np.asarray(v)>0)), "negative_fold_fraction": float(np.mean(np.asarray(v)<0)), "direction_stable": bool(np.all(np.asarray(v)>=0) or np.all(np.asarray(v)<=0))} for k,v in stability.items()],
        "predictive_sensitivity.csv": [],
        "predictive_model_agreement.csv": [],
        "predictive_findings.csv": [],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True); AUDIT.mkdir(parents=True, exist_ok=True); MODELS.mkdir(parents=True, exist_ok=True)
    inputs = {"master": MASTER, "hiring": HIRING, "bridge": BRIDGE, "signals": SIGNALS}
    data, input_hashes = {}, {}
    for name, path in inputs.items():
        rows, raw = read_rows(path); data[name] = rows; input_hashes[name] = {"path": str(path.relative_to(BASE)), "rows": len(rows), "sha256": sha(raw)}
    if (len(data["master"]), len(data["hiring"]), len(data["bridge"]), len(data["signals"])) != (1246,1095,41,1246):
        raise ValueError("Phase 2/3 input row counts differ from frozen expectations.")
    cells, diagnostics, bridge_source = build_role_month_dataset(data["master"], data["hiring"], data["signals"], data["bridge"])
    male_cells = sum(c["male_count"] > 0 for c in cells); female_cells = sum(c["female_count"] > 0 for c in cells)
    reason = None
    if len(cells) < MIN_ROLE_MONTHS or male_cells < MIN_CLASS_CELLS or female_cells < MIN_CLASS_CELLS:
        reason = (f"Only {len(cells)} exact role/month cells have both dated postings and known-sex observed hires "
                  f"(minimum {MIN_ROLE_MONTHS}); cells containing Male outcomes={male_cells}, Female outcomes={female_cells} "
                  f"(minimum {MIN_CLASS_CELLS} each). Grouped cross-validation is not estimable.")
    if reason:
        result = not_estimable_outputs(cells, reason)
    else:
        result = grouped_binomial_training(cells)

    audit_rows = []
    for name, path in inputs.items():
        audit_rows.append({"check": f"input:{path.name}", "status": "PASS", "rows": len(data[name]), "detail": f"Read-only; sha256={input_hashes[name]['sha256']}"})
    audit_rows += [
        {"check": "frozen_bridge_reconciliation", "status": "RECONCILED_IN_MEMORY" if bridge_source != "frozen_phase2_bridge" else "PASS", "rows": diagnostics["frozen_bridge_cells_with_hires"], "detail": f"bridge_source={bridge_source}; Phase 2 file unchanged."},
        {"check": "role_month_sample", "status": "PASS" if not reason else "NOT_ESTIMABLE", "rows": len(cells), "detail": reason or "Adequate exact role/month cells for grouped CV."},
        {"check": "candidate_level_linkage", "status": "PASS", "rows": 0, "detail": "No individual hire was linked to a Greenhouse posting."},
        {"check": "unknown_handling", "status": "PASS", "rows": sum(c["unknown_count"] for c in cells), "detail": "Unknown remains separate and is excluded from the Male/Female binomial outcome."},
    ]

    output_hashes = {}
    for filename, rows in result.items():
        path = OUT / filename
        count = csv_write(path, rows, OUTPUT_COLUMNS[filename])
        output_hashes[filename] = {"path": str(path.relative_to(BASE)), "rows": count, "sha256": sha(path.read_bytes()), "readback_verified": count == len(rows)}
        audit_rows.append({"check": f"readback:{filename}", "status": "PASS" if count == len(rows) else "FAIL", "rows": count, "detail": "Output reopened; CSV row count verified."})
    audit_path = AUDIT / "predictive_model_audit.csv"
    csv_write(audit_path, audit_rows, ["check", "status", "rows", "detail"])
    manifest = {
        "manifest_type": "version_c_phase_4_grouped_binomial_predictive_models",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "NOT_ESTIMABLE" if reason else "ESTIMATED",
        "study_window": {"start": "2026-04-01", "end": "2026-09-30"},
        "inputs": input_hashes,
        "outputs": output_hashes,
        "audit": {"path": str(audit_path.relative_to(BASE)), "rows": len(audit_rows), "sha256": sha(audit_path.read_bytes())},
        "counts": {**diagnostics, "eligible_binomial_cells": len(cells), "male_present_cells": male_cells, "female_present_cells": female_cells, "unknown_outcomes": sum(c["unknown_count"] for c in cells)},
        "bridge_source": bridge_source,
        "model_design": {"primary": "grouped/binomial logistic regression", "secondary": "scikit-learn Gradient Boosting classifier using weighted grouped-binomial pseudo-outcomes", "structural_baseline": "role family + posting month", "signal_model": "baseline + Phase 3 signal families", "sensitivity": "signal model excluding explicit gender-language family", "grouped_cv": "GroupKFold by role/month; role/month units never split across train/test"},
        "design_guards": {"phase2_phase3_inputs_modified": False, "phase5_phase6_outputs_modified": False, "candidate_level_linkage": False, "unknown_in_binary_target": False, "archive_capture_as_posting_date": False, "causal_claim": False},
        "not_estimable_reason": reason,
        "model_artifacts": {"created": False, "reason": reason or "Full-data artifacts must be written after validated grouped CV."},
    }
    manifest_path = AUDIT / "predictive_model_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Read back all Phase 4 output row counts and manifest.
    check = json.loads(manifest_path.read_text(encoding="utf-8"))
    if check["status"] != manifest["status"]:
        raise RuntimeError("Phase 4 manifest read-back failed")
    print("PREDICTION: NOT ESTIMABLE FROM PUBLIC DATA" if reason else "PREDICTION: ESTIMABILITY GATE PASSED")
    print(json.dumps({"status": manifest["status"], "diagnostics": diagnostics, "eligible_binomial_cells": len(cells), "male_cells": male_cells, "female_cells": female_cells, "reason": reason, "outputs": output_hashes, "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
