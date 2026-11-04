# Retail Fraud Intelligence Platform

A working local research website for fictional retail transaction generation, fraud detection and controlled model robustness experiments.

## Open the website

After dependency installation (see INSTALLATION_GUIDE.md):

```powershell
./scripts/start-local.ps1
```

Open http://127.0.0.1:5174/dashboard and register your own researcher account. Swagger: http://127.0.0.1:8000/api/v1/docs. Stop with `./scripts/stop-local.ps1`. No default credentials are included; administrator bootstrap is an interactive local CLI command.

## Implemented workflow

- All 32 individual catalog routes, responsive navigation, themes, account settings and private resource search.
- Rule/statistical generation, actual SDV CTGAN/TVAE training and conditional sampling, validation, quality analysis and CSV/JSON dataset exports.
- Ten fraud scenarios with independent synthetic ground truth.
- Logistic Regression, Random Forest, XGBoost and Isolation Forest, fitted preprocessing, chronological/grouped splits, bounded tuning, registry versions and predictions.
- Paired A–F baseline/augmentation studies with shared tests, signed performance changes, same-size controls, uncertainty, drift, imbalance, noise and unseen-fraud analyses.
- Global/local SHAP, original-feature mapping and held-out permutation importance.
- Persisted experiments, MLflow metrics/artifacts, authenticated background jobs and replayable SSE events.
- Bounded simulated monitoring, model predictions and alerts; actual dashboard charts and saved results.
- PDF/CSV research reports, authenticated artifact downloads, authentication/roles and database migrations.

The verified local database is SQLite. PostgreSQL support and a complete Docker Compose profile are prepared; Docker/PostgreSQL runtime verification is pending because those services are unavailable on this machine. This is a synthetic-data research platform, not a production payment processor. Quality and explanations do not prove privacy or real-world fraud efficacy.

For hosted deployment, `railway.json` and `backend/app/hosted.py` prepare a persistent API/worker service, while `frontend/scripts/prepare-vercel.mjs` prepares the Vercel frontend's same-origin API routing after verifying a real backend. Account connections, live PostgreSQL/cloud checks and hosted acceptance are required before a working public URL can be claimed. See DEPLOYMENT_GUIDE.md for the full Vercel + Railway profile.

## Verification

Browser acceptance: all 12 desktop/mobile cases pass, including all 32 routes and the real research/report workflow. See docs/VERIFICATION.md for fixes, evidence and deployment boundaries.

```powershell
# backend/
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m alembic -c alembic.ini check
# frontend/
npm run build
npm test
npm run test:e2e
```

Browser tests start an isolated real API, worker and temporary database; they never mock research results. See TESTING_GUIDE.md for prerequisites and coverage.

## Documentation

- PROJECT_REQUIREMENTS.md: original specification.
- SYSTEM_ARCHITECTURE.md: approved architecture and implementation notes.
- DATABASE_SCHEMA.md / API_DOCUMENTATION.md: persistence and API contracts.
- MODEL_EVALUATION.md: scientific methodology, score definitions and limitations.
- INSTALLATION_GUIDE.md / DEPLOYMENT_GUIDE.md: local startup, optional containers and operations.
- TESTING_GUIDE.md: reproducible checks.
- docs/ACCEPTANCE.md: delivery status and verification boundaries.

Use Python 3.12 and Node 22.12+ or Node 24 LTS. Exact dependency snapshots are included. Generated data, models, reports, secrets and runtime logs are ignored by Git. The source is organized under frontend/ and backend/app/research/ rather than empty domain directories.


