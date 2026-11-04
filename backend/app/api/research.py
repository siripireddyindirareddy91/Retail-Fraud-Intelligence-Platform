import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import Response
from sqlalchemy import select

from .deps import CurrentUser, DB, owned
from .jobs import submission_data
from ..core.errors import APIError
from ..models import Artifact, Dataset, GenerativeModel, Job, MLModel, Notification, Prediction, ResearchRun
from ..research.data import CATEGORICAL, FEATURES, NUMERIC, SCENARIOS, validation
from ..research.ml import scores
from ..research.schemas import Analysis, BatchPrediction, Generation, GenerativeTraining, Report, Robustness, Scenario, SinglePrediction, Training
from ..research.storage import clean, read_bundle, read_frame, records
from ..schemas import Input
from ..services.jobs import record_event
from ..services.rate_limit import enforce
from ..services.research_runtime import forward_if_needed, require_worker

router = APIRouter(tags=["Research workflows"])


@router.get("/analytics/overview")
def analytics(request: Request, user: CurrentUser, db: DB):
    datasets = db.scalars(select(Dataset).where(Dataset.owner_id == user.id).order_by(Dataset.created_at.desc()).limit(5)).all()
    activity, categories = [], []
    if datasets:
        delegated = forward_if_needed(request, "pandas", "fastparquet")
        if delegated is not None:
            return delegated
        import pandas as pd
        frame = read_frame(db, request.app.state.settings, datasets[0])
        frame["day"] = pd.to_datetime(frame.transaction_timestamp, utc=True, format="ISO8601").dt.strftime("%Y-%m-%d")
        for day, group in frame.groupby("day"):
            activity.append({"day": day, "transactions": len(group), "fraud": int(group.is_fraud.sum()), "fraud_percentage": float(group.is_fraud.mean() * 100)})
        categories = [{"category": name, "legitimate": int((group.is_fraud == 0).sum()), "fraud": int(group.is_fraud.sum())} for name, group in frame.groupby("product_category")]
    training = db.scalars(select(ResearchRun).where(ResearchRun.owner_id == user.id, ResearchRun.kind == "model.train").order_by(ResearchRun.created_at.desc()).limit(5)).all()
    quality_runs = db.scalars(select(ResearchRun).where(ResearchRun.owner_id == user.id, ResearchRun.kind == "analysis.quality").order_by(ResearchRun.created_at.desc()).limit(5)).all()
    robustness_run = db.scalar(select(ResearchRun).where(ResearchRun.owner_id == user.id, ResearchRun.kind == "robustness.run").order_by(ResearchRun.created_at.desc()).limit(1))
    return {"latest_dataset": dataset_data(datasets[0]) if datasets else None, "recent_datasets": [dataset_data(item) for item in datasets], "activity": activity, "categories": categories, "model_performance": [{"name": item.config.get("name", item.id[:8]), "recall": item.result["metrics"]["recall"], "pr_auc": item.result["metrics"]["pr_auc"]} for item in training], "quality": [{"name": item.id[:8], "score": item.result.get("sdv_quality", {}).get("score")} for item in quality_runs], "robustness": {"summary": robustness_run.result.get("summary"), "limitations": robustness_run.result.get("limitations")} if robustness_run else None, "alerts": [{"message": item.message, "created_at": item.created_at.isoformat() + "Z"} for item in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.severity == "warning").order_by(Notification.created_at.desc()).limit(5))], "recent_jobs": [{"kind": item.kind, "state": item.state, "stage": item.stage} for item in db.scalars(select(Job).where(Job.owner_id == user.id).order_by(Job.created_at.desc()).limit(5))]}


def enqueue(db, request, user, kind, payload):
    config = payload.model_dump(mode="json")
    for field, model in [("dataset_id", Dataset), ("reference_dataset_id", Dataset), ("model_id", MLModel), ("generative_model_id", GenerativeModel), ("run_id", ResearchRun), ("prediction_id", Prediction)]:
        if config.get(field):
            owned(db, model, config[field], user.id)
    require_worker(db, request.app.state.settings)
    active = db.scalars(select(Job).where(Job.owner_id == user.id, Job.state.in_(["queued", "running"]))).all()
    if len(active) >= 5:
        raise APIError(429, "queue_limit", "At most five jobs may be queued or running per account.")
    enforce(db, f"job:{user.id}", request.app.state.settings.job_limit, seconds=60)
    job = Job(owner_id=user.id, kind=kind, config=config)
    db.add(job)
    db.flush()
    record_event(db, job)
    db.commit()
    return submission_data(job)


