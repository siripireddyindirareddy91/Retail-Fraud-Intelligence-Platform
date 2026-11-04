import numpy as np
import pandas as pd

from .data import NUMERIC, apply_scenario, frame_hash, quality, sequence_features
from .generative import fit_synthesizer, sample_synthesizer
from .ml import metrics, scores, split_data, train


def augment(training, ratio, method, seed, epochs=5):
    count = max(100, round(len(training) * ratio))
    rng = np.random.default_rng(seed)
    template = training.sample(count, replace=True, random_state=seed).reset_index(drop=True).copy()
    template["transaction_id"] = [f"AUG-{seed}-{i}" for i in range(count)]
    if method in {"ctgan", "tvae"}:
        synthesizer = fit_synthesizer(training, method, epochs, seed)
        extra = sample_synthesizer(synthesizer, template)
    else:
        extra = template
        if method != "bootstrap_control":
            extra["transaction_amount"] = (extra.transaction_amount * rng.lognormal(0, .15 if method == "statistical" else .05, count)).clip(.01).round(2)
            extra["quantity"] = (extra.quantity + rng.integers(-1, 2, count)).clip(1)
        extra = sequence_features(extra)
    extra["scenario_type"] = "training_augmentation"
    return pd.concat([training, extra], ignore_index=True)


def shift_frame(frame, severity=.5):
    shifted = frame.copy()
    shifted["transaction_amount"] = (shifted.transaction_amount * (1 + severity)).round(2)
    shifted["previous_transaction_amount"] *= 1 + severity
    selected = shifted.index[::3]
    shifted.loc[selected, "product_category"] = "shifted_category"
    shifted["customer_account_age_days"] = (shifted.customer_account_age_days * (1 - severity / 2)).round()
    return shifted


def paired_recall_ci(test, left, right, left_threshold, right_threshold, seed=42):
    rng = np.random.default_rng(seed)
    groups = test.groupby("customer_id").indices
    keys = list(groups)
    deltas = []
    truth = test.is_fraud.to_numpy()
    for _ in range(100):
        indexes = np.concatenate([groups[key] for key in rng.choice(keys, len(keys), replace=True)])
        positive = truth[indexes] == 1
        if positive.any():
            a = (left[indexes][positive] >= left_threshold).mean()
            b = (right[indexes][positive] >= right_threshold).mean()
            deltas.append(float(b - a))
    return {"lower": float(np.quantile(deltas, .025)) if deltas else None, "upper": float(np.quantile(deltas, .975)) if deltas else None, "method": "100 paired customer-block bootstrap replicates", "unit": "recall difference"}


def recall_at_fpr(bundle, test, target=.01):
    validation = bundle["validation"]
    negative = scores(bundle, validation)[validation.is_fraud.to_numpy() == 0]
    threshold = float(np.quantile(negative, 1 - target, method="higher"))
    evaluation = metrics(test.is_fraud, scores(bundle, test), threshold)
    return {"target_validation_fpr": target, "threshold": threshold, "achieved_test_fpr": evaluation["fpr"], "test_recall": evaluation["recall"]}


def run_study(frame, config, progress=lambda *_: None):
    # Never expose the reserved fraud family to baseline OR augmentation fitting.
    original_rows = len(frame)
    frame = frame[frame.scenario_type != "novel_combination"].copy()
    results, all_pairs = [], []
    for seed in config.seeds:
        progress(f"Seed {seed}: freezing shared held-out sets")
        training, validation, baseline_test = split_data(frame, seed=seed)
        shifted = shift_frame(baseline_test)
        unseen = apply_scenario(baseline_test, "novel_combination", .2, seed=seed + 100)
        unseen_ids = set(baseline_test.transaction_id)
        unseen = sequence_features(pd.concat([training, validation, unseen], ignore_index=True))
        unseen = unseen[unseen.transaction_id.isin(unseen_ids)].reset_index(drop=True)
        progress(f"Seed {seed}: training baseline")
        baseline, baseline_result = train(frame, config.algorithm, seed, parts=(training, validation, baseline_test), progress=progress)
        progress(f"Seed {seed}: generating training-only augmentation")
        augmented_train = augment(training, config.ratio, config.augmentation, seed, config.epochs)
        augmented, augmented_result = train(frame, config.algorithm, seed, parts=(augmented_train, validation, baseline_test), progress=progress)
        control_train = augment(training, config.ratio, "bootstrap_control", seed)
        control, _ = train(frame, config.algorithm, seed, parts=(control_train, validation, baseline_test), progress=progress)
        pairs = []
        for condition, test, letters in [("baseline", baseline_test, ("A", "B")), ("shifted", shifted, ("C", "D")), ("unseen", unseen, ("E", "F"))]:
            progress(f"Seed {seed}: evaluating shared {condition} test set")
            left, right = scores(baseline, test), scores(augmented, test)
            a, b = metrics(test.is_fraud, left, baseline["threshold"]), metrics(test.is_fraud, right, augmented["threshold"])
            delta = {key: b[key] - a[key] if a[key] is not None and b[key] is not None else None for key in ["precision", "recall", "f1", "pr_auc", "roc_auc", "fpr", "fnr", "brier", "ece"]}
            pair = {"condition": condition, "baseline_experiment": letters[0], "augmented_experiment": letters[1], "test_sha256": frame_hash(test), "test_rows": len(test), "baseline": a, "augmented": b, "signed_delta": delta, "recall_difference_ci": paired_recall_ci(test, left, right, baseline["threshold"], augmented["threshold"], seed), "baseline_recall_at_fpr": recall_at_fpr(baseline, test), "augmented_recall_at_fpr": recall_at_fpr(augmented, test), "same_size_bootstrap_control": metrics(test.is_fraud, scores(control, test), control["threshold"])}
            pairs.append(pair)
        reference_recall = pairs[0]["baseline"]["recall"]
        for pair in pairs:
            pair["baseline_recall_degradation"] = reference_recall - pair["baseline"]["recall"]
            pair["augmented_recall_degradation"] = pairs[0]["augmented"]["recall"] - pair["augmented"]["recall"]
        results.append({"seed": seed, "pairs": pairs, "baseline_training": baseline_result, "augmented_training": augmented_result, "training_only_augmentation": True, "held_out_shared": True, "excluded_unseen_training_rows": original_rows - len(frame)})
        all_pairs.extend(pairs)
    summaries = []
    for condition in ["baseline", "shifted", "unseen"]:
        chosen = [pair for pair in all_pairs if pair["condition"] == condition]
        summaries.append({"condition": condition, "baseline_recall": float(np.mean([p["baseline"]["recall"] for p in chosen])), "augmented_recall": float(np.mean([p["augmented"]["recall"] for p in chosen])), "recall_delta": float(np.mean([p["signed_delta"]["recall"] for p in chosen])), "baseline_pr_auc": float(np.mean([p["baseline"]["pr_auc"] for p in chosen])), "augmented_pr_auc": float(np.mean([p["augmented"]["pr_auc"] for p in chosen]))})
    retained = []
    for run in results:
        baseline_recall = run["pairs"][0]["baseline"]["recall"]
        if baseline_recall:
            retained.extend(min(1, pair["baseline"]["recall"] / baseline_recall) for pair in run["pairs"][1:])
    return {"summary": summaries, "runs": results, "retention_score": float(np.mean(retained) * 100) if retained else None, "retention_definition": "100 × mean(min(1, stressed baseline recall / unshifted baseline recall)) across shifted and unseen conditions; null if unshifted recall is zero", "metric_priority": "Recall, precision, PR-AUC; accuracy is secondary", "limitations": "Artificial-only evaluation. Confidence intervals are conditional on each generated population. Repeated fitting seeds are not independent real-world populations. Augmentation can reduce performance."}


