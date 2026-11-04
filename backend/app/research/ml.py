import time

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, brier_score_loss, confusion_matrix, f1_score, precision_recall_curve, precision_score, recall_score, roc_auc_score, roc_curve
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import CATEGORICAL, FEATURES, NUMERIC, frame_hash


def split_data(frame, strategy="chronological", seed=42):
    frame = frame.sort_values(["transaction_timestamp", "transaction_id"]).reset_index(drop=True)
    if strategy == "customer_grouped":
        first = GroupShuffleSplit(n_splits=1, train_size=.7, random_state=seed)
        train_idx, rest_idx = next(first.split(frame, groups=frame.customer_id))
        rest = frame.iloc[rest_idx]
        second = GroupShuffleSplit(n_splits=1, train_size=.5, random_state=seed + 1)
        val_idx, test_idx = next(second.split(rest, groups=rest.customer_id))
        parts = [frame.iloc[train_idx].copy(), rest.iloc[val_idx].copy(), rest.iloc[test_idx].copy()]
    else:
        a, b = int(len(frame) * .7), int(len(frame) * .85)
        parts = [frame.iloc[:a].copy(), frame.iloc[a:b].copy(), frame.iloc[b:].copy()]
    if any(len(part) < 20 or part.is_fraud.nunique() != 2 for part in parts):
        raise ValueError("Every training/validation/test partition needs both classes and at least 20 rows. Generate more transactions or increase the fraud rate.")
    return parts


def build_pipeline(algorithm, seed=42, trial=0):
    numerical = Pipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True)), ("scale", StandardScaler())])
    categorical = Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    preprocess = ColumnTransformer([("num", numerical, NUMERIC), ("cat", categorical, CATEGORICAL)])
    if algorithm == "logistic_regression":
        estimator = LogisticRegression(C=[1, .1, 10, .01, 100][trial], max_iter=1000, class_weight="balanced", random_state=seed)
    elif algorithm == "random_forest":
        estimator = RandomForestClassifier(n_estimators=80 + 20 * trial, max_depth=[8, 12, 6, 16, None][trial], class_weight="balanced_subsample", min_samples_leaf=2, n_jobs=2, random_state=seed)
    elif algorithm == "xgboost":
        from xgboost import XGBClassifier
        estimator = XGBClassifier(n_estimators=80 + 20 * trial, max_depth=3 + trial, learning_rate=.08, n_jobs=2, random_state=seed, eval_metric="logloss")
    elif algorithm == "isolation_forest":
        estimator = IsolationForest(n_estimators=100, contamination="auto", random_state=seed, n_jobs=2)
    else:
        raise ValueError("Unsupported algorithm")
    return Pipeline([("preprocess", preprocess), ("estimator", estimator)])


def scores(bundle, frame):
    pipeline = bundle["pipeline"]
    if bundle["algorithm"] != "isolation_forest":
        return pipeline.predict_proba(frame[FEATURES])[:, 1]
    raw = -pipeline.decision_function(frame[FEATURES])
    reference = bundle["score_reference"]
    return np.searchsorted(reference, raw, side="right") / len(reference)


def choose_threshold(y, probabilities):
    p, r, thresholds = precision_recall_curve(y, probabilities)
    f1 = 2 * p[:-1] * r[:-1] / np.maximum(p[:-1] + r[:-1], 1e-12)
    return float(thresholds[np.argmax(f1)])


