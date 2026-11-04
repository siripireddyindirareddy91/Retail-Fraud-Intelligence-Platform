import importlib
import secrets
import subprocess
import sys
import tomllib
from pathlib import Path

from alembic import command
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy.engine import Engine

from app.database import Base
from app.main import create_app


@pytest.fixture
def load_entrypoint(monkeypatch, tmp_path):
    monkeypatch.setenv("RF_ENVIRONMENT", "test")
    monkeypatch.setenv("RF_JWT_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("RF_COOKIE_SECURE", "false")
    monkeypatch.setenv("RF_REQUIRE_WORKER_READY", "false")
    monkeypatch.setenv("RF_DATABASE_URL", f"sqlite:///{(tmp_path / 'entrypoint.db').as_posix()}")
    monkeypatch.setenv("RF_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("RF_MLFLOW_TRACKING_URI", f"sqlite:///{(tmp_path / 'tracking.db').as_posix()}")
    loaded = []

    def load():
        sys.modules.pop("asgi", None)
        module = importlib.import_module("asgi")
        loaded.append(module)
        return module

    yield load
    for module in loaded:
        module.app.state.engine.dispose()
    sys.modules.pop("asgi", None)


def test_vercel_configuration_resolves_real_application(load_entrypoint):
    backend = Path(__file__).resolve().parents[1]
    configuration = tomllib.loads((backend / "pyproject.toml").read_text())
    assert configuration["tool"]["vercel"]["entrypoint"] == "asgi:app"
    assert (backend / ".python-version").read_text().strip() == "3.12"
    assert isinstance(load_entrypoint().app, FastAPI)


def test_import_does_not_start_processes_connect_or_migrate(load_entrypoint, monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("ASGI import must not start processes, connect or migrate")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(Engine, "connect", forbidden)
    monkeypatch.setattr(command, "upgrade", forbidden)
    monkeypatch.setattr(Base.metadata, "create_all", forbidden)
    entrypoint = load_entrypoint()
    assert isinstance(entrypoint.app, FastAPI)
    assert not (tmp_path / "entrypoint.db").exists()
    assert not (tmp_path / "artifacts").exists()


def test_entrypoint_preserves_factory_routes_and_http_behavior(load_entrypoint):
    application = load_entrypoint().app
    reference = create_app(application.state.settings)
    try:
        assert application.openapi() == reference.openapi()
        assert [(item.cls, item.args, item.kwargs) for item in application.user_middleware] == [
            (item.cls, item.args, item.kwargs) for item in reference.user_middleware
        ]
        assert set(application.exception_handlers) == set(reference.exception_handlers)
        with TestClient(application) as client:
            response = client.get("/api/v1/health/live")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            assert response.headers.get("X-Request-ID")
            assert client.get("/api/v1/auth/me").status_code == 401
            missing = client.get("/not-a-route")
            assert missing.status_code == 404
            assert "error" in missing.json()
    finally:
        reference.state.engine.dispose()


def test_entrypoint_requires_environment_secret(load_entrypoint, monkeypatch):
    # The developer's root .env must not satisfy serverless configuration.
    monkeypatch.delenv("RF_JWT_SECRET", raising=False)
    with pytest.raises(ValidationError) as failure:
        load_entrypoint()
    assert any(item["loc"] == ("jwt_secret",) for item in failure.value.errors())


def test_entrypoint_requires_secure_cookies_in_production(load_entrypoint, monkeypatch):
    monkeypatch.setenv("RF_ENVIRONMENT", "production")
    monkeypatch.setenv("RF_COOKIE_SECURE", "false")
    with pytest.raises(ValidationError, match="Production requires RF_COOKIE_SECURE"):
        load_entrypoint()
