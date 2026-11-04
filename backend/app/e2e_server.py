"""Isolated browser-test API with a separate real worker process.

Not an application entry point. All state and relaxed test limits stay in an
explicitly temporary test workspace; normal server configuration is unchanged.
"""
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
import uvicorn

from .core.config import ROOT, Settings
from .main import create_app


def main():
    api_port = int(os.environ.get("RF_E2E_API_PORT", "8001"))
    frontend_port = int(os.environ.get("RF_E2E_FRONTEND_PORT", "5175"))
    if not (1024 <= api_port <= 65535 and 1024 <= frontend_port <= 65535) or api_port == frontend_port:
        raise ValueError("Browser-test ports must be distinct ports between 1024 and 65535")
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="browser-tests-", dir=runtime) as directory:
        test_root = Path(directory).resolve()
        if runtime.resolve() not in test_root.parents:
            raise RuntimeError("Test workspace must stay inside runtime")
        settings = Settings(_env_file=None, environment="test", jwt_secret=secrets.token_urlsafe(48), database_url=f"sqlite:///{(test_root / 'test.db').as_posix()}", artifact_root=test_root / "artifacts", mlflow_tracking_uri=f"sqlite:///{(test_root / 'mlflow.db').as_posix()}", register_limit=100, login_limit=100, job_limit=100, log_level="WARNING", allowed_origins=[f"http://127.0.0.1:{frontend_port}"])
        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.attributes["database_url"] = settings.database_url
        command.upgrade(config, "head")
        environment = dict(os.environ, RF_ENVIRONMENT="test", RF_DATABASE_URL=settings.database_url, RF_JWT_SECRET=settings.jwt_secret.get_secret_value(), RF_ARTIFACT_ROOT=str(settings.artifact_root), RF_MLFLOW_TRACKING_URI=settings.mlflow_tracking_uri, RF_LOG_LEVEL="WARNING")
        worker = subprocess.Popen([sys.executable, "-m", "app.workers.runner"], env=environment, cwd=ROOT / "backend", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            uvicorn.run(create_app(settings), host="127.0.0.1", port=api_port, access_log=False, log_level="warning")
        finally:
            worker.terminate()
            worker.wait(timeout=15)


if __name__ == "__main__":
    main()