def sensitivity(bundle, analysis, seed=42, levels=None, noise_mode="all", unseen_scenario="novel_combination"):
    test = bundle["test"].copy()
    rng = np.random.default_rng(seed)
    rows = []
    if analysis == "imbalance":
        for rate in levels or [.005, .01, .02, .05, .1, .2]:
            if rate <= 0 or rate >= 1:
                raise ValueError("Prevalence levels must be strictly between zero and one")
            positives, negatives = test[test.is_fraud == 1], test[test.is_fraud == 0]
            size = min(len(test), int(len(positives) / rate), int(len(negatives) / (1 - rate)))
            p, n = max(1, round(size * rate)), max(1, size - round(size * rate))
            sampled = pd.concat([positives.sample(min(p, len(positives)), random_state=seed), negatives.sample(min(n, len(negatives)), random_state=seed)])
            rows.append({"level": rate, "actual_fraud_rate": float(sampled.is_fraud.mean()), **metrics(sampled.is_fraud, scores(bundle, sampled), bundle["threshold"], bundle["algorithm"] != "isolation_forest")})
    elif analysis == "unseen":
        unseen = apply_scenario(test, unseen_scenario, .2, seed=seed)
        unseen_ids = set(test.transaction_id)
        unseen = sequence_features(pd.concat([bundle["train"], bundle["validation"], unseen], ignore_index=True))
        unseen = unseen[unseen.transaction_id.isin(unseen_ids)].reset_index(drop=True)
        rows.append({"level": unseen_scenario, **metrics(unseen.is_fraud, scores(bundle, unseen), bundle["threshold"], bundle["algorithm"] != "isolation_forest")})
    else:
        for mode in ["numeric_noise", "missingness", "category_corruption", "behavior_shift", "frequency_shift"]:
            if noise_mode != "all" and mode != noise_mode:
                continue
            for severity in levels or [0, .05, .1, .2, .4]:
                altered = test.copy()
                if mode == "numeric_noise":
                    for feature in NUMERIC:
                        altered[feature] = altered[feature].astype(float) + rng.normal(0, max(float(bundle["train"][feature].std()), .01) * severity, len(altered))
                elif mode == "missingness":
                    for feature in NUMERIC:
                        altered[feature] = altered[feature].astype(float)
                        altered.loc[rng.random(len(altered)) < severity, feature] = np.nan
                elif mode == "category_corruption":
                    altered.loc[rng.random(len(altered)) < severity, "device_type"] = "corrupted_device"
                elif mode == "behavior_shift":
                    altered = shift_frame(altered, severity)
                else:
                    altered["transaction_frequency"] = altered.transaction_frequency * (1 + severity * 5)
                    altered["transaction_velocity"] = altered.transaction_velocity * (1 + severity * 5)
                rows.append({"mode": mode, "level": severity, **metrics(altered.is_fraud, scores(bundle, altered), bundle["threshold"], bundle["algorithm"] != "isolation_forest")})
    return {"analysis": analysis, "rows": rows, "test_sha256": frame_hash(test), "threshold_frozen": True, "limitation": "Uses the model's stored held-out set. Missingness/noise is label-preserving; observed harm depends on this artificial population."}
