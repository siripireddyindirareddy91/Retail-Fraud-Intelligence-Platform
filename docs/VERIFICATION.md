# Verification record — 4 November 2026

## Final browser acceptance

- Playwright: **12 passed (3.4 minutes)** in one complete clean run, using one worker.
- Both desktop Chromium and an emulated iPhone viewport passed: authentication and session restoration, saved settings and experiment history, worker integrity/export, logout/login, all 32 catalog routes, search/history/navigation drawer, themes and responsive width checks.
- Both passed real dataset generation, detector training, batch prediction, SHAP, paired robustness evaluation, CTGAN fitting, conditional generation, PDF download, dashboard totals and chart rendering.
- Both passed simulated stream automatic completion, filtering, transaction details, separation of ground truth from unavailable predictions and explicit stop.
- Desktop training/dashboard and desktop/mobile monitoring screenshots were visually inspected. Charts render real saved results; tables scroll within their panels.
- Tests used isolated accounts, API, worker, temporary database and tracking storage. Existing user research data was not used or reset.

## Fixes verified

Workflow submission now waits for research resources to finish loading. Learned generation submits the validated fitted model shown in the dropdown, including when an old draft contains another selection. The conditional-sampling example now uses a supported payment-method condition; fraud percentage controls the label quota.

The theme test now verifies persisted settings through the UI instead of reading a response body after navigation. Each browser case creates its own account so monitoring events cannot contaminate research dashboard totals. The login check verifies return to the current protected route.

## Other checks and boundaries

- Production frontend build: passed after the fixes.
- Frontend component tests: **36 passed**.
- Full backend suite after separating API/worker dependencies: **74 passed, 1 skipped**, with 496 existing scientific-library/deprecation warnings. The skipped check requires live PostgreSQL. This supersedes the earlier entrypoint-only 66-test passing run.
- Alembic check: no new upgrade operations detected. Dependency check: no broken requirements found.
- Actual generated PDF was rendered with Poppler and visually inspected.
- Docker and live PostgreSQL remain unverified here; the browser checks establish the local SQLite workflow, not a hosted deployment.

Earlier incomplete browser runs were superseded by the clean 12-case passing run above. Reproduce checks using TESTING_GUIDE.md. Avoid concurrent scientific/browser suites on an 8 GB host.

## Vercel entrypoint verification

The independent import from backend/ loaded `asgi:app` as a real FastAPI instance
with all 55 API paths. No test fixture, hosted supervisor or worker module was
imported, and no database file was created. Five regression tests verify explicit
entrypoint resolution, preservation of factory OpenAPI/middleware and HTTP
behavior, no process/connection/migration startup, mandatory environment secrets,
and production secure-cookie enforcement.

Vercel CLI 65.11.0 is installed, but no backend project settings are linked
locally. A Vercel cloud build, Linux dependency bundle, production database,
shared storage and external-worker integration have not been verified by this
entrypoint change. See docs/VERCEL_BACKEND.md before deploying.

## API bundle profile verification

- A separately created API-only environment passed **20 tests** covering the
  entrypoint, zero scientific startup imports, authentication, all four detector
  prediction routes, Parquet reading, queued research operations and truthful
  capability reporting. Its dependency check passed.
- That API environment contains none of SDV, Torch, SHAP, MLflow, PyArrow,
  Matplotlib or ReportLab. Existing full-worker serialized models loaded there
  and reproduced scores for all four detectors, including the original XGBoost
  wheel to the CPU-only distribution. Worker-written PyArrow Parquet also read
  successfully there through Fastparquet.
- The full research environment passed **74 tests**, with one live-PostgreSQL
  check skipped. Alembic and dependency checks passed. The full environment
  retains compatibility with its historical XGBoost distribution; the new
  API-only environment verifies the official CPU distribution directly.
- Exporting the default `uv.lock` profile excludes research extras. Measured
  Linux CPython 3.12 wheels total **338,080,245 bytes**. Source/config/lockfiles
  plus an all-source bytecode estimate produce **449,026,784 bytes**. See
  API_BUNDLE_MEASUREMENT.json for the full wheel/hash evidence and
  VERCEL_BUNDLE_SIZE.md for the method and limitations.
- This cross-platform component measurement supersedes the earlier absence of
  Linux wheel-size evidence. It is not Linux execution or a Vercel cloud build.
  Vercel runtime overhead and the actual packaged Function size remain
  unverified, as do live PostgreSQL and shared remote artifact integration.
- Frontend code did not change in this step; the earlier 12 passing browser
  cases were not rerun for this backend-only packaging change.
