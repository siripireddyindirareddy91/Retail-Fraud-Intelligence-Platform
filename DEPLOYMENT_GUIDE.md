# Deployment and operations

For the separate backend Vercel project and `FASTAPI_ENTRYPOINT_NOT_FOUND`, see
[docs/VERCEL_BACKEND.md](docs/VERCEL_BACKEND.md). Its tested ASGI adapter exposes
the existing factory application without starting the container supervisor or
worker. Discovery success alone does not provide durable storage or job execution.

For the 5.9 GB Function bundle error, see [docs/VERCEL_BUNDLE_SIZE.md](docs/VERCEL_BUNDLE_SIZE.md).
Vercel uses the default API dependency profile and `uv.lock`; separate research
workers must install the research extra or the complete worker snapshot. Do not
install the full worker snapshot in the Vercel API build.

## Vercel frontend and Railway backend

This hosting profile is prepared in source. It is not a claim that a cloud deployment has passed verification. The frontend stays on Vercel; a single Railway application service runs the API and a separate worker process against PostgreSQL and one shared persistent volume. Keep this service at one replica: Railway volumes are not a shared filesystem across independently deployed services. Do not split API and worker onto unrelated local disks.

1. Connect the Vercel and Railway accounts. Create a Railway project with PostgreSQL and an application service uploaded from the repository root. `railway.json` selects `backend/Dockerfile` and `python -m app.hosted`. The checkout does not currently contain Git metadata; deployment may use a CLI source upload rather than a Git import. Never upload `.env`, `runtime`, `.venv`, datasets, model files or account data.
2. Attach a persistent volume to the application at `/data`. Set `RAILWAY_RUN_UID=0` so the launcher can prepare `/data/retail-fraud`. It immediately switches to the image's unprivileged `researcher` account before migrations and before starting either application process. Keep serverless/sleeping mode disabled for the queue worker.
3. Configure `RF_DATABASE_URL` using the private PostgreSQL `DATABASE_URL` reference. The hosted launcher converts `postgresql://` to the psycopg SQLAlchemy driver. Generate a fresh production `RF_JWT_SECRET` with at least 32 random bytes; never reuse the local secret. Set `RF_ALLOWED_ORIGINS` to a JSON list of exact HTTPS Vercel frontend origins (no wildcard or trailing slash). The final Vercel project domain can be reserved before its first deployment. `RF_ENVIRONMENT=production` and `RF_COOKIE_SECURE=true` are the hosted defaults and are enforced. Put secrets in provider variables only.
4. The launcher runs Alembic upgrade before spawning the API and worker. Artifacts and private local MLflow tracking are stored under the mounted volume; MLflow has no public web endpoint in this profile. The readiness endpoint requires the expected schema, a recent worker heartbeat and an actual successful storage write. If either child exits, the supervisor stops its sibling and exits. Container restarts do not resubmit research jobs; stale in-flight jobs become interrupted.
5. Give the Railway service an HTTPS domain. After its readiness check passes, run from the project root:

   ```powershell
   node frontend/scripts/prepare-vercel.mjs https://YOUR-BACKEND.up.railway.app
   ```

   This checks the real backend and writes the ignored `frontend/vercel.json` with its origin. It configures an uncached `/api/*` reverse proxy before the SPA fallback. No backend URL is invented or bundled into UI code. The generated file must be present in the Vercel source upload. Set the Vercel project root to `frontend`, build command to `npm run build`, output to `dist`, and use Node 24. Deploy through the connected account or authenticated Vercel CLI.
6. Verify readiness through the Vercel domain, direct links to all 32 routes, secure refresh/CSRF cookies, session rotation, downloads and SSE reconnection. Use a separate staging API/database/volume/worker for browser acceptance tests; never point the browser test runner at the production user's database. Run the full real generation → training → predictions → explanations → robustness → report workflow on that isolated staging profile before calling the hosted workflow verified.
7. Enable PostgreSQL backups and volume backups, record a restore procedure, and configure external uptime checks for `/api/v1/health/ready`. Railway's deployment health check is not continuous monitoring. Provision account recovery/verification if the service is intended for wider public use. Keep admission limited to the intended research users until those product capabilities are available.

