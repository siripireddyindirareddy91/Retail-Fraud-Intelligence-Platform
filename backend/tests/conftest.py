from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.main import create_app


def migrate(url, revision="head"):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, revision)


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, environment="test", jwt_secret="test-secret-" + "a" * 50, database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", artifact_root=tmp_path / "artifacts", mlflow_tracking_uri=f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}", job_limit=100, poll_seconds=0.1, sse_max_seconds=1, log_level="WARNING")


@pytest.fixture
def app(settings):
    migrate(settings.database_url)
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def register(client, email="researcher@example.com", **extra):
    response = client.post("/api/v1/auth/register", json={"email": email, "display_name": "Researcher", "password": "correct horse battery staple", **extra})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def account(client):
    return register(client)


@pytest.fixture
def headers(account):
    return {"Authorization": "Bearer " + account["access_token"]}
