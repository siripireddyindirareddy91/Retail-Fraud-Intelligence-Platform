"""Opt-in live PostgreSQL check; uses a newly created disposable database only."""
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.main import create_app
from app.services.jobs import claim_next
from app.workers.runner import run_worker
from conftest import register


@pytest.mark.skipif(not os.environ.get("RF_TEST_POSTGRES_URL"), reason="RF_TEST_POSTGRES_URL not set; live PostgreSQL unavailable")
def test_live_postgres_migrations_queue_worker_and_ownership(tmp_path):
    url = make_url(os.environ["RF_TEST_POSTGRES_URL"])
    if url.drivername != "postgresql+psycopg":
        pytest.fail("RF_TEST_POSTGRES_URL must use postgresql+psycopg")
    name = "rf_verify_" + uuid4().hex
    maintenance = create_engine(url, isolation_level="AUTOCOMMIT")
    application = None
    created = False
    try:
        with maintenance.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        settings = Settings(_env_file=None, environment="test", jwt_secret=uuid4().hex + uuid4().hex, database_url=url.set(database=name).render_as_string(hide_password=False), artifact_root=tmp_path / "artifacts", mlflow_tracking_uri=f"sqlite:///{(tmp_path / 'tracking.db').as_posix()}", sse_max_seconds=1, log_level="WARNING")
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["database_url"] = settings.database_url
        command.upgrade(config, "head")
        command.check(config)
        application = create_app(settings)
        with TestClient(application) as client:
            account = register(client)
            headers = {"Authorization": "Bearer " + account["access_token"]}
            assert client.get("/api/v1/health/ready").status_code == 200
            first = client.post("/api/v1/jobs", json={}, headers=headers).json()["job_id"]
            second = client.post("/api/v1/jobs", json={}, headers=headers).json()["job_id"]
            # A locked queue row must be skipped by a concurrent claimant.
            with application.state.sessions() as locking, application.state.sessions() as other:
                locking.execute(text("SELECT id FROM jobs WHERE id=:id FOR UPDATE"), {"id": first})
                assert claim_next(other, "parallel-worker") == second
                locking.rollback()
            run_worker(settings, once=True)
            assert client.get(f"/api/v1/jobs/{first}", headers=headers).json()["state"] == "succeeded"
            with TestClient(application) as stranger:
                other = register(stranger, "postgres-other@example.com")
                assert stranger.get(f"/api/v1/jobs/{first}", headers={"Authorization": "Bearer " + other["access_token"]}).status_code == 404
        application.state.engine.dispose()
        command.downgrade(config, "base")
        assert "users" not in inspect(application.state.engine).get_table_names()
        application.state.engine.dispose()
        command.upgrade(config, "head")
        command.check(config)
    finally:
        if application:
            application.state.engine.dispose()
        if created:
            # Only the unique database created by this check is removed.
            with maintenance.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        maintenance.dispose()
