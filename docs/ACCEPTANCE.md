# Implementation and acceptance

Updated 4 November 2026. This application studies fictional transactions; generated results are not evidence of performance on real retail fraud.

## Current deployment verification

The Vercel + Railway hosting profile is implemented in source, not yet deployed. `app.hosted` runs migrations, supervises separate API/worker processes, keeps files on a persistent volume and requires worker/storage readiness. Source-upload allowlists exclude secrets and generated research data. Vercel routing is generated only after a real backend passes its readiness check.

- Production frontend build: passed. Frontend component suite: passed (36 tests).
- Hosting readiness/configuration/supervision: 14 tests passed.
- Actual CTGAN and TVAE fit, conditional samples and quality checks: both passed after fixing CTGAN's unbounded nested Joblib preprocessing pool. Regression coverage forbids that process backend while executing the real models.
- Full backend: 61 tests passed, 1 skipped (live PostgreSQL). Final desktop/mobile browser acceptance is running; do not treat earlier or partial browser runs as the final result.
- Alembic metadata check and installed dependency check: passed after the final backend changes.
- Live PostgreSQL: unavailable until a test service is connected. The opt-in check creates a disposable database and tests migrations, row locking, worker execution and ownership; an unavailable server is a skip, not a pass.
- Docker/Linux image, Railway deployment, Vercel API proxy/cookies/SSE and cloud persistence/restarts: not yet verified. Vercel and Railway account connections are pending. No hosted URL has been created.

Restricted Windows sandbox runs could not use the default pytest temporary directory and stalled API/process-based checks. Verified reruns use disposable workspace test data outside that sandbox. Browser tests keep their own API, database, tracking store and worker; they do not use the user's application database.

| Area | Implemented behavior | Verification |
| --- | --- | --- |
| Architecture and frontend | 32 named catalog routes, shared responsive layout, themes, forms, search | Component and desktop/mobile browser suites |
| Authentication | Argon2 passwords, memory-only access tokens, rotating refresh cookies, CSRF, roles, ownership and live session checks | Disposable-database API tests |
| Data generation | Seeded rule/statistical generation, real fitted CTGAN and TVAE, conditional samples, Parquet storage and exports | Engine, worker/API and browser workflows |
| Fraud scenarios | Ten controlled scenarios with ground truth kept separate from predictions | Engine tests |
| Data analysis | Validation, missingness, outliers, category and distribution comparisons, saved results | API and engine tests |
| Detection | Logistic regression, random forest, XGBoost and isolation forest; chronological or customer-grouped splits | Real training and evaluation tests |
| Evaluation | Held-out PR/ROC, confusion, calibration, validation-selected thresholds and compatible-model comparison | Engine and API tests |
| Robustness | Shared held-out A–F comparisons, training-only augmentation, paired customer bootstrap intervals and bounded sensitivity tests | Engine and API tests |
| Explanations | Actual SHAP calculations using training background, original-feature importance and saved-prediction explanations | Engine, API and browser workflows |
| Monitoring | Bounded persisted simulated streams, real optional inference, cursor replay, saved predictions and alerts | API stream tests and browser controls |
| Tracking and reporting | Durable jobs, interruption/cancellation handling, MLflow metadata/artifacts, downloadable PDF/CSV | Worker/API tests; PDF rendered and visually reviewed |
| Installation and deployment | Local start/stop scripts; full PostgreSQL/API/worker/MLflow/Nginx compose configuration | Local launcher exercised; Docker and live PostgreSQL unavailable |

## Boundaries

There is no real transaction feed, payment integration or production decision service. Stream events are explicitly simulated. CPU training and SHAP execution are bounded, on demand and may take minutes. Progress indicates completed stages; numerical completion is not invented during library calls. Empty accounts contain no fabricated statistics. Negative augmentation results remain visible.

SQLite supports the single-machine workflow. PostgreSQL SQL compilation is checked but does not establish live PostgreSQL behavior. The container stack requires runtime validation on a machine with Docker before deployment. Public hosting, domain, TLS and operational monitoring are not provisioned by the local launcher.

See TESTING_GUIDE.md for reproducible check commands and MODEL_EVALUATION.md for methodological limitations.
