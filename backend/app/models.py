from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def now():
    # UTC without tzinfo provides identical comparisons across SQLite/PostgreSQL.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def uid():
    return str(uuid4())


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="researcher")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("role IN ('researcher','administrator')", name="ck_user_role"),)


class AuthSession(Identity, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)


class UsedRefreshToken(Base):
    __tablename__ = "used_refresh_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id"), index=True)


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    theme: Mapped[str] = mapped_column(String(10), default="light")
    methodology_guidance: Mapped[bool] = mapped_column(Boolean, default=True)
    job_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    __table_args__ = (CheckConstraint("theme IN ('light','dark')", name="ck_settings_theme"),)


class Artifact(Identity, Base):
    __tablename__ = "artifacts"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (Index("ix_artifact_owner_created", "owner_id", "created_at"), CheckConstraint("size_bytes >= 0", name="ck_artifact_size"))


class Dataset(Identity, Base):
    __tablename__ = "datasets"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    method: Mapped[str] = mapped_column(String(30))
    row_count: Mapped[int] = mapped_column(Integer)
    fraud_count: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    __table_args__ = (Index("ix_dataset_owner_created", "owner_id", "created_at"), CheckConstraint("fraud_count >= 0 AND row_count >= fraud_count", name="ck_dataset_counts"))


class Experiment(Identity, Base):
    __tablename__ = "experiments"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    __table_args__ = (Index("ix_experiment_owner_created", "owner_id", "created_at"),)


class MLModel(Identity, Base):
    __tablename__ = "ml_models"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"))
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    name: Mapped[str] = mapped_column(String(120))
    algorithm: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer)
    threshold: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="registered")
    __table_args__ = (UniqueConstraint("owner_id", "name", "version", name="uq_model_version"), CheckConstraint("threshold >= 0 AND threshold <= 1", name="ck_model_threshold"))


class Job(Identity, Base):
    __tablename__ = "jobs"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(60))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(20), default="queued")
    stage: Mapped[str] = mapped_column(String(100), default="Queued")
    completed_units: Mapped[int] = mapped_column(Integer, default=0)
    total_units: Mapped[int | None] = mapped_column(Integer)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    worker_id: Mapped[str | None] = mapped_column(String(36))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[dict | None] = mapped_column(JSON)
    result_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (Index("ix_job_queue", "state", "created_at"), Index("ix_job_owner_created", "owner_id", "created_at"), UniqueConstraint("owner_id", "idempotency_key", name="uq_job_idempotency"), CheckConstraint("state IN ('queued','running','succeeded','failed','cancelled','interrupted')", name="ck_job_state"), CheckConstraint("completed_units >= 0 AND (total_units IS NULL OR total_units >= completed_units)", name="ck_job_units"))


class JobEvent(Base):
    __tablename__ = "job_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    state: Mapped[str] = mapped_column(String(20))
    stage: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (Index("ix_job_events_cursor", "job_id", "id"),)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now)


class Notification(Identity, Base):
    __tablename__ = "notifications"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(String(240))
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (Index("ix_notification_user_read", "user_id", "read_at"),)


class AuditEvent(Identity, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[str | None] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class ResearchRun(Identity, Base):
    __tablename__ = "research_runs"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id"))
    model_id: Mapped[str | None] = mapped_column(ForeignKey("ml_models.id"))
    kind: Mapped[str] = mapped_column(String(50), index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id"))
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64))


class GenerativeModel(Identity, Base):
    __tablename__ = "generative_models"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    training_dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"))
    name: Mapped[str] = mapped_column(String(120))
    method: Mapped[str] = mapped_column(String(20))
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class Prediction(Identity, Base):
    __tablename__ = "predictions"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("ml_models.id"), index=True)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id"))
    transaction_id: Mapped[str] = mapped_column(String(100), index=True)
    features: Mapped[dict] = mapped_column(JSON)
    probability: Mapped[float | None] = mapped_column(Float)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    predicted_class: Mapped[int] = mapped_column(Integer)
    ground_truth: Mapped[int | None] = mapped_column(Integer)
    risk: Mapped[str] = mapped_column(String(10))


class StreamSession(Identity, Base):
    __tablename__ = "stream_sessions"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    model_id: Mapped[str | None] = mapped_column(ForeignKey("ml_models.id"))
    state: Mapped[str] = mapped_column(String(20), default="running")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class StreamEvent(Base):
    __tablename__ = "stream_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("stream_sessions.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
