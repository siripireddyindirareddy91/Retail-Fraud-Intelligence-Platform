# Local installation

Requirements: Python 3.12, Node 22.12+ or 24, and npm. Allow several GB for the scientific Python dependencies and generated artifacts.

The default backend `pyproject.toml` install is now the API/CPU-inference profile.
The full snapshot below includes research engines. A full worker can alternatively
install `pip install -e ".[research]"` from backend. Vercel should use the default
profile with `uv.lock`, never the full worker snapshot or research extras.

For an existing environment that has `xgboost`, stop its services after research
jobs finish before changing packages. Use a fresh environment, or uninstall that
distribution before installing `xgboost-cpu`; do not overlay both distributions.
The CPU package retains the implemented CPU workflows. Keep all user databases
and artifacts intact. See docs/VERCEL_BUNDLE_SIZE.md for profile details.

From the project root:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
backend/.venv/Scripts/python.exe -m pip install --no-deps -e backend
npm --prefix frontend ci
./scripts/start-local.ps1
```

Open http://127.0.0.1:5174/dashboard and register your own account. Existing accounts and artifacts persist under runtime/. Never commit runtime contents or backend/.env. The launcher initializes local configuration, applies Alembic migrations and starts the API, worker and website in hidden processes. Logs are in runtime/. It refuses occupied ports.

```powershell
./scripts/stop-local.ps1
```

Stopping preserves accounts, datasets, models and results. Start again using the same launcher. API documentation is at http://127.0.0.1:8000/api/v1/docs.

Begin by generating a dataset, then train a detector and inspect its held-out evaluation. Train CTGAN/TVAE before requesting learned samples. Use robustness studies for controlled augmentation comparisons. Small CPU jobs can take minutes; do not interpret stage indicators as measured percentage completion. Reports export actual saved results.

For container deployment, PostgreSQL, MLflow and public-hosting requirements, see DEPLOYMENT_GUIDE.md. The full container configuration is prepared but has not been runtime verified on this machine.

