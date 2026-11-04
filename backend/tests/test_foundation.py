from datetime import timedelta
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.main import create_app
from app.models import Artifact, Job, User, now
from app.services.artifacts import safe_path, write_json
from app.services.jobs import claim_next
from app.workers.runner import recover_stale, run_worker
from conftest import migrate, register


def test_migration_round_trip_and_metadata(settings):
    migrate(settings.database_url)
    application = create_app(settings)
    inspector = inspect(application.state.engine)
    assert {"users", "jobs", "artifacts", "used_refresh_tokens", "datasets", "notifications"} <= set(inspector.get_table_names())
    with TestClient(application) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = settings.database_url
    command.downgrade(config, "base")
    assert "users" not in inspect(application.state.engine).get_table_names()
    command.upgrade(config, "head")
    assert "users" in inspect(application.state.engine).get_table_names()


def test_unmigrated_database_not_ready(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 503


def test_database_foreign_keys(client, app):
    with app.state.sessions() as db:
        db.add(Job(owner_id="missing", kind="system.integrity_check"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_settings_experiments_persistence_and_pagination(client, headers, app):
    assert client.patch("/api/v1/settings", json={"theme": "dark", "job_notifications": False}, headers=headers).status_code == 200
    assert client.get("/api/v1/settings", headers=headers).json()["theme"] == "dark"
    ids = set()
    for n in range(3):
        result = client.post("/api/v1/experiments", json={"name": f"Research {n}", "kind": "robustness", "seed": n}, headers=headers)
        ids.add(result.json()["id"])
        assert result.json()["status"] == "draft"
    first = client.get("/api/v1/experiments?limit=2", headers=headers).json()
    second = client.get("/api/v1/experiments", params={"limit": 2, "cursor": first["next_cursor"]}, headers=headers).json()
    assert {item["id"] for item in first["items"] + second["items"]} == ids
    other_app = create_app(app.state.settings)
    with TestClient(other_app) as restarted:
        assert restarted.get("/api/v1/settings", headers=headers).json()["theme"] == "dark"
    assert client.get("/api/v1/experiments?limit=101", headers=headers).status_code == 422


def test_resource_isolation(client, app, headers):
    experiment = client.post("/api/v1/experiments", json={"name": "Private", "kind": "training"}, headers=headers).json()
    job = client.post("/api/v1/jobs", json={}, headers=headers).json()
    second = TestClient(app)
    other = register(second, "other@example.com")
    other_headers = {"Authorization": "Bearer " + other["access_token"]}
    assert second.get(f"/api/v1/experiments/{experiment['id']}", headers=other_headers).status_code == 404
    for suffix in ("", "/events"):
        assert second.get(f"/api/v1/jobs/{job['job_id']}{suffix}", headers=other_headers).status_code == 404
    assert second.post(f"/api/v1/jobs/{job['job_id']}/cancel", headers=other_headers).status_code == 404
    assert second.get("/api/v1/experiments", headers=other_headers).json()["items"] == []
    assert second.get("/api/v1/search?q=Private", headers=other_headers).json()["items"] == []


def test_admin_role_and_last_admin_protection(client, app, headers, account):
    assert client.get("/api/v1/users", headers=headers).status_code == 403
    with app.state.sessions() as db:
        db.get(User, account["user"]["id"]).role = "administrator"
        db.commit()
    assert client.get("/api/v1/users", headers=headers).status_code == 200
    target = account["user"]["id"]
    assert client.patch(f"/api/v1/users/{target}", json={"active": False}, headers=headers).status_code == 409
    assert client.patch(f"/api/v1/users/{target}", json={"role": "researcher"}, headers=headers).status_code == 409


def test_actual_worker_artifact_sse_replay_and_integrity(client, headers, settings, app, account):
    submitted = client.post("/api/v1/jobs", json={}, headers={**headers, "Idempotency-Key": "integrity-1"})
    assert submitted.status_code == 202
    job_id = submitted.json()["job_id"]
    assert client.post("/api/v1/jobs", json={}, headers={**headers, "Idempotency-Key": "integrity-1"}).json()["job_id"] == job_id
    assert client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()["state"] == "queued"
    run_worker(settings, once=True)
    complete = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
    assert complete["state"] == "succeeded" and complete["progress_percentage"] == 100
    artifact_id = complete["result_artifact_id"]
    download = client.get(f"/api/v1/artifacts/{artifact_id}/download", headers=headers)
    assert download.json()["checked_count"] == 0
    events = client.get(f"/api/v1/jobs/{job_id}/events", headers=headers)
    assert "text/event-stream" in events.headers["content-type"]
    assert '"state": "queued"' in events.text and '"state": "succeeded"' in events.text
    last = int([line[4:] for line in events.text.splitlines() if line.startswith("id: ")][-1])
    replay = client.get(f"/api/v1/jobs/{job_id}/events", headers={**headers, "Last-Event-ID": str(last)})
    assert "event: job" not in replay.text
    with app.state.sessions() as db:
        artifact = db.get(Artifact, artifact_id)
        safe_path(settings.artifact_root, artifact.storage_key).write_text("tampered")
    second = client.post("/api/v1/jobs", json={}, headers=headers).json()["job_id"]
    run_worker(settings, once=True)
    next_artifact = client.get(f"/api/v1/jobs/{second}", headers=headers).json()["result_artifact_id"]
    assert client.get(f"/api/v1/artifacts/{next_artifact}/download", headers=headers).json()["invalid_count"] == 1
    other_client = TestClient(app)
    other = register(other_client, "artifact-other@example.com")
    assert other_client.get(f"/api/v1/artifacts/{artifact_id}/download", headers={"Authorization": "Bearer " + other["access_token"]}).status_code == 404


def test_queued_cancellation_and_stale_recovery(client, headers, app, settings):
    queued = client.post("/api/v1/jobs", json={}, headers=headers).json()["job_id"]
    assert client.post(f"/api/v1/jobs/{queued}/cancel", headers=headers).json()["state"] == "cancelled"
    assert client.post(f"/api/v1/jobs/{queued}/cancel", headers=headers).status_code == 409
    running = client.post("/api/v1/jobs", json={}, headers=headers).json()["job_id"]
    with app.state.sessions() as db:
        assert claim_next(db, "dead-worker") == running
        job = db.get(Job, running)
        job.heartbeat_at = now() - timedelta(seconds=120)
        db.commit()
    recover_stale(app.state.sessions, settings)
    assert client.get(f"/api/v1/jobs/{running}", headers=headers).json()["state"] == "interrupted"


def test_storage_path_constraints(settings):
    with pytest.raises(Exception) as error:
        safe_path(settings.artifact_root, "../../outside.json")
    assert error.value.status_code == 400


def test_protected_endpoints_empty_dashboard_and_capabilities(client, headers):
    for url in ("/dashboard", "/settings", "/jobs", "/datasets", "/models", "/experiments", "/artifacts", "/system/status", "/capabilities"):
        assert client.get("/api/v1" + url).status_code == 401
    dashboard = client.get("/api/v1/dashboard", headers=headers).json()
    assert dashboard["total_transactions"] == 0 and dashboard["fraud_percentage"] is None
    assert client.get("/api/v1/capabilities", headers=headers).json()["generation"]["ctgan"] is True
    assert client.post("/api/v1/jobs", json={"kind": "generate"}, headers=headers).status_code == 422


def test_errors_request_id_body_bound_and_openapi(client, headers):
    response = client.post("/api/v1/auth/login", json={"email": "wrong", "password": "never-echo-this"})
    assert "never-echo-this" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert client.patch("/api/v1/profile", content="x" * 70000, headers={**headers, "Content-Type": "application/json"}).status_code == 413
    schema = client.get("/api/v1/openapi.json")
    assert schema.status_code == 200 and "/api/v1/auth/login" in schema.json()["paths"]
