"""Single-replica hosted API and separate worker sharing one persistent volume.

The supervisor exits if either process exits. The platform may restart the
service; research jobs are never automatically resubmitted.
"""
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

log = logging.getLogger("retail.hosted")


def prepare_environment():
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or os.environ.get("RF_VOLUME_ROOT")
    if not volume or not Path(volume).is_absolute() or not Path(volume).is_dir():
        raise ValueError("A mounted persistent volume is required")
    root = Path(volume).resolve() / "retail-fraud"
    root.mkdir(mode=0o700, exist_ok=True)
    # Railway mounts volumes as root. Prepare only our own directory, then run
    # the API and worker as the image's unprivileged researcher account.
    if hasattr(os, "getuid") and os.getuid() == 0:
        import pwd
        account = pwd.getpwnam("researcher")
        os.chown(root, account.pw_uid, account.pw_gid)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    os.environ.setdefault("RF_ENVIRONMENT", "production")
    os.environ.setdefault("RF_COOKIE_SECURE", "true")
    os.environ["RF_REQUIRE_WORKER_READY"] = "true"
    os.environ["RF_ARTIFACT_ROOT"] = str(root / "artifacts")
    os.environ.setdefault("RF_MLFLOW_TRACKING_URI", f"sqlite:///{(root / 'mlflow.db').as_posix()}")
    database = os.environ.get("RF_DATABASE_URL", "")
    if database.startswith(("postgresql://", "postgres://")):
        os.environ["RF_DATABASE_URL"] = "postgresql+psycopg://" + database.split("://", 1)[1]
    from .core.config import Settings
    settings = Settings(_env_file=None)
    if settings.environment != "production" or not settings.database_url.startswith("postgresql+psycopg://"):
        raise ValueError("Hosted deployment requires production settings and PostgreSQL")
    if not settings.allowed_origins or any(not valid_origin(origin) for origin in settings.allowed_origins):
        raise ValueError("Configure exact HTTPS frontend origins")
    settings.artifact_root.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.TemporaryFile(dir=settings.artifact_root) as stream:
        stream.write(b"startup")
        stream.flush()
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    return settings, port


def valid_origin(origin):
    try:
        parsed = urlsplit(origin)
        return bool(parsed.scheme == "https" and parsed.hostname and parsed.port in (None, 443) and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and parsed.path == "" and "*" not in origin)
    except ValueError:
        return False


def supervise(commands, stop, shutdown_seconds=20):
    children = []
    try:
        for command in commands:
            children.append(subprocess.Popen(command, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
        while not stop.wait(0.25):
            for child in children:
                code = child.poll()
                if code is not None:
                    log.error("hosted_child_exited")
                    return code or 1
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + shutdown_seconds
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def main():
    try:
        settings, port = prepare_environment()
        from .middleware import configure_logging
        configure_logging(settings.log_level)
        from alembic import command
        from alembic.config import Config
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["database_url"] = settings.database_url
        command.upgrade(config, "head")
        bind_host = os.environ.get("RF_BIND_HOST", "0.0.0.0")
        if bind_host not in ("127.0.0.1", "0.0.0.0"):
            raise ValueError("RF_BIND_HOST must be 127.0.0.1 or 0.0.0.0")
        stop = threading.Event()
        for name in (signal.SIGTERM, signal.SIGINT):
            signal.signal(name, lambda *_: stop.set())
        return supervise([
            [sys.executable, "-m", "app.workers.runner"],
            [sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory", "--host", bind_host, "--port", str(port), "--no-access-log", "--no-proxy-headers"],
        ], stop)
    except Exception as error:
        # Configuration and connection exceptions may contain credentials.
        print(f"Hosted startup failed ({type(error).__name__}). Check service configuration, database and volume.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
