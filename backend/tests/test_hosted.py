from datetime import timedelta
import sys
import threading
import os

import pytest

from app.hosted import prepare_environment, supervise, valid_origin
from app.models import WorkerHeartbeat, now


@pytest.mark.parametrize("origin", ["http://app.example.com", "https://*.vercel.app", "https://app.example.com/", "https://app.example.com/path", "https://user:secret@app.example.com", "https://app.example.com?x=1", "https://app.example.com:123", "https://app.example.com#fragment"])
def test_hosted_rejects_inexact_or_insecure_origins(origin):
    assert not valid_origin(origin)


def test_hosted_accepts_exact_https_origin():
    assert valid_origin("https://retail-research.vercel.app")


def test_hosted_requires_a_persistent_volume(monkeypatch):
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    monkeypatch.delenv("RF_VOLUME_ROOT", raising=False)
    with pytest.raises(ValueError, match="persistent volume"):
        prepare_environment()


@pytest.mark.skipif(hasattr(os, "getuid") and os.getuid() == 0, reason="This check must not drop the test runner's root privileges")
def test_hosted_defaults_keep_state_on_volume_and_use_psycopg(tmp_path, monkeypatch):
    # The launcher sets derived variables itself; keep those mutations local to
    # this test as well as variables explicitly changed with monkeypatch.
    monkeypatch.setattr(os, "environ", os.environ.copy())
    for name in ("RAILWAY_VOLUME_MOUNT_PATH", "RF_ARTIFACT_ROOT", "RF_MLFLOW_TRACKING_URI", "RF_REQUIRE_WORKER_READY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RF_VOLUME_ROOT", str(tmp_path))
    monkeypatch.setenv("RF_ENVIRONMENT", "production")
    monkeypatch.setenv("RF_COOKIE_SECURE", "true")
    monkeypatch.setenv("RF_JWT_SECRET", "test-hosted-configuration-" + "a" * 48)
    monkeypatch.setenv("RF_DATABASE_URL", "postgresql://test:test@localhost/disposable")
    monkeypatch.setenv("RF_ALLOWED_ORIGINS", '["https://retail-research.vercel.app"]')
    monkeypatch.setenv("PORT", "8123")
    settings, port = prepare_environment()
    assert port == 8123 and settings.require_worker_ready and settings.cookie_secure
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.artifact_root == tmp_path / "retail-fraud" / "artifacts"
    assert str(tmp_path).replace("\\", "/") in settings.mlflow_tracking_uri
    monkeypatch.setenv("RF_DATABASE_URL", "sqlite:///disallowed.db")
    with pytest.raises(ValueError, match="PostgreSQL"):
        prepare_environment()


def test_deployment_readiness_requires_live_worker_and_storage(client, app, settings):
    settings.require_worker_ready = True
    settings.artifact_root.mkdir()
    assert client.get("/api/v1/health/ready").json()["reason"] == "worker_unavailable"
    with app.state.sessions() as db:
        db.add(WorkerHeartbeat(id="hosted-worker", last_seen=now()))
        db.commit()
    assert client.get("/api/v1/health/ready").status_code == 200
    settings.artifact_root = settings.artifact_root / "missing"
    assert client.get("/api/v1/health/ready").json()["reason"] == "storage_unavailable"
    with app.state.sessions() as db:
        db.get(WorkerHeartbeat, "hosted-worker").last_seen = now() - timedelta(seconds=settings.stale_seconds + 1)
        db.commit()
    assert client.get("/api/v1/health/ready").json()["reason"] == "worker_unavailable"


def test_supervisor_stops_sibling_when_a_process_fails(tmp_path):
    # Real subprocesses: a failed worker cannot leave an apparently healthy API.
    marker = tmp_path / "should-not-survive.txt"
    sibling = "import time; from pathlib import Path; time.sleep(3); Path({!r}).write_text('alive')".format(str(marker))
    assert supervise([[sys.executable, "-c", "raise SystemExit(7)"], [sys.executable, "-c", sibling]], threading.Event()) == 7
    assert not marker.exists()


def test_supervisor_shutdown_does_not_launch_replacements():
    stop = threading.Event()
    stop.set()
    assert supervise([[sys.executable, "-c", "import time; time.sleep(30)"]], stop) == 0
