import importlib.metadata
import io
import logging
import time

import numpy as np
import pandas as pd
from sqlalchemy import func, select, update

from ..models import Artifact, Dataset, Experiment, GenerativeModel, Job, MLModel, Prediction, ResearchRun, User, now
from ..services.artifacts import safe_path, write_bytes, write_json
from ..services.jobs import finish
from .data import FEATURES, apply_scenario, generate, quality, validation
from .generative import fit_synthesizer, sample_synthesizer, sdv_quality
from .ml import explain, metrics, scores, train
from .robustness import run_study, sensitivity
from .schemas import Analysis, Generation, GenerativeTraining, Robustness, Scenario, Training
from .storage import clean, read_bundle, read_frame, records, write_bundle, write_frame

log = logging.getLogger("retail.research")


def track(settings, owner_id, kind, config, result, artifact_path=None):
    try:
        import os
        os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
        from mlflow.tracking import MlflowClient
        client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
        name = f"retail-research-{owner_id}"
        experiment = client.get_experiment_by_name(name)
        artifact_root = settings.artifact_root / "mlflow" / owner_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        experiment_id = experiment.experiment_id if experiment else client.create_experiment(name, artifact_location=artifact_root.resolve().as_uri())
        run = client.create_run(experiment_id, tags={"workflow": kind, "artificial_data_only": "true"})
        for key, value in config.items():
            client.log_param(run.info.run_id, key, str(value)[:1000])
        for key, value in result.get("metrics", {}).items():
            if isinstance(value, (int, float)) and np.isfinite(value):
                client.log_metric(run.info.run_id, key, float(value))
        for key, value in result.get("split_hashes", {}).items():
            client.set_tag(run.info.run_id, f"{key}_sha256", value)
        if artifact_path:
            client.log_artifact(run.info.run_id, str(artifact_path))
        client.set_terminated(run.info.run_id)
        return run.info.run_id, "tracked"
    except Exception as error:
        log.warning("mlflow_tracking_failed", extra={"exception_type": type(error).__name__})
        return None, f"tracking_failed:{type(error).__name__}"