@router.post("/datasets/generate", status_code=202)
def generate_dataset(payload: Generation, request: Request, user: CurrentUser, db: DB):
    if payload.generative_model_id:
        gm = owned(db, GenerativeModel, payload.generative_model_id, user.id)
        if gm.method != payload.method:
            raise APIError(422, "method_mismatch", "The fitted synthesizer method must match the generation method.")
    return enqueue(db, request, user, "dataset.generate", payload)


def dataset_data(dataset):
    return {"id": dataset.id, "artifact_id": dataset.artifact_id, "name": dataset.name, "method": dataset.method, "row_count": dataset.row_count, "fraud_count": dataset.fraud_count, "fraud_rate": dataset.fraud_count / max(1, dataset.row_count), "config": dataset.config, "created_at": dataset.created_at.isoformat() + "Z"}


@router.get("/datasets/{dataset_id}")
def dataset_detail(dataset_id: UUID, user: CurrentUser, db: DB):
    return dataset_data(owned(db, Dataset, dataset_id, user.id))


@router.get("/datasets/{dataset_id}/preview")
def preview_dataset(dataset_id: UUID, request: Request, user: CurrentUser, db: DB, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), q: str = Query("", max_length=100), label: int | None = Query(None, ge=0, le=1), min_amount: float = Query(0, ge=0), max_amount: float = Query(10000000, ge=0), start_at: str | None = None, end_at: str | None = None):
    dataset = owned(db, Dataset, dataset_id, user.id)
    delegated = forward_if_needed(request, "pandas", "fastparquet")
    if delegated is not None:
        return delegated
    import pandas as pd
    frame = read_frame(db, request.app.state.settings, dataset)
    if q:
        frame = frame[frame.transaction_id.str.contains(q, regex=False) | frame.customer_id.str.contains(q, regex=False)]
    if label is not None:
        frame = frame[frame.is_fraud == label]
    frame = frame[frame.transaction_amount.between(min_amount, max_amount)]
    try:
        if start_at:
            frame = frame[pd.to_datetime(frame.transaction_timestamp, utc=True, format="ISO8601") >= pd.to_datetime(start_at, utc=True, format="ISO8601")]
        if end_at:
            frame = frame[pd.to_datetime(frame.transaction_timestamp, utc=True, format="ISO8601") <= pd.to_datetime(end_at, utc=True, format="ISO8601")]
    except (ValueError, TypeError):
        raise APIError(422, "invalid_date", "Date filters must be valid timestamps.")
    return {"items": records(frame.iloc[offset:offset + limit]), "total": len(frame), "offset": offset, "limit": limit, "columns": list(frame.columns)}


@router.get("/datasets/{dataset_id}/statistics")
def statistics(dataset_id: UUID, request: Request, user: CurrentUser, db: DB):
    dataset = owned(db, Dataset, dataset_id, user.id)
    delegated = forward_if_needed(request, "pandas", "fastparquet")
    if delegated is not None:
        return delegated
    import pandas as pd
    frame = read_frame(db, request.app.state.settings, dataset)
    return {**validation(frame), "activity": records(frame.assign(day=pd.to_datetime(frame.transaction_timestamp, utc=True, format="ISO8601").dt.strftime("%Y-%m-%d")).groupby("day").agg(transactions=("is_fraud", "count"), fraud=("is_fraud", "sum")).reset_index()), "categories": records(frame.groupby("product_category").agg(transactions=("is_fraud", "count"), fraud=("is_fraud", "sum")).reset_index())}


@router.get("/datasets/{dataset_id}/download")
def dataset_download(dataset_id: UUID, request: Request, user: CurrentUser, db: DB, format: Literal["csv", "json"] = "csv"):
    dataset = owned(db, Dataset, dataset_id, user.id)
    delegated = forward_if_needed(request, "pandas", "fastparquet", stream="file")
    if delegated is not None:
        return delegated
    frame = read_frame(db, request.app.state.settings, dataset)
    payload = frame.to_csv(index=False) if format == "csv" else frame.to_json(orient="records")
    return Response(payload, media_type="text/csv" if format == "csv" else "application/json", headers={"Content-Disposition": f'attachment; filename="synthetic-transactions-{dataset_id}.{format}"'})


@router.post("/generative-models/train", status_code=202)
def train_generator(payload: GenerativeTraining, request: Request, user: CurrentUser, db: DB):
    return enqueue(db, request, user, "generative.train", payload)


@router.get("/generative-models")
def list_generators(user: CurrentUser, db: DB):
    return {"items": [{"id": item.id, "name": item.name, "method": item.method, "training_dataset_id": item.training_dataset_id, "config": item.config, "created_at": item.created_at.isoformat() + "Z"} for item in db.scalars(select(GenerativeModel).where(GenerativeModel.owner_id == user.id).order_by(GenerativeModel.created_at.desc()).limit(100))]}


