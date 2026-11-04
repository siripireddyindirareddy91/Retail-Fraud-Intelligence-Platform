from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.models import Job
from app.services.jobs import claim_next
from app.workers.runner import checkpoint, execute


def test_postgres_migration_sql_compiles():
    # Compilation verifies PostgreSQL DDL portability, not a live database run.
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
    config.attributes["database_url"] = "postgresql+psycopg://test:test@localhost/test"
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE users" in sql and "CREATE TABLE jobs" in sql
    assert "FOREIGN KEY" in sql and "0001_foundation" in sql


def test_running_cancellation_prevents_completion(client, headers, app, settings):
    job_id = client.post("/api/v1/jobs", json={}, headers=headers).json()["job_id"]
    with app.state.sessions() as db:
        assert claim_next(db, "test-worker") == job_id
    assert client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers).json()["cancel_requested"]
    execute(app.state.sessions, settings, job_id, "test-worker")
    result = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
    assert result["state"] == "cancelled" and result["result_artifact_id"] is None


def test_unsupported_internal_job_fails_without_fake_completion(client, headers, app, settings):
    job_id = client.post("/api/v1/jobs", json={}, headers=headers).json()["job_id"]
    with app.state.sessions() as db:
        job = db.get(Job, job_id)
        job.kind = "unsupported.engine"
        db.commit()
        assert claim_next(db, "test-worker") == job_id
    execute(app.state.sessions, settings, job_id, "test-worker")
    result = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
    assert result["state"] == "failed"
    assert result["progress_percentage"] is None
    assert result["error"]["code"] == "execution_failed"


def test_password_whitespace_is_preserved(client):
    payload = {"email": "whitespace@example.com", "display_name": "Whitespace", "password": "  deliberate password  "}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"].strip()}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).status_code == 200
