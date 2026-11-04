from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update

from .auth import user_data
from .deps import Admin, CurrentUser, DB, owned
from ..core.errors import APIError
from ..models import Artifact, AuditEvent, AuthSession, Dataset, Experiment, Job, MLModel, Notification, Prediction, StreamEvent, StreamSession, User, UserSettings, now
from ..schemas import ExperimentCreate, NotificationUpdate, ProfileUpdate, SettingsUpdate, UserUpdate
from ..services.artifacts import safe_path

router = APIRouter(tags=["Workspace"])


def page(db, query, model, limit, cursor, serialize):
    if cursor:
        query = query.where(model.id > str(cursor))
    rows = list(db.scalars(query.order_by(model.id).limit(limit + 1)))
    return {"items": [serialize(row) for row in rows[:limit]], "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def artifact_data(item):
    return {"id": item.id, "name": item.name, "content_type": item.content_type, "size_bytes": item.size_bytes, "sha256": item.sha256, "created_at": item.created_at.isoformat() + "Z"}


def settings_data(item):
    return {"theme": item.theme, "methodology_guidance": item.methodology_guidance, "job_notifications": item.job_notifications}


@router.get("/settings")
def get_settings(user: CurrentUser, db: DB):
    return settings_data(db.get(UserSettings, user.id))


@router.patch("/settings")
def set_settings(payload: SettingsUpdate, user: CurrentUser, db: DB):
    item = db.get(UserSettings, user.id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    db.commit()
    return settings_data(item)


@router.patch("/profile")
def set_profile(payload: ProfileUpdate, user: CurrentUser, db: DB):
    user.display_name = payload.display_name
    db.commit()
    return user_data(user)


@router.get("/users")
def list_users(user: Admin, db: DB, limit: int = Query(20, ge=1, le=100), cursor: UUID | None = None):
    return page(db, select(User), User, limit, cursor, user_data)


@router.patch("/users/{user_id}")
def change_user(user_id: UUID, payload: UserUpdate, actor: Admin, db: DB):
    # A common write lock serializes competing admin changes on both databases.
    db.execute(update(User).where(User.role == "administrator").values(active=User.active))
    db.refresh(actor)
    if not actor.active or actor.role != "administrator":
        raise APIError(403, "administrator_required", "Administrator access is required.")
    user = db.get(User, str(user_id))
    if not user:
        raise APIError(404, "not_found", "The user was not found.")
    if user.role == "administrator" and user.active and (payload.role == "researcher" or payload.active is False):
        count = db.scalar(select(func.count()).select_from(User).where(User.role == "administrator", User.active.is_(True)))
        if count <= 1:
            raise APIError(409, "last_administrator", "The last active administrator cannot be removed.")
    for name, value in payload.model_dump(exclude_none=True).items():
        setattr(user, name, value)
    if payload.active is False:
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now()))
    db.add(AuditEvent(actor_id=actor.id, action="user.update", resource_id=user.id, details=payload.model_dump(exclude_none=True)))
    db.commit()
    return user_data(user)


@router.get("/artifacts")
def artifacts(user: CurrentUser, db: DB, limit: int = Query(20, ge=1, le=100), cursor: UUID | None = None):
    return page(db, select(Artifact).where(Artifact.owner_id == user.id), Artifact, limit, cursor, artifact_data)


