"""Version C — gated employment-selection model runner.

Current public aggregate data are rejected by the Phase 2 readiness gate. The
future internal path accepts aggregate-safe schema documentation plus an
authorized candidate-stage parquet input, then fits only after strict schema,
variation, and grouped-validation gates pass. Candidate records and predictions
are never written to outputs.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION_C = HERE.parent
INPUT_DIR = HERE / "inputs"
OUTPUT_DIR = HERE / "outputs"
AUDIT_DIR = HERE / "audit"
INPUT_DATA = INPUT_DIR / "internal_candidate_stage_training_data.parquet"
GATE_FILE = OUTPUT_DIR / "02_employment_selection_ml_gate.json"
STATUS_FILE = OUTPUT_DIR / "03_employment_selection_model_status.json"
CONTRACT_FILE = OUTPUT_DIR / "03_internal_model_feature_contract.json"
METRICS_FILE = OUTPUT_DIR / "03_model_cv_metrics.csv"
COEFFICIENTS_FILE = OUTPUT_DIR / "03_logistic_coefficients.csv"
IMPORTANCE_FILE = OUTPUT_DIR / "03_gradient_boosting_permutation_importance.csv"
AUDIT_FILE = AUDIT_DIR / "03_employment_selection_model_audit.csv"
MANIFEST_FILE = AUDIT_DIR / "03_employment_selection_model_manifest.json"
GITHUB_DESTINATION = "https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"

# A run analyzes one specified decision point. Set this only after the
# internal export's stage semantics are documented and validated.
TARGET_STAGE = "screened"
N_FOLDS = 5
MIN_ROWS = 100
MIN_REQUISITIONS = 20
MIN_REQUISITIONS_PER_OUTCOME = 5
NUMERIC_FEATURES = ["signal_research", "signal_technical", "signal_leadership",
                    "signal_collaboration", "signal_accomplishment", "signal_candidate_expectations"]
CATEGORICAL_FEATURES = ["role_family", "application_month"]
IDENTIFIER_COLUMNS = ["candidate_record_key", "requisition_id"]
AUDIT_ONLY_COLUMNS = ["demographic_group", "selection_stage"]
TARGET_COLUMN = "selected"
REQUIRED_COLUMNS = set(IDENTIFIER_COLUMNS + AUDIT_ONLY_COLUMNS + [TARGET_COLUMN] + CATEGORICAL_FEATURES + NUMERIC_FEATURES)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if not GATE_FILE.is_file():
        raise SystemExit("Run 02_employment_selection_ml_gate.py before the model runner.")
    gate = json.loads(GATE_FILE.read_text(encoding="utf-8"))
    public_gate = gate.get("gate")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    contract = {
        "target_track": "Future internal candidate-stage selection model",
        "target_column": TARGET_COLUMN,
        "target_stage": TARGET_STAGE,
        "target_definition": "Whether a candidate entering the named stage was selected to advance from that stage.",
        "predictive_features": {"numeric": NUMERIC_FEATURES, "categorical": CATEGORICAL_FEATURES},
        "identifier_columns_never_used_as_features": IDENTIFIER_COLUMNS,
        "audit_only_columns_never_used_as_features": AUDIT_ONLY_COLUMNS,
        "forbidden_features": ["sex", "gender", "name", "pronouns", "protected attributes", "post-hire outcomes", "future stage outcomes", "candidate identifiers", "Greenhouse person-linkage keys"],
        "minimum_gate": {"rows": MIN_ROWS, "independent_requisitions": MIN_REQUISITIONS,
                         "requisitions_with_each_outcome": MIN_REQUISITIONS_PER_OUTCOME,
                         "grouped_cv_folds": N_FOLDS},
        "validation": "GroupKFold by requisition; no requisition crosses train/test; class balancing, if needed, is via training weights only; no oversampling or synthetic rows.",
        "output_policy": "Aggregate cross-validation metrics and feature summaries only; do not export candidate identifiers, row-level predictions, or training rows.",
        "public_data_track": "Separate aggregate role/month target; current public gate result is not estimable and is never overridden by this internal model track.",
        "github_repository_destination": GITHUB_DESTINATION,
    }
    write_json(CONTRACT_FILE, contract)
    audit_rows: list[dict] = []
    metric_rows: list[dict] = []
    coefficient_rows: list[dict] = []
    importance_rows: list[dict] = []
    model_fit = False
    state = "ARCHITECTURE_READY_INTERNAL_DATA_NOT_PROVIDED"
    internal_gate_detail = "No authorized internal candidate-stage dataset was supplied."

    if public_gate != "ESTIMABLE":
        audit_rows.append({"check": "public_aggregate_gate", "status": "NOT_ESTIMABLE",
                           "detail": f"Public aggregate modeling remains blocked: {public_gate}."})
    else:
        audit_rows.append({"check": "public_aggregate_gate", "status": "PASS",
                           "detail": "Public aggregate gate passed; internal target remains a separate modeling track."})

    if INPUT_DATA.is_file():
        # Heavy/modeling dependencies are loaded only when an internal input is present.
        import numpy as np
        import pandas as pd
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.inspection import permutation_importance
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
        from sklearn.model_selection import GroupKFold
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler

        frame = pd.read_parquet(INPUT_DATA)
        missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
        if missing:
            internal_gate_detail = "Missing required fields: " + ", ".join(missing)
            state = "INTERNAL_SCHEMA_INVALID"
            audit_rows.append({"check": "internal_schema", "status": "FAIL", "detail": internal_gate_detail})
        else:
            audit_rows.append({"check": "internal_schema", "status": "PASS", "detail": "Required conceptual columns present."})
            stage_frame = frame.loc[frame["selection_stage"].astype(str).str.strip().str.lower() == TARGET_STAGE.lower()].copy()
            # Candidate identifiers are used only transiently to check duplicate rows.
            duplicates = stage_frame["candidate_record_key"].duplicated().any()
            target = pd.to_numeric(stage_frame[TARGET_COLUMN], errors="coerce")
            binary_ok = target.notna().all() and set(target.astype(int).unique()) == {0, 1} and (target == target.astype(int)).all()
            groups = stage_frame["requisition_id"].astype(str)
            grouped_labels = stage_frame.assign(_y=target.to_numpy()).groupby("requisition_id")["_y"]
            positive_groups = int(grouped_labels.apply(lambda s: bool((s == 1).any())).sum())
            negative_groups = int(grouped_labels.apply(lambda s: bool((s == 0).any())).sum())
            feature_cols = CATEGORICAL_FEATURES + NUMERIC_FEATURES
            feature_frame = stage_frame[feature_cols].copy()
            for col in NUMERIC_FEATURES:
                feature_frame[col] = pd.to_numeric(feature_frame[col], errors="coerce")
            variation = any(feature_frame[c].nunique(dropna=True) > 1 for c in feature_cols)
            no_empty_features = not feature_frame.isna().all(axis=0).any()
            eligible_groups = groups.nunique()
            gate_components = {
                "row_count": len(stage_frame) >= MIN_ROWS,
                "requisition_count": eligible_groups >= MIN_REQUISITIONS,
                "positive_requisition_count": positive_groups >= MIN_REQUISITIONS_PER_OUTCOME,
                "negative_requisition_count": negative_groups >= MIN_REQUISITIONS_PER_OUTCOME,
                "binary_target": binary_ok,
                "unique_candidate_stage_rows": not duplicates,
                "feature_variation": variation and no_empty_features,
                "one_target_stage": not stage_frame.empty,
            }
            internal_gate_detail = "; ".join(f"{k}={v}" for k, v in gate_components.items())
            for key, passed in gate_components.items():
                audit_rows.append({"check": "internal_gate:" + key, "status": "PASS" if passed else "NOT_MET", "detail": str(passed)})
            internal_pass = all(gate_components.values())

            # Ensure every held-out fold and its training complement have both
            # outcomes before any fitting begins.
            fold_pairs = []
            if internal_pass:
                splitter = GroupKFold(n_splits=N_FOLDS)
                for train_idx, test_idx in splitter.split(feature_frame, target.astype(int), groups):
                    if set(target.iloc[train_idx].astype(int)) != {0, 1} or set(target.iloc[test_idx].astype(int)) != {0, 1}:
                        internal_pass = False
                        internal_gate_detail += "; a grouped CV fold lacks both outcomes"
                        break
                    fold_pairs.append((train_idx, test_idx))
                audit_rows.append({"check": "grouped_cv_class_support", "status": "PASS" if internal_pass else "NOT_MET",
                                   "detail": "All folds have both classes in train and test." if internal_pass else "At least one grouped fold lacks both classes; fitting refused."})

            if not internal_pass:
                state = "INTERNAL_DATA_NOT_ESTIMABLE"
            else:
                categorical = CATEGORICAL_FEATURES
                numeric = NUMERIC_FEATURES
                preprocessor = ColumnTransformer([
                    ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                                                ("encode", OneHotEncoder(handle_unknown="ignore"))]), categorical),
                    ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                                           ("scale", StandardScaler())]), numeric),
                ])
                models = {
                    "Logistic Regression": LogisticRegression(max_iter=2000, random_state=42),
                    "Gradient Boosting": GradientBoostingClassifier(n_estimators=150, max_depth=2,
                        learning_rate=.04, subsample=.9, random_state=42),
                }
                y = target.astype(int).to_numpy()
                X = feature_frame
                groups_array = groups.to_numpy()
                pred_store = {name: np.full(len(y), np.nan) for name in models}
                coef_store: dict[str, list[float]] = {}
                permutation_store: dict[str, list[float]] = {c: [] for c in feature_cols}
                for fold_no, (train_idx, test_idx) in enumerate(fold_pairs, start=1):
                    for name, estimator in models.items():
                        pipeline = Pipeline([("preprocess", preprocessor), ("model", estimator)])
                        pipeline.fit(X.iloc[train_idx], y[train_idx])
                        probability = pipeline.predict_proba(X.iloc[test_idx])[:, 1]
                        pred_store[name][test_idx] = probability
                        if name == "Logistic Regression":
                            feature_names = pipeline.named_steps["preprocess"].get_feature_names_out()
                            for feature_name, coef in zip(feature_names, pipeline.named_steps["model"].coef_[0]):
                                coef_store.setdefault(feature_name, []).append(float(coef))
                        if name == "Gradient Boosting":
                            perm = permutation_importance(pipeline, X.iloc[test_idx], y[test_idx],
                                scoring="neg_brier_score", n_repeats=5, random_state=100 + fold_no, n_jobs=1)
                            for feature_name, value in zip(feature_cols, perm.importances_mean):
                                permutation_store[feature_name].append(float(value))
                for name, probs in pred_store.items():
                    metric_rows.append({"model": name, "target_stage": TARGET_STAGE,
                        "n_rows": len(y), "n_requisitions": int(len(set(groups_array))),
                        "grouped_cv_folds": N_FOLDS, "roc_auc": float(roc_auc_score(y, probs)),
                        "brier_score": float(brier_score_loss(y, probs)),
                        "log_loss": float(log_loss(y, probs)),
                        "accuracy_at_0_5": float(accuracy_score(y, probs >= .5)),
                        "interpretation": "Internal stage-selection association; not a causal estimate."})
                for name, values in coef_store.items():
                    coefficient_rows.append({"feature": name, "mean_fold_coefficient": float(np.mean(values)),
                        "sd_fold_coefficient": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                        "folds": len(values), "interpretation": "Predictive association only; not causal."})
                for name, values in permutation_store.items():
                    if values:
                        importance_rows.append({"feature": name, "mean_brier_score_improvement": float(np.mean(values)),
                            "sd_across_folds": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                            "folds": len(values)})
                state = "INTERNAL_MODELS_FIT_CANDIDATE_ROWS_NOT_EXPORTED"
                model_fit = True
                audit_rows.append({"check": "models_fit_only_after_internal_gate", "status": "PASS", "detail": "Both classifiers trained with requisition-grouped cross-validation; no candidate predictions exported."})
    else:
        audit_rows.append({"check": "internal_candidate_data", "status": "NOT_PROVIDED",
                           "detail": f"Expected future input: {INPUT_DATA}"})

    write_csv(METRICS_FILE, metric_rows, ["model", "target_stage", "n_rows", "n_requisitions", "grouped_cv_folds", "roc_auc", "brier_score", "log_loss", "accuracy_at_0_5", "interpretation"])
    write_csv(COEFFICIENTS_FILE, coefficient_rows, ["feature", "mean_fold_coefficient", "sd_fold_coefficient", "folds", "interpretation"])
    write_csv(IMPORTANCE_FILE, importance_rows, ["feature", "mean_brier_score_improvement", "sd_across_folds", "folds"])
    overall = "PASS" if not any(r["status"] == "FAIL" for r in audit_rows) else "FAIL"
    status = {
        "architecture_status": overall,
        "model_status": "FIT_PERFORMED" if model_fit else "NOT_PERFORMED",
        "public_aggregate_gate": public_gate,
        "internal_candidate_stage_status": state,
        "internal_gate_detail": internal_gate_detail,
        "executive_question": "Do observable recruiting signals contain predictive information about observed hiring composition?",
        "public_data_conclusion": "NOT ESTIMABLE FROM PUBLIC DATA; 3 eligible cells, 3 Male-present cells, 0 Female-present cells.",
        "internal_model_target": f"Selected to advance at the {TARGET_STAGE} stage, conditional on entering that stage.",
        "internal_model_is_same_as_public_aggregate_question": False,
        "github_repository_destination": GITHUB_DESTINATION,
        "github_publish_performed": False,
        "candidate_level_predictions_written": False,
        "candidate_identifiers_written": False,
        "demographic_feature_used": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(STATUS_FILE, status)
    with AUDIT_FILE.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check", "status", "detail"])
        writer.writeheader(); writer.writerows(audit_rows)
    manifest = {"artifact": "Version C gated employment-selection model runner",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "architecture_status": overall,
        "model_fit_performed": model_fit, "public_aggregate_gate": public_gate,
        "internal_data_present": INPUT_DATA.is_file(), "internal_input_sha256": sha256(INPUT_DATA) if INPUT_DATA.is_file() else None,
        "outputs": {"status": {"path": str(STATUS_FILE.relative_to(VERSION_C)), "sha256": sha256(STATUS_FILE)},
                    "feature_contract": {"path": str(CONTRACT_FILE.relative_to(VERSION_C)), "sha256": sha256(CONTRACT_FILE)},
                    "metrics": {"path": str(METRICS_FILE.relative_to(VERSION_C)), "sha256": sha256(METRICS_FILE)},
                    "logistic_coefficients": {"path": str(COEFFICIENTS_FILE.relative_to(VERSION_C)), "sha256": sha256(COEFFICIENTS_FILE)},
                    "gradient_boosting_importance": {"path": str(IMPORTANCE_FILE.relative_to(VERSION_C)), "sha256": sha256(IMPORTANCE_FILE)},
                    "audit": {"path": str(AUDIT_FILE.relative_to(VERSION_C)), "sha256": sha256(AUDIT_FILE)}},
        "github_repository_destination": GITHUB_DESTINATION, "github_publish_performed": False,
        "candidate_rows_or_predictions_exported": False}
    write_json(MANIFEST_FILE, manifest)

    print("VERSION C — 03 EMPLOYMENT SELECTION MODEL RUNNER")
    print("=" * 68)
    print(f"MODEL ARCHITECTURE: {overall}")
    print(f"PUBLIC AGGREGATE GATE: {public_gate}")
    print(f"INTERNAL CANDIDATE DATA: {'PRESENT' if INPUT_DATA.is_file() else 'NOT PROVIDED'}")
    print(f"INTERNAL MODEL STATUS: {state}")
    print("LOGISTIC REGRESSION: CONFIGURED")
    print("GRADIENT BOOSTING: CONFIGURED")
    print(f"MODEL FIT: {'PERFORMED' if model_fit else 'NOT PERFORMED'}")
    print("CANDIDATE ROWS / PREDICTIONS EXPORTED: NO")
    print("PUBLIC RESULT: NOT ESTIMABLE FROM PUBLIC DATA")
    print("GITHUB DESTINATION (metadata only): " + GITHUB_DESTINATION)
    print("GITHUB PUBLISH PERFORMED: NO")
    print(f"STATUS: {STATUS_FILE}")
    print(f"FEATURE CONTRACT: {CONTRACT_FILE}")
    print(f"AUDIT: {AUDIT_FILE}")
    print(f"MANIFEST: {MANIFEST_FILE}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