@router.get("/scenarios/catalog")
def scenario_catalog(user: CurrentUser):
    return {"items": [{"id": name, "name": name.replace("_", " ").title(), "version": 1, "ground_truth": "synthetic simulator labels", "distribution_shift_can_be_legitimate": name == "distribution_shift"} for name in SCENARIOS]}


@router.post("/scenarios/execute", status_code=202)
def execute_scenario(payload: Scenario, request: Request, user: CurrentUser, db: DB):
    return enqueue(db, request, user, "scenario.execute", payload)


@router.post("/models/train", status_code=202)
def train_model(payload: Training, request: Request, user: CurrentUser, db: DB):
    return enqueue(db, request, user, "model.train", payload)


class Comparison(Input):
    model_ids: list[UUID]


@router.post("/models/comparison")
def compare_models(payload: Comparison, user: CurrentUser, db: DB):
    if not 2 <= len(payload.model_ids) <= 5:
        raise APIError(422, "comparison_size", "Select two to five models.")
    if len(set(payload.model_ids)) != len(payload.model_ids):
        raise APIError(422, "distinct_models", "Select different model versions for comparison.")
    results = []
    for model_id in payload.model_ids:
        model = owned(db, MLModel, model_id, user.id)
        run = db.scalar(select(ResearchRun).where(ResearchRun.model_id == model.id, ResearchRun.kind == "model.train"))
        results.append({"model_id": model.id, "name": model.name, "version": model.version, "algorithm": model.algorithm, "result": run.result})
    if len({item["result"]["split_hashes"]["test"] for item in results}) != 1:
        raise APIError(409, "incompatible_evaluations", "These models were evaluated on different held-out rows. Train them using the same dataset and split before comparing.")
    return {"items": results, "shared_test_sha256": results[0]["result"]["split_hashes"]["test"]}


@router.get("/models/{model_id}")
def model_detail(model_id: UUID, user: CurrentUser, db: DB):
    model = owned(db, MLModel, model_id, user.id)
    run = db.scalar(select(ResearchRun).where(ResearchRun.model_id == model.id, ResearchRun.kind == "model.train"))
    return {"id": model.id, "name": model.name, "algorithm": model.algorithm, "version": model.version, "threshold": model.threshold, "status": model.status, "training": run.result, "dataset_id": run.dataset_id}


class ModelState(Input):
    status: Literal["active", "retired"]


@router.patch("/models/{model_id}/status")
def model_state(model_id: UUID, payload: ModelState, user: CurrentUser, db: DB):
    model = owned(db, MLModel, model_id, user.id)
    model.status = payload.status
    db.commit()
    return {"id": model.id, "status": model.status}


@router.post("/predictions/batch", status_code=202)
def predict_batch(payload: BatchPrediction, request: Request, user: CurrentUser, db: DB):
    return enqueue(db, request, user, "predictions.batch", payload)


def prediction_data(item):
    return {"id": item.id, "transaction_id": item.transaction_id, "model_id": item.model_id, "dataset_id": item.dataset_id, "features": item.features, "probability": item.probability, "anomaly_score": item.anomaly_score, "predicted_class": item.predicted_class, "ground_truth": item.ground_truth, "risk": item.risk, "explanation_url": f"/api/v1/predictions/{item.id}/explanation", "created_at": item.created_at.isoformat() + "Z"}


@router.post("/predictions")
def single_prediction(payload: SinglePrediction, request: Request, user: CurrentUser, db: DB):
    from math import isfinite
    model = owned(db, MLModel, payload.model_id, user.id)
    if set(payload.features) != set(FEATURES):
        raise APIError(422, "feature_contract", "Supply exactly the model's canonical feature fields.", {"required": FEATURES})
    try:
        features = {key: float(payload.features[key]) for key in NUMERIC}
        if any(not isfinite(value) or value < 0 or value > 10000000 for value in features.values()):
            raise ValueError()
        features.update({key: str(payload.features[key])[:50] for key in CATEGORICAL})
        if features["hour"] > 23 or features["quantity"] < 1:
            raise ValueError()
    except (ValueError, TypeError):
        raise APIError(422, "feature_values", "Feature values must satisfy nonnegative finite numeric and transaction constraints.")
    runtime = ["pandas", "sklearn"] + (["xgboost"] if model.algorithm == "xgboost" else [])
    delegated = forward_if_needed(request, *runtime, payload=payload.model_dump(mode="json"))
    if delegated is not None:
        return delegated
    import pandas as pd
    bundle = read_bundle(db, request.app.state.settings, model.artifact_id)
    score = float(scores(bundle, pd.DataFrame([features]))[0])
    anomaly = bundle["algorithm"] == "isolation_forest"
    row = Prediction(owner_id=user.id, model_id=model.id, transaction_id=f"SINGLE-{__import__('uuid').uuid4()}", features=features, probability=None if anomaly else score, anomaly_score=score if anomaly else None, predicted_class=int(score >= bundle["threshold"]), ground_truth=None, risk="high" if score >= bundle["threshold"] else "low")
    db.add(row)
    db.commit()
    return prediction_data(row)


