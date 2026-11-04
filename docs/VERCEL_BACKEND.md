# FastAPI entrypoint on Vercel

Set this backend Vercel project's **Root Directory to `backend`** and use the
FastAPI framework preset. Clear frontend-specific build/output overrides:
there is no npm build or `dist` directory for this Python backend.

`backend/pyproject.toml` explicitly selects `asgi:app`. The top-level variable in
`backend/asgi.py` is a real FastAPI instance created by the existing factory:

```python
from app.core.config import Settings
from app.main import create_app

app = create_app(Settings(_env_file=None))
```

Python is pinned to the locally tested 3.12 series by `backend/.python-version`.
The entrypoint does not import test fixtures, run Alembic, start Uvicorn, or
start the hosted supervisor/worker. The existing factory, routers, authorization,
middleware, exception handlers and container entrypoints remain unchanged.
The backend `.vercelignore` excludes local environments, test files, caches and
private runtime files from CLI source uploads; review the actual deployment
bundle too. Dependency packaging is not reduced by removing research features.

## Environment configuration

This adapter deliberately reads environment variables only, not the developer's
root `.env`. Configure each Vercel environment independently before building.

| Variable | Requirement |
| --- | --- |
| `RF_JWT_SECRET` | Required for import. Supply your own randomly generated secret of at least 32 bytes through provider secrets; never commit it. |
| `RF_ENVIRONMENT` | Set to `production` for hosted use. |
| `RF_COOKIE_SECURE` | Set to `true`; production import fails if false. |
| `RF_DATABASE_URL` | Set a real PostgreSQL SQLAlchemy URI beginning `postgresql+psycopg://`, with the provider's required TLS options. The adapter does not perform the hosted supervisor's URL conversion. |
| `RF_ALLOWED_ORIGINS` | JSON list of exact HTTPS frontend origins. No wildcard or trailing slash. |
| `RF_RESEARCH_API_ORIGIN` | HTTPS origin of the full research backend, with the same database and JWT secret/issuer/audience. Keep unset on that service itself. No scientific operations execute locally in the web-only profile. |
| `RF_ARTIFACT_ROOT` | Explicit durable filesystem path on the research service/worker. The thin API can delegate artifact downloads. `/tmp` is not durable storage. |
| `RF_MLFLOW_TRACKING_URI` | Configure durable tracking on the research worker; the thin API does not import MLflow. |
| `RF_REQUIRE_WORKER_READY` | When true, check the real worker and, if configured, research-service readiness. Without delegation the original local storage check remains. False checks DB/schema only. |

A valid secret is sufficient to instantiate the lazy database engine locally;
that does not prove database connectivity or readiness. Do not leave the default
local SQLite URL in a hosted environment. No credentials are supplied by this fix.

## Limits this entrypoint does not solve

- **Migrations:** run `python -m alembic -c alembic.ini upgrade head` from
  `backend` in a controlled release environment against the intended database.
  Do not run it per request or during ASGI import. Readiness expects revision
  `0003_streams`; an absent/outdated schema returns 503.
- **Artifacts:** datasets, models, reports and MLflow artifacts currently use
  local filesystem paths. PostgreSQL alone does not share those files between
  a Vercel API and an external worker. Durable remote storage requires an
  implemented storage adapter; simply setting an S3/Blob URL as a local path
  will not work. Alternatively the implemented `RF_RESEARCH_API_ORIGIN` boundary
  keeps artifact access on the full service/worker volume. Research routes return
  a safe 503 until their execution dependencies are available.
- **Workers:** `python -m app.workers.runner` must run separately in a suitable
  worker host. Queued research jobs do not execute merely because the API is
  deployed. `python -m app.hosted` remains the separate container deployment
  option and must not be used as a Vercel Function handler. Vercel Daemons are
  another possible worker platform, but their initial release has no persistent
  filesystem; moving there requires integration work.
- **Packages:** Vercel reads the default API dependencies from `pyproject.toml`
  through the explicit web-only installer and frozen `uv.lock`. Research workers
  and full services install `.[research]` or the full `requirements.lock.txt`
  snapshot. All scientific libraries, including CPU XGBoost and Parquet readers,
  are research extras. Detector implementations and route paths are retained;
  the thin API delegates execution or returns a clear 503. See
  VERCEL_BUNDLE_SIZE.md and API_BUNDLE_MEASUREMENT.json for measured components.
  The actual Vercel Function remains unverified.
  Standard Python Functions allow 500 MB uncompressed. Current large-function
  beta supports up to 5 GB when eligible/enabled; it does not provide durable
  disk or solve worker coordination.
- **Sessions:** keep frontend `/api` calls behind a same-origin proxy. The
  current strict refresh cookies and readable CSRF cookie are not a drop-in
  cross-site authentication design. Test secure cookies and exact origins on
  the actual deployment domain.
- **Streams:** test SSE reconnect/replay and proxy/function timeouts on staging.
  A successful import is not proof of long-lived cloud streaming behavior.

The existing Vercel-frontend/container-backend profile in DEPLOYMENT_GUIDE.md
preserves the current shared-volume architecture with fewer changes. This
adapter fixes discovery and enables HTTP startup testing; it does not establish
that a full Vercel-only deployment is ready.

## Verify, then release

From `backend`, after setting real deployment environment variables without
printing them:

```powershell
.venv/Scripts/python.exe -c "from fastapi import FastAPI; from asgi import app; assert isinstance(app, FastAPI); print('ASGI import OK')"
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m alembic -c alembic.ini check
```

Tests generate isolated temporary configuration and do not need production
credentials. Do not use `tests/conftest.py` as an entrypoint. After any authorized
deployment, check `/api/v1/health/live`, `/api/v1/openapi.json`, authentication,
and `/api/v1/health/ready`. Only claim full research readiness after testing the
real database, storage and worker together on an isolated staging profile.

Local verification on 4 November 2026: standalone import passed with 55 API
paths; the full backend suite passed 66 tests with one live-PostgreSQL test
skipped. Alembic and dependency checks passed. No Vercel cloud deployment or
Linux bundle build was performed.

Official references: [FastAPI entrypoints](https://vercel.com/docs/frameworks/backend/fastapi),
[Python configuration](https://vercel.com/docs/functions/runtimes/python),
[Function limits](https://vercel.com/docs/functions/limitations),
and [Daemons storage](https://vercel.com/daemons).