Official platform references: [Vercel external rewrites](https://vercel.com/docs/routing/rewrites), [Railway configuration](https://docs.railway.com/config-as-code/reference), [Railway volume availability and permissions](https://docs.railway.com/volumes), and [Railway health checks](https://docs.railway.com/deployments/healthchecks).

## Verified local website

The verified runtime is Python 3.12 + Node 24 on Windows, using SQLite, a separate bounded worker and local immutable artifacts. After installing dependencies as documented in INSTALLATION_GUIDE.md:

```powershell
./scripts/start-local.ps1
```

The script runs migrations, starts hidden API/worker/frontend processes and records only its own process IDs under ignored `runtime/local-services.json`. Open http://127.0.0.1:5174/dashboard. Logs are in `runtime/`. Stop with `./scripts/stop-local.ps1`; the stop script verifies process ownership against the checkout before terminating its own process trees. It preserves database and artifacts. Stop after jobs finish: forced process termination interrupts running work, which is subsequently marked interrupted through heartbeat recovery.

## Full Docker Compose profile

```powershell
cd backend
.venv/Scripts/python.exe -m app.cli init-postgres
cd ..
docker compose up --build
```

Services: Nginx/React frontend, FastAPI, persistent worker, PostgreSQL, migration service and MLflow. Frontend is exposed only on loopback port 8080. API, database and MLflow remain on the internal Compose network. Nginx supports direct SPA URLs and unbuffered SSE. Redis is unnecessary for the database-backed queue.

PostgreSQL stores application records in `retail_fraud`; a separate `retail_tracking` database prevents MLflow's migrations from colliding with application migrations. The initialization SQL creates the tracking database on first volume creation. Existing volumes created without that initialization need an explicit tracking-database creation before starting MLflow; do not delete existing volumes to resolve it. Shared artifact volumes preserve model/data/report files. Credentials come from ignored environment configuration and are not baked into images.

The Compose runtime uses its own database. Switching from local SQLite does not transfer accounts or research data automatically. Keep the local database intact and perform any future transfer through a reviewed migration/export process.

Docker and PostgreSQL are not installed on the current host. PostgreSQL DDL compilation and YAML structure have been checked; actual container builds, PostgreSQL locking behavior and service startup remain unverified. The Docker profile is supplied for validation on a host with Docker, not represented as a successful deployment here. Scientific images can be large because SDV/PyTorch, SHAP and MLflow are included.

## Resource envelope

Recommended for full local demonstrations: 8 CPU cores, 16 GB RAM and 25–40 GB free disk; more memory/disk for large repeated studies. Default jobs run on CPU. Dataset requests accept 100–100,000 rows, learned fitting accepts 1–200 epochs, tuning accepts 1–5 trials, SHAP accepts up to 200 explained rows/100 background rows, and robustness accepts up to five seeds and 2x augmentation. Start with 1,000–10,000 rows and a few learned-model epochs. Report progress is based on actual engine stages; calls without trustworthy counters remain indeterminate.

SQLite permits one worker per artifact store. PostgreSQL supports atomic queue claims across workers, but live multi-worker behavior still needs PostgreSQL verification. Stream sessions are bounded to 500 transactions and produce while subscribed; they are simulated research feeds, not payment integrations. Larger populations and long-lived high-throughput streaming require a separately sized deployment.

## Public hosting checklist

This delivery is a local research website. Before public hosting, configure TLS and production secure cookies, a precise allowed-origin list, trusted ingress handling, monitoring, storage/database backups, retention and recovery targets, account verification/recovery, and an operational threat-model review. Keep MLflow private. Do not expose raw model artifact directories or accept uploaded pickle files. Never commit `.env` or reuse example secrets.

Back up the application database, MLflow database and artifact store consistently while workers are stopped or using an appropriate database snapshot procedure. Restore into an isolated environment and verify artifact hashes before serving restored models. No automatic destructive retention cleanup or database downgrade is part of normal startup.