def process(sessions, settings, job_id, worker_id, progress):
    with sessions() as db:
        job = db.get(Job, job_id)
        owner_id, kind, config = job.owner_id, job.kind, job.config
        dataset = db.get(Dataset, config.get("dataset_id")) if config.get("dataset_id") else None
        frame = read_frame(db, settings, dataset) if dataset else None
        model = db.get(MLModel, config.get("model_id")) if config.get("model_id") else None
        bundle = read_bundle(db, settings, model.artifact_id) if model else None
    progress("Validating research configuration")
    result, artifact_id, model_id = {}, None, model.id if model else None
    new_frame, learned, fitted, experiment_result = None, None, None, None
    if kind == "dataset.generate":
        cfg = Generation(**config)
        progress("Sampling fictional customer transactions")
        new_frame = generate(cfg.model_copy(update={"method": "statistical"}) if cfg.method in {"ctgan", "tvae"} else cfg)
        if cfg.method in {"ctgan", "tvae"}:
            with sessions() as db:
                gm = db.get(GenerativeModel, str(cfg.generative_model_id))
                learned = read_bundle(db, settings, gm.artifact_id)
            progress("Sampling learned synthetic transactions (indeterminate)")
            parts = []
            positive_count = round(len(new_frame) * cfg.fraud_rate)
            if positive_count:
                parts.append(sample_synthesizer(learned, new_frame.iloc[:positive_count].copy(), {**cfg.conditions, "is_fraud": 1}))
            if positive_count < len(new_frame):
                parts.append(sample_synthesizer(learned, new_frame.iloc[positive_count:].copy(), {**cfg.conditions, "is_fraud": 0}))
            from .data import sequence_features
            new_frame = sequence_features(pd.concat(parts, ignore_index=True))
        result = {"validation": validation(new_frame), "method": cfg.method, "seed": cfg.seed, "synthetic_only": True, "label_definition": "Simulator ground truth; separate from predictions"}
    elif kind == "scenario.execute":
        cfg = Scenario(**config)
        progress(f"Applying coherent {cfg.scenario} scenario")
        new_frame = apply_scenario(frame, cfg.scenario, cfg.fraction, cfg.severity, cfg.seed)
        result = {"validation": validation(new_frame), "scenario": cfg.scenario, "source_dataset_id": dataset.id, "affected_requested_fraction": cfg.fraction}
    elif kind == "generative.train":
        cfg = GenerativeTraining(**config)
        progress(f"Fitting SDV {cfg.method.upper()} for {cfg.epochs} epochs (indeterminate)")
        learned = fit_synthesizer(frame, cfg.method, cfg.epochs, cfg.seed)
        progress("Sampling the fitted synthesizer for quality evaluation")
        generated = sample_synthesizer(learned, frame.head(min(500, len(frame))).copy())
        progress("Evaluating learned distributions and SDV quality")
        result = {"method": cfg.method, "epochs": cfg.epochs, "training_rows": len(frame), "seed": cfg.seed, "quality": quality(generated, frame), "sdv_quality": sdv_quality(frame, generated), "limitations": "The synthesizer was trained on an artificial seed dataset. Quality is not a privacy guarantee."}
    elif kind == "model.train":
        cfg = Training(**config)
        fitted, result = train(frame, cfg.algorithm, cfg.seed, cfg.split, cfg.trials, progress)
    elif kind == "robustness.run":
        result = run_study(frame, Robustness(**config), progress)
    elif kind == "predictions.batch":
        progress("Scoring transactions with the saved preprocessing pipeline")
        probability = scores(bundle, frame)
        predicted = (probability >= bundle["threshold"]).astype(int)
        result = {"metrics": metrics(frame.is_fraud, probability, bundle["threshold"], bundle["algorithm"] != "isolation_forest"), "scored_rows": len(frame), "model_id": model.id, "threshold": bundle["threshold"], "ground_truth_separate": True}
        for start in range(0, len(frame), 500):
            progress(f"Persisting predictions {start + 1}–{min(start + 500, len(frame))}")
            with sessions() as db:
                for index in range(start, min(start + 500, len(frame))):
                    row = frame.iloc[index]
                    is_anomaly = bundle["algorithm"] == "isolation_forest"
                    db.add(Prediction(owner_id=owner_id, model_id=model.id, dataset_id=dataset.id, transaction_id=str(row.transaction_id), features=records(frame.iloc[index:index + 1][FEATURES])[0], probability=None if is_anomaly else float(probability[index]), anomaly_score=float(probability[index]) if is_anomaly else None, predicted_class=int(predicted[index]), ground_truth=int(row.is_fraud), risk="high" if predicted[index] else "low"))
                db.commit()
    elif kind.startswith("analysis."):
        cfg = Analysis(**config)
        analysis = cfg.analysis
        progress(f"Computing {analysis} from persisted data")
        if analysis == "validation":
            result = validation(frame)
        elif analysis in {"quality", "drift"}:
            with sessions() as db:
                reference = db.get(Dataset, str(cfg.reference_dataset_id)) if cfg.reference_dataset_id else dataset
                reference_frame = read_frame(db, settings, reference)
            result = quality(frame, reference_frame)
            result["reference_dataset_id"] = reference.id
            if analysis == "quality":
                result["sdv_quality"] = sdv_quality(reference_frame, frame)
        elif analysis == "patterns":
            frame = frame.copy()
            frame["flag"] = (scores(bundle, frame) >= bundle["threshold"]).astype(int) if cfg.source == "predictions" else frame.is_fraud
            result = {"rows": [{"group": cfg.group_by, "category": str(name), "transactions": len(group), "flagged_count": int(group.flag.sum()), "flagged_rate": float(group.flag.mean())} for name, group in frame.groupby(cfg.group_by)], "source": cfg.source}
        elif analysis in {"noise", "imbalance", "unseen"}:
            result = sensitivity(bundle, analysis, cfg.seed, cfg.levels, cfg.noise_mode, cfg.unseen_scenario)
            if analysis == "unseen":
                if cfg.unseen_scenario in set(bundle["train"].scenario_type):
                    raise ValueError("The selected model has seen the reserved fraud family. Train a model without it first.")
                result["training_exclusion_verified"] = True
        elif analysis in {"shap", "importance"}:
            explanation_frame = bundle["test"]
            if cfg.prediction_id:
                with sessions() as db:
                    prediction = db.get(Prediction, str(cfg.prediction_id))
                    explanation_frame = pd.DataFrame([{**prediction.features, "transaction_id": prediction.transaction_id}])
            result = explain(bundle, explanation_frame, cfg.samples, cfg.seed, cfg.background_samples)
        elif analysis == "permutation":
            from sklearn.inspection import permutation_importance
            test = bundle["test"]
            if bundle["algorithm"] == "isolation_forest":
                raise ValueError("Use SHAP importance for the anomaly baseline; supervised permutation PR-AUC is not supported for this estimator")
            importance = permutation_importance(bundle["pipeline"], test[FEATURES], test.is_fraud, scoring="average_precision", n_repeats=3, random_state=cfg.seed, n_jobs=1)
            result = {"importance": sorted([{"feature": name, "importance": float(value), "std": float(std)} for name, value, std in zip(FEATURES, importance.importances_mean, importance.importances_std)], key=lambda item: -item["importance"]), "method": "Held-out permutation PR-AUC decrease", "repeats": 3}
        elif analysis in {"risk", "performance"}:
            test = bundle["test"] if analysis == "performance" else frame
            probabilities = scores(bundle, test)
            from .robustness import recall_at_fpr
            threshold = cfg.threshold if cfg.threshold is not None and analysis == "risk" else bundle["threshold"]
            result = {"metrics": metrics(test.is_fraud, probabilities, threshold, bundle["algorithm"] != "isolation_forest"), "risk_bands": [{"band": f"{lower:.1f}–{lower + .2:.1f}", "count": int(((probabilities >= lower) & (probabilities < lower + .2 + (1e-10 if lower == .8 else 0))).sum())} for lower in [0, .2, .4, .6, .8]], "recall_at_target_fpr": recall_at_fpr(bundle, test, cfg.target_fpr), "evaluation_scope": "stored held-out test" if analysis == "performance" else "selected dataset (may include training rows)"}
        else:
            raise ValueError("Unsupported analysis")
    elif kind == "report.generate":
        with sessions() as db:
            source = db.get(ResearchRun, config["run_id"])
            run_data = {"id": source.id, "kind": source.kind, "config": source.config, "result": source.result, "created_at": source.created_at.isoformat() + "Z"}
        progress("Rendering actual research results")
        if config["format"] == "pdf":
            from .reports import report_pdf
            payload = report_pdf(run_data)
            content_type, extension = "application/pdf", ".pdf"
        else:
            rows = source.result.get("summary", source.result.get("rows", []))
            if not rows:
                rows = [{"metric": key, "value": value} for key, value in source.result.get("metrics", source.result).items() if isinstance(value, (str, float, int, type(None))) ]
            payload = pd.json_normalize(rows).to_csv(index=False).encode()
            content_type, extension = "text/csv", ".csv"
        with sessions() as db:
            artifact = write_bytes(db, settings.artifact_root, owner_id, f"research-report-{source.id}{extension}", payload, content_type, extension)
            db.commit()
            artifact_id = artifact.id
        result = {"source_run_id": source.id, "format": config["format"], "download_artifact_id": artifact_id}
    else:
        raise ValueError("Unsupported research job")

    progress("Publishing versioned research artifacts")
    with sessions() as db:
        db.execute(update(Job).where(Job.id == job_id).values(heartbeat_at=Job.heartbeat_at))
        publishing_job = db.get(Job, job_id)
        if publishing_job.state != "running" or publishing_job.worker_id != worker_id:
            return
        if publishing_job.cancel_requested:
            finish(db, publishing_job, "cancelled")
            db.commit()
            return
        if new_frame is not None:
            name = config.get("name", f"{config.get('scenario', 'derived')} transactions")
            new_dataset = write_frame(db, settings, owner_id, new_frame, name, config.get("method", "scenario"), {**config, "parent_dataset_id": dataset.id if dataset else None})
            result["dataset_id"] = new_dataset.id
            artifact_id = new_dataset.artifact_id
        if kind == "generative.train":
            artifact = write_bundle(db, settings, owner_id, learned, "generative-model.pkl")
            gm = GenerativeModel(owner_id=owner_id, training_dataset_id=dataset.id, artifact_id=artifact.id, name=config["name"], method=config["method"], config=config)
            db.add(gm)
            db.flush()
            result["generative_model_id"], artifact_id = gm.id, artifact.id
        if fitted is not None:
            artifact = write_bundle(db, settings, owner_id, fitted, "fraud-model.pkl")
            db.execute(update(User).where(User.id == owner_id).values(active=User.active))
            version = (db.scalar(select(func.max(MLModel.version)).where(MLModel.owner_id == owner_id, MLModel.name == config["name"])) or 0) + 1
            experiment = Experiment(owner_id=owner_id, name=config["name"], kind="training", config=config, status="completed")
            db.add(experiment)
            db.flush()
            fitted_model = MLModel(owner_id=owner_id, artifact_id=artifact.id, experiment_id=experiment.id, name=config["name"], algorithm=config["algorithm"], version=version, threshold=fitted["threshold"], status="active")
            db.add(fitted_model)
            db.flush()
            model_id, artifact_id = fitted_model.id, artifact.id
            result.update(model_id=model_id, model_version=version, experiment_id=experiment.id)
        if kind == "robustness.run":
            experiment = Experiment(owner_id=owner_id, name=config.get("name", f"A–F robustness {job_id[:8]}"), kind="robustness", config=config, status="completed")
            db.add(experiment)
            db.flush()
            result["experiment_id"] = experiment.id
        result["versions"] = {name: importlib.metadata.version(name) for name in ["numpy", "pandas", "scikit-learn", "sdv", "shap", "torch", "xgboost", "mlflow"]}
        import platform
        result["versions"]["python"] = platform.python_version()
        if dataset:
            result["source_dataset_sha256"] = db.get(Artifact, dataset.artifact_id).sha256
        if artifact_id:
            result["artifact_sha256"] = db.get(Artifact, artifact_id).sha256
        result = clean(result)
        run = ResearchRun(owner_id=owner_id, job_id=job_id, dataset_id=dataset.id if dataset else result.get("dataset_id"), model_id=model_id, kind=kind, config=config, result=result, artifact_id=artifact_id)
        db.add(run)
        db.flush()
        run_id = run.id
        result = {**result, "run_id": run_id}
        run.result = result
        if artifact_id is None:
            artifact = write_json(db, settings.artifact_root, owner_id, f"{kind.replace('.', '-')}-results.json", result)
            artifact_id = artifact.id
            run.artifact_id = artifact_id
        db.commit()
    with sessions() as db:
        tracked_artifact = db.get(Artifact, artifact_id)
        tracking_path = safe_path(settings.artifact_root, tracked_artifact.storage_key)
    tracking_id, tracking_status = track(settings, owner_id, kind, config, result, tracking_path)
    with sessions() as db:
        run = db.get(ResearchRun, run_id)
        run.mlflow_run_id = tracking_id
        run.result = {**run.result, "tracking_status": tracking_status}
        job = db.get(Job, job_id)
        # Work has completed and committed; do not claim success before publication.
        if job.state == "running" and job.worker_id == worker_id:
            job.result_artifact_id = artifact_id
            job.completed_units, job.total_units = 1, 1
            finish(db, job, "succeeded")
        db.commit()
