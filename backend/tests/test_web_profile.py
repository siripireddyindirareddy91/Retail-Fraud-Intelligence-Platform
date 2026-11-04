from datetime import timedelta
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.models import Artifact, Dataset, Experiment, Job, MLModel, WorkerHeartbeat, now
from app.services import research_runtime
from app.services.artifacts import write_bytes


def seed_resources(app, owner_id):
    # Metadata-only fixtures for availability/ownership checks, not predictions.
    with app.state.sessions() as db:
        artifact = write_bytes(db, app.state.settings.artifact_root, owner_id, "availability fixture", b"fixture", "application/octet-stream", ".parquet")
        dataset = Dataset(owner_id=owner_id, artifact_id=artifact.id, name="Availability fixture", method="statistical", row_count=100, fraud_count=2, config={})
        experiment = Experiment(owner_id=owner_id, name="Availability fixture", kind="training", config={})
        db.add_all([dataset, experiment])
        db.flush()
        model = MLModel(owner_id=owner_id, artifact_id=artifact.id, experiment_id=experiment.id, name="Availability fixture", algorithm="random_forest", version=1, threshold=.5)
        db.add(model)
        db.commit()
        return dataset.id, model.id


def test_thin_api_empty_dashboard_and_metadata_remain_available(client, headers, monkeypatch):
    monkeypatch.setattr(research_runtime, "modules_available", lambda *names: False)
    for path in ("/dashboard", "/analytics/overview", "/datasets", "/models", "/runs", "/scenarios/catalog"):
        assert client.get("/api/v1" + path, headers=headers).status_code == 200


def test_thin_api_rejects_work_without_worker_and_creates_no_job(client, headers, app, monkeypatch):
    monkeypatch.setattr(research_runtime, "modules_available", lambda *names: False)
    response = client.post("/api/v1/datasets/generate", headers=headers, json={"rows": 100})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "research_worker_unavailable"
    assert response.headers["Retry-After"] == "30"
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Job)) == 0


def test_thin_api_checks_fresh_worker_heartbeat(client, headers, app, monkeypatch):
    monkeypatch.setattr(research_runtime, "modules_available", lambda *names: False)
    with app.state.sessions() as db:
        db.add(WorkerHeartbeat(id="availability-test-worker", last_seen=now() - timedelta(hours=1)))
        db.commit()
    assert client.post("/api/v1/datasets/generate", headers=headers, json={"rows": 100}).status_code == 503
    with app.state.sessions() as db:
        db.get(WorkerHeartbeat, "availability-test-worker").last_seen = now()
        db.commit()
    assert client.post("/api/v1/datasets/generate", headers=headers, json={"rows": 100}).status_code == 202


def test_scientific_reads_fail_safely_after_auth_and_ownership(client, headers, app, account, monkeypatch):
    dataset_id, _ = seed_resources(app, account["user"]["id"])
    monkeypatch.setattr(research_runtime, "modules_available", lambda *names: False)
    for suffix in ("preview", "statistics", "download"):
        path = f"/api/v1/datasets/{dataset_id}/{suffix}"
        assert client.get(path).status_code == 401
        response = client.get(path, headers=headers)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "research_service_unavailable"
    assert client.post("/api/v1/streams", headers=headers, json={}).status_code == 503


def test_single_prediction_validates_before_reporting_runtime_unavailable(client, headers, app, account, monkeypatch):
    _, model_id = seed_resources(app, account["user"]["id"])
    from app.research.data import CATEGORICAL, NUMERIC
    features = {key: 1 for key in NUMERIC}
    features.update({key: "test-category" for key in CATEGORICAL})
    monkeypatch.setattr(research_runtime, "modules_available", lambda *names: False)
    response = client.post("/api/v1/predictions", headers=headers, json={"model_id": model_id, "features": features})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "research_service_unavailable"
    assert client.post("/api/v1/predictions", headers=headers, json={"model_id": model_id, "features": {}}).status_code == 422


def test_service_origin_requires_https_and_rejects_embedded_credentials(settings):
    for origin in ("http://example.com", "https://user:password@example.com", "https://example.com/path", "https://example.com?secret=value"):
        values = settings.model_dump()
        values.update(environment="production", cookie_secure=True, research_api_origin=origin)
        with pytest.raises(ValueError):
            Settings(_env_file=None, **values)


def test_unavailable_service_never_echoes_transport_errors(client, headers, app, account, monkeypatch):
    dataset_id, _ = seed_resources(app, account["user"]["id"])
    app.state.settings.research_api_origin = "https://research.example.test"
    real_client = httpx.Client

    def fail(request):
        raise httpx.ConnectError("sensitive transport diagnostic", request=request)

    monkeypatch.setattr(research_runtime.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(fail), **kwargs))
    response = client.get(f"/api/v1/datasets/{dataset_id}/preview", headers=headers)
    assert response.status_code == 503
    assert "sensitive transport diagnostic" not in response.text


def test_research_readiness_checks_upstream_without_local_artifact_writes(client, app, monkeypatch, tmp_path):
    app.state.settings = app.state.settings.model_copy(update={"research_api_origin": "https://research.example.test", "require_worker_ready": True, "artifact_root": tmp_path / "no-local-artifacts"})
    with app.state.sessions() as db:
        db.add(WorkerHeartbeat(id="readiness-test-worker", last_seen=now()))
        db.commit()
    real_client = httpx.Client
    monkeypatch.setattr(research_runtime.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "ready"})), **kwargs))
    assert client.get("/api/v1/health/ready").status_code == 200
    assert not app.state.settings.artifact_root.exists()
    loop = client.get("/api/v1/health/ready", headers={"X-Research-Delegated": "1"})
    assert loop.status_code == 503
    assert loop.json()["reason"] == "research_service_configuration"


def test_vercel_install_command_is_explicit_and_build_scripts_are_uploaded():
    backend = Path(__file__).resolve().parents[1]
    configuration = json.loads((backend / "vercel.json").read_text())
    assert configuration["installCommand"] == "python scripts/install_vercel_api.py"
    assert "scripts/" not in (backend / ".vercelignore").read_text().splitlines()
    assert "scripts/**" in configuration["functions"]["asgi.py"]["excludeFiles"]
