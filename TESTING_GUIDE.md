# Verification

Run from backend/ using its isolated environment:

In a restricted Windows environment where the default temporary directory is unavailable, set `$env:PYTEST_DEBUG_TEMPROOT=(Resolve-Path ../runtime).Path` before pytest. All temporary databases and tracking files then stay in the ignored workspace runtime directory. This changes test storage only, not the application's database.

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m alembic -c alembic.ini check
.venv/Scripts/python.exe -m pip check
```

The suite exercises real migrations, authentication, authorization, ownership, workers, generation, CTGAN/TVAE, four detector algorithms, SHAP, robustness, simulated streams and report exports. Tests use disposable SQLite databases and isolated tracking stores. Offline PostgreSQL SQL compilation does not replace a live PostgreSQL test. Scientific libraries emit deprecation warnings; these are distinct from failed checks.

Learned-generation tests use at least 500 rows, which exercises CTGAN's parallel-transform branch. They reject a nested Joblib process pool while still fitting and sampling actual CTGAN/TVAE models. Production learned fitting and sampling select Joblib's sequential backend so the separate bounded research worker does not fan out into an all-core subprocess pool.

`tests/test_hosted.py` verifies worker/storage readiness and real subprocess supervision. `tests/test_postgres.py` is an opt-in live PostgreSQL migration, locking, worker and ownership check. Supply `RF_TEST_POSTGRES_URL` privately using the `postgresql+psycopg://` driver and a test server login with permission to create databases. The check creates and removes only its own uniquely named `rf_verify_*` database, never migrates the supplied database, and leaves its absence clearly marked as a skip. Do not put connection credentials in command history or committed files.

Run from frontend/:

```powershell
npm run build
npm test
npm run test:e2e
```

Browser checks cover all 32 catalog routes, navigation, search, themes, responsive layout, simulated-stream completion/filtering/details/manual stop, and an actual generation/training/prediction/explanation/robustness/learned-generation/PDF workflow on desktop and mobile. The default uses one browser worker to bound memory usage. The runner owns a separate API on port 8001, worker, temporary database, tracking store and frontend on port 5175. It does not use the user's account or application database. CPU training can take minutes; workflow timeouts account for queued worker execution. Test artifacts remain ignored under runtime/ and frontend/test-results/ when present.

The browser runner waits up to 180 seconds for cold scientific-library/API startup, reports early process exit separately, and allows `RF_E2E_STARTUP_TIMEOUT_MS` between 1,000 and 600,000 for measured slow environments. Assertions and research execution checks remain unchanged. An external `PLAYWRIGHT_BASE_URL` must refer to a separately isolated staging stack, never the user's production or local application database.

For concurrent acceptance runs, set distinct `RF_E2E_API_PORT` and `RF_E2E_FRONTEND_PORT` values before `npm run test:e2e`. The runner uses those loopback ports for its own API, frontend proxy and exact test CORS origin; temporary database and worker isolation are unchanged. It rejects occupied ports instead of stopping another run. Each concurrent Playwright run should also use a distinct `--output` directory.

A generated multipage PDF was rendered with Poppler and visually inspected. Deployment requires a separate Docker/PostgreSQL smoke test; neither runtime is available here. See docs/ACCEPTANCE.md for scope and MODEL_EVALUATION.md for statistical limitations.

