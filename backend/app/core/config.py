from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_REVISION = "0003_streams"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_prefix="RF_", extra="ignore", hide_input_in_errors=True)

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = f"sqlite:///{(ROOT / 'runtime' / 'platform.db').as_posix()}"
    jwt_secret: SecretStr
    jwt_issuer: str = "retail-fraud-intelligence"
    jwt_audience: str = "retail-fraud-workspace"
    access_minutes: int = Field(default=15, ge=1, le=60)
    refresh_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool = False
    require_worker_ready: bool = False
    allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://localhost:5173", "http://localhost:5174"]
    artifact_root: Path = ROOT / "runtime" / "artifacts"
    log_level: str = "INFO"
    login_limit: int = Field(default=20, ge=1)
    register_limit: int = Field(default=10, ge=1)
    job_limit: int = Field(default=10, ge=1)
    stale_seconds: int = Field(default=60, ge=10)
    poll_seconds: float = Field(default=1, ge=0.1, le=30)
    sse_max_seconds: int = Field(default=300, ge=1, le=900)
    max_json_bytes: int = Field(default=65536, ge=1024, le=1048576)
    mlflow_tracking_uri: str = f"sqlite:///{(ROOT / 'runtime' / 'mlflow.db').as_posix()}"
    research_api_origin: str | None = None

    @model_validator(mode="after")
    def secure_configuration(self):
        secret = self.jwt_secret.get_secret_value()
        if len(secret.encode()) < 32 or "replace" in secret.lower():
            raise ValueError("RF_JWT_SECRET must be a randomly generated secret of at least 32 bytes")
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("Production requires RF_COOKIE_SECURE=true and HTTPS")
        if not self.database_url.startswith(("sqlite:///", "postgresql+psycopg://")):
            raise ValueError("Use sqlite:/// or postgresql+psycopg://")
        if self.research_api_origin:
            from urllib.parse import urlsplit
            origin = urlsplit(self.research_api_origin)
            test_loopback = self.environment == "test" and origin.scheme == "http" and origin.hostname in ("localhost", "127.0.0.1")
            if (origin.scheme != "https" and not test_loopback) or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ("", "/"):
                raise ValueError("RF_RESEARCH_API_ORIGIN must be an HTTPS origin without credentials, path or query")
            self.research_api_origin = self.research_api_origin.rstrip("/")
        return self