def metrics(y, probabilities, threshold=.5, probabilistic=True):
    y = np.asarray(y, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    predicted = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    both = len(np.unique(y)) == 2
    result = {"accuracy": float(accuracy_score(y, predicted)), "precision": float(precision_score(y, predicted, zero_division=0)) if tp + fp else None, "recall": float(recall_score(y, predicted, zero_division=0)) if tp + fn else None, "f1": float(f1_score(y, predicted, zero_division=0)) if tp + fp + fn else None, "roc_auc": float(roc_auc_score(y, probabilities)) if both else None, "pr_auc": float(average_precision_score(y, probabilities)) if both else None, "pr_auc_definition": "average_precision", "fpr": float(fp / (fp + tn)) if fp + tn else None, "fnr": float(fn / (fn + tp)) if fn + tp else None, "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]], "positives": int(y.sum()), "negatives": int(len(y) - y.sum()), "threshold": threshold, "brier": float(brier_score_loss(y, probabilities)) if probabilistic else None}
    bins, ece = [], 0
    for lower in np.linspace(0, .9, 10):
        chosen = (probabilities >= lower) & (probabilities < lower + .1 + (1e-10 if lower >= .9 else 0))
        if chosen.any():
            observed, mean = float(y[chosen].mean()), float(probabilities[chosen].mean())
            bins.append({"predicted": mean, "observed": observed, "count": int(chosen.sum())})
            ece += abs(observed - mean) * chosen.mean()
    result.update(ece=float(ece) if probabilistic else None, calibration=bins if probabilistic else [], undefined_metric_reason=None if both else "Test data contains only one class; ranking metrics are undefined.")
    if both:
        fpr, tpr, _ = roc_curve(y, probabilities)
        p, r, _ = precision_recall_curve(y, probabilities)
        indexes = np.unique(np.linspace(0, len(fpr) - 1, min(60, len(fpr)), dtype=int))
        result["roc_curve"] = [{"fpr": float(fpr[i]), "recall": float(tpr[i])} for i in indexes]
        indexes = np.unique(np.linspace(0, len(p) - 1, min(60, len(p)), dtype=int))
        result["pr_curve"] = [{"precision": float(p[i]), "recall": float(r[i])} for i in indexes]
    return result


def train(frame, algorithm="random_forest", seed=42, split="chronological", trials=1, progress=lambda *_: None, parts=None):
    train_set, validation, test = parts or split_data(frame, split, seed)
    if len(train_set) > 70000:
        raise ValueError("Training exceeds the configured 70,000-row local limit")
    best, best_ap = None, -1
    started = time.perf_counter()
    for trial in range(trials):
        progress(f"Fitting {algorithm}: trial {trial + 1}/{trials}")
        pipeline = build_pipeline(algorithm, seed, trial)
        fitted = train_set[train_set.is_fraud == 0] if algorithm == "isolation_forest" else train_set
        pipeline.fit(fitted[FEATURES], fitted.is_fraud)
        bundle = {"pipeline": pipeline, "algorithm": algorithm}
        if algorithm == "isolation_forest":
            bundle["score_reference"] = np.sort(-pipeline.decision_function(fitted[FEATURES]))
        probability = scores(bundle, validation)
        ap = average_precision_score(validation.is_fraud, probability)
        if ap > best_ap:
            best, best_ap = bundle, ap
    best["threshold"] = choose_threshold(validation.is_fraud, scores(best, validation))
    best["background"] = train_set[FEATURES].sample(min(40, len(train_set)), random_state=seed)
    best["train"] = train_set
    best["validation"] = validation
    best["test"] = test
    best["split_manifest"] = {name: {"rows": len(part), "sha256": frame_hash(part), "transaction_ids": part.transaction_id.tolist()} for name, part in zip(["train", "validation", "test"], [train_set, validation, test])}
    result = {"algorithm": algorithm, "seed": seed, "split": split, "trials": trials, "threshold": best["threshold"], "training_seconds": time.perf_counter() - started, "train_rows": len(train_set), "validation_rows": len(validation), "test_rows": len(test), "excluded_features": ["is_fraud", "scenario_type", "transaction_id", "customer_id", "product_id"], "metrics": metrics(test.is_fraud, scores(best, test), best["threshold"], algorithm != "isolation_forest"), "validation_pr_auc": float(best_ap), "split_hashes": {name: value["sha256"] for name, value in best["split_manifest"].items()}}
    result["model_parameters"] = {key: value for key, value in best["pipeline"]["estimator"].get_params().items() if value is None or isinstance(value, (str, int, float, bool))}
    result["threshold_criterion"] = "Maximum validation F1; held-out labels do not select the threshold"
    result["preprocessing"] = {"numeric": "Training-fitted median imputation and standard scaling", "categorical": "Training-fitted mode imputation and unknown-safe one-hot encoding", "features": FEATURES}
    return best, result


def explain(bundle, frame, samples=40, seed=42, background_samples=20):
    import shap
    pipeline = bundle["pipeline"]
    background_frame = bundle["train"][FEATURES].sample(min(background_samples, len(bundle["train"])), random_state=seed)
    background = pipeline["preprocess"].transform(background_frame)
    selected = frame[FEATURES].head(samples)
    transformed = pipeline["preprocess"].transform(selected)
    estimator = pipeline["estimator"]
    if bundle["algorithm"] == "isolation_forest":
        reference = bundle["score_reference"]
        fn = lambda x: np.searchsorted(reference, -estimator.decision_function(x), side="right") / len(reference)
    else:
        fn = lambda x: estimator.predict_proba(x)[:, 1]
    # A common probability-space permutation explainer supports every detector.
    # The transformed background is training-only, never held-out test rows.
    explainer = shap.Explainer(fn, background, algorithm="permutation", seed=seed)
    explanation = explainer(transformed, max_evals=2 * transformed.shape[1] + 1, silent=True)
    names = pipeline["preprocess"].get_feature_names_out().tolist()
    values = np.asarray(explanation.values)
    global_values = sorted([{"feature": name, "importance": float(np.abs(values[:, index]).mean())} for index, name in enumerate(names)], key=lambda item: -item["importance"])
    mapping, original = {}, {}
    for index, name in enumerate(names):
        source = name.replace("num__", "") if name.startswith("num__") else next((column for column in CATEGORICAL if name.startswith(f"cat__{column}_")), name)
        mapping[name] = source
        original[source] = original.get(source, 0) + float(np.abs(values[:, index]).mean())
    local = [{"transaction_id": str(frame.iloc[i].transaction_id), "base_value": float(np.asarray(explanation.base_values)[i]), "output": float(fn(transformed[i:i + 1])[0]), "contributions": [{"feature": name, "value": float(transformed[i, j]), "contribution": float(values[i, j])} for j, name in enumerate(names)]} for i in range(len(selected))]
    errors = np.abs(np.asarray(explanation.base_values) + values.sum(axis=1) - fn(transformed))
    return {"importance": global_values, "original_feature_importance": sorted([{"feature": name, "importance": value} for name, value in original.items()], key=lambda item: -item["importance"]), "feature_mapping": mapping, "individual": local, "sample_count": len(selected), "output_space": "anomaly percentile" if bundle["algorithm"] == "isolation_forest" else "fraud probability", "max_additivity_error": float(errors.max()), "method": "SHAP permutation on transformed features", "limitation": "Attributions explain model behavior, not proof of fraud. One permutation cycle is a bounded approximation."}
