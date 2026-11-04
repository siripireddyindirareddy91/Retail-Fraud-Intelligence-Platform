from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from .deps import CurrentUser, DB
from ..core.config import SCHEMA_REVISION
from ..models import Job, WorkerHeartbeat, now

router = APIRouter(tags=["System"])


def research_runtime_status():
    import importlib.util
    return "installed" if all(importlib.util.find_spec(name) is not None for name in ("sdv", "torch", "shap", "mlflow", "pyarrow")) else "external_worker_required"


@router.get("/health/live")
def live():
    return {"status": "ok", "service": "retail-fraud-api"}


@router.get("/health/ready")
def ready(request: Request):
    try:
        with request.app.state.engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        if revision != SCHEMA_REVISION:
            return JSONResponse({"status": "not_ready", "reason": "migration_required"}, status_code=503)
        settings = request.app.state.settings
        if settings.require_worker_ready:
            with request.app.state.sessions() as db:
                worker = db.scalar(select(WorkerHeartbeat.id).where(WorkerHeartbeat.last_seen >= now() - timedelta(seconds=settings.stale_seconds)).limit(1))
            if not worker:
                return JSONResponse({"status": "not_ready", "reason": "worker_unavailable"}, status_code=503)
            try:
                import tempfile
                with tempfile.TemporaryFile(dir=settings.artifact_root) as stream:
                    stream.write(b"readiness")
                    stream.flush()
            except OSError:
                return JSONResponse({"status": "not_ready", "reason": "storage_unavailable"}, status_code=503)
        return {"status": "ready", "database": "connected", "schema_revision": revision}
    except SQLAlchemyError:
        return JSONResponse({"status": "not_ready", "reason": "database_or_migration_unavailable"}, status_code=503)


@router.get("/capabilities")
def capabilities(user: CurrentUser):
    import importlib.util
    available = lambda name: importlib.util.find_spec(name) is not None
    return {"authentication": True, "persistence": True, "persistent_jobs": ["system.integrity_check", "dataset.generate", "generative.train", "scenario.execute", "model.train", "predictions.batch", "robustness.run", "analysis.*", "report.generate"], "job_events_sse": True, "generation": {"rule_based": available("numpy"), "statistical": available("scipy"), "ctgan": available("sdv") and available("torch"), "tvae": available("sdv") and available("torch")}, "model_training": available("sklearn"), "robustness": available("sklearn"), "shap": available("shap"), "transaction_stream": True, "research_engine_status": research_runtime_status(), "availability_scope": "api_process", "research_execution": "separate_worker"}


@router.get("/system/status")
def status(request: Request, user: CurrentUser, db: DB):
    settings = request.app.state.settings
    count = db.scalar(select(func.count()).select_from(WorkerHeartbeat).where(WorkerHeartbeat.last_seen >= now() - timedelta(seconds=settings.stale_seconds)))
    queue = db.scalar(select(func.count()).select_from(Job).where(Job.owner_id == user.id, Job.state == "queued"))
    storage_ok = False
    try:
        root = settings.artifact_root
        root.mkdir(parents=True, exist_ok=True)
        import tempfile
        with tempfile.TemporaryFile(dir=root) as stream:
            stream.write(b"readiness")
            stream.flush()
        storage_ok = True
    except OSError:
        pass
    return {"database": {"status": "connected", "dialect": db.bind.dialect.name}, "worker": {"status": "available" if count else "unavailable", "active_workers": count}, "storage": {"status": "writable" if storage_ok else "unavailable"}, "queue": {"owned_queued_jobs": queue}, "mlflow": {"status": "configured", "tracking": "runs record actual tracking success or failure"}, "engines": {"status": research_runtime_status(), "execution": "separate worker; runtime availability above describes the API process"}}