@router.get("/artifacts/{artifact_id}/download")
def download(artifact_id: UUID, request: Request, user: CurrentUser, db: DB):
    item = owned(db, Artifact, artifact_id, user.id)
    path = safe_path(request.app.state.settings.artifact_root, item.storage_key)
    if not path.is_file():
        raise APIError(410, "artifact_missing", "The artifact file is missing. Run an integrity check.")
    return FileResponse(path, media_type=item.content_type, filename=item.name, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/datasets")
def datasets(user: CurrentUser, db: DB, limit: int = Query(20, ge=1, le=100), cursor: UUID | None = None):
    return page(db, select(Dataset).where(Dataset.owner_id == user.id), Dataset, limit, cursor, lambda row: {"id": row.id, "name": row.name, "method": row.method, "row_count": row.row_count, "fraud_count": row.fraud_count, "status": row.status, "config": row.config, "created_at": row.created_at.isoformat() + "Z"})


@router.get("/models")
def models(user: CurrentUser, db: DB, limit: int = Query(20, ge=1, le=100), cursor: UUID | None = None):
    return page(db, select(MLModel).where(MLModel.owner_id == user.id), MLModel, limit, cursor, lambda row: {"id": row.id, "name": row.name, "algorithm": row.algorithm, "version": row.version, "status": row.status})


def experiment_data(row):
    return {"id": row.id, "name": row.name, "kind": row.kind, "config": row.config, "status": row.status, "created_at": row.created_at.isoformat() + "Z"}


@router.post("/experiments", status_code=201)
def create_experiment(payload: ExperimentCreate, user: CurrentUser, db: DB):
    item = Experiment(owner_id=user.id, name=payload.name, kind=payload.kind, config={"seed": payload.seed}, status="draft")
    db.add(item)
    db.flush()
    db.add(AuditEvent(actor_id=user.id, action="experiment.create", resource_id=item.id))
    db.commit()
    return experiment_data(item)


@router.get("/experiments")
def experiments(user: CurrentUser, db: DB, limit: int = Query(20, ge=1, le=100), cursor: UUID | None = None):
    return page(db, select(Experiment).where(Experiment.owner_id == user.id), Experiment, limit, cursor, experiment_data)


@router.get("/experiments/{experiment_id}")
def experiment(experiment_id: UUID, user: CurrentUser, db: DB):
    return experiment_data(owned(db, Experiment, experiment_id, user.id))


@router.get("/notifications")
def notifications(user: CurrentUser, db: DB, limit: int = Query(20, ge=1, le=100), cursor: UUID | None = None):
    return page(db, select(Notification).where(Notification.user_id == user.id), Notification, limit, cursor, lambda row: {"id": row.id, "message": row.message, "severity": row.severity, "job_id": row.job_id, "read": row.read_at is not None, "created_at": row.created_at.isoformat() + "Z"})


@router.patch("/notifications/{notification_id}")
def mark_notification(notification_id: UUID, payload: NotificationUpdate, user: CurrentUser, db: DB):
    item = owned(db, Notification, notification_id, user.id, "user_id")
    item.read_at = now()
    db.commit()
    return {"id": item.id, "read": True}


@router.get("/dashboard")
def dashboard(user: CurrentUser, db: DB):
    total, fraud = db.execute(select(func.coalesce(func.sum(Dataset.row_count), 0), func.coalesce(func.sum(Dataset.fraud_count), 0)).where(Dataset.owner_id == user.id, Dataset.status == "completed")).one()
    stream_total, stream_fraud = db.execute(select(func.count(StreamEvent.id), func.coalesce(func.sum(StreamEvent.payload["ground_truth"].as_integer()), 0)).join(StreamSession, StreamEvent.stream_id == StreamSession.id).where(StreamSession.owner_id == user.id)).one()
    total, fraud = total + stream_total, fraud + stream_fraud
    count = lambda model, *conditions: db.scalar(select(func.count()).select_from(model).where(model.owner_id == user.id, *conditions))
    return {"total_transactions": total, "fraudulent_transactions": fraud, "legitimate_transactions": total - fraud, "fraud_percentage": fraud / total * 100 if total else None, "active_models": count(MLModel, MLModel.status == "active"), "registered_models": count(MLModel, MLModel.status != "retired"), "completed_experiments": count(Experiment, Experiment.status == "completed"), "jobs": {state: count(Job, Job.state == state) for state in ("queued", "running", "succeeded", "failed", "interrupted", "cancelled")}, "recent_experiments": [experiment_data(item) for item in db.scalars(select(Experiment).where(Experiment.owner_id == user.id).order_by(Experiment.created_at.desc()).limit(5))]}


@router.get("/search")
def search(user: CurrentUser, db: DB, q: str = Query(min_length=1, max_length=100)):
    # contains(autoescape=True) keeps SQL wildcard characters literal.
    result = []
    for model, kind in ((Dataset, "dataset"), (Experiment, "experiment"), (MLModel, "model")):
        for item in db.scalars(select(model).where(model.owner_id == user.id, model.name.contains(q, autoescape=True)).limit(10)):
            result.append({"id": item.id, "name": item.name, "type": kind})
    for item in db.scalars(select(Prediction).where(Prediction.owner_id == user.id, Prediction.transaction_id.contains(q, autoescape=True)).limit(10)):
        result.append({"id": item.id, "name": item.transaction_id, "type": "transaction"})
    return {"items": result}