@router.get("/predictions")
def prediction_history(user: CurrentUser, db: DB, model_id: UUID | None = None, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0), q: str = Query("", max_length=100)):
    query = select(Prediction).where(Prediction.owner_id == user.id)
    if model_id:
        owned(db, MLModel, model_id, user.id)
        query = query.where(Prediction.model_id == str(model_id))
    if q:
        query = query.where(Prediction.transaction_id.contains(q, autoescape=True))
    return {"items": [prediction_data(item) for item in db.scalars(query.order_by(Prediction.created_at.desc()).offset(offset).limit(limit))]}


@router.get("/predictions/{prediction_id}")
def prediction_detail(prediction_id: UUID, user: CurrentUser, db: DB):
    return prediction_data(owned(db, Prediction, prediction_id, user.id))


@router.post("/analysis", status_code=202)
def analyze(payload: Analysis, request: Request, user: CurrentUser, db: DB):
    if payload.analysis in {"quality", "validation", "patterns", "drift", "risk"} and not payload.dataset_id:
        raise APIError(422, "dataset_required", "Select a dataset.")
    if payload.analysis in {"risk", "performance", "noise", "imbalance", "unseen", "shap", "importance", "permutation"} and not payload.model_id:
        raise APIError(422, "model_required", "Select a fitted detection model.")
    if payload.source == "predictions" and not payload.model_id:
        raise APIError(422, "model_required", "Select a model for predicted pattern analysis.")
    if payload.prediction_id:
        prediction = owned(db, Prediction, payload.prediction_id, user.id)
        if prediction.model_id != str(payload.model_id):
            raise APIError(422, "prediction_model_mismatch", "Select the model used for this saved prediction.")
    return enqueue(db, request, user, f"analysis.{payload.analysis}", payload)


@router.post("/predictions/{prediction_id}/explanation", status_code=202)
def explain_prediction(prediction_id: UUID, request: Request, user: CurrentUser, db: DB):
    prediction = owned(db, Prediction, prediction_id, user.id)
    return enqueue(db, request, user, "analysis.shap", Analysis(dataset_id=prediction.dataset_id, model_id=prediction.model_id, prediction_id=prediction.id, analysis="shap", samples=1))


@router.post("/robustness/runs", status_code=202)
def robustness(payload: Robustness, request: Request, user: CurrentUser, db: DB):
    return enqueue(db, request, user, "robustness.run", payload)


def run_data(item):
    return {"id": item.id, "job_id": item.job_id, "kind": item.kind, "dataset_id": item.dataset_id, "model_id": item.model_id, "config": item.config, "result": item.result, "artifact_id": item.artifact_id, "mlflow_run_id": item.mlflow_run_id, "created_at": item.created_at.isoformat() + "Z"}


@router.get("/runs")
def runs(user: CurrentUser, db: DB, kind: str | None = Query(None, max_length=50), limit: int = Query(30, ge=1, le=100)):
    query = select(ResearchRun).where(ResearchRun.owner_id == user.id)
    if kind:
        query = query.where(ResearchRun.kind == kind)
    return {"items": [run_data(item) for item in db.scalars(query.order_by(ResearchRun.created_at.desc()).limit(limit))]}


@router.get("/runs/{run_id}")
def run_detail(run_id: UUID, user: CurrentUser, db: DB):
    return run_data(owned(db, ResearchRun, run_id, user.id))


@router.get("/jobs/{job_id}/result")
def job_result(job_id: UUID, user: CurrentUser, db: DB):
    owned(db, Job, job_id, user.id)
    run = db.scalar(select(ResearchRun).where(ResearchRun.job_id == str(job_id), ResearchRun.owner_id == user.id))
    if not run:
        raise APIError(404, "result_pending", "Research results have not been published for this job.")
    return run_data(run)


@router.post("/reports", status_code=202)
def report(payload: Report, request: Request, user: CurrentUser, db: DB):
    return enqueue(db, request, user, "report.generate", payload)


@router.get("/reports")
def reports(user: CurrentUser, db: DB):
    return {"items": [run_data(item) for item in db.scalars(select(ResearchRun).where(ResearchRun.owner_id == user.id, ResearchRun.kind == "report.generate").order_by(ResearchRun.created_at.desc()).limit(100))]}

