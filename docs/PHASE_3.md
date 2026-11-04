# Phase 3 delivery — backend foundation

Implemented on 4 November 2026. This milestone establishes backend infrastructure; research engines remain future phases.

## Delivered

- Modular FastAPI application factory, Pydantic validation and typed OpenAPI/Swagger.
- SQLAlchemy persistence with initial Alembic migration, PostgreSQL driver and verified SQLite fallback. No automatic table creation on API startup.
- Registration, login, logout, Argon2id password hashing, bounded JWTs with issuer/audience validation, rotating hashed refresh sessions, CSRF protection and immediate session revocation.
- Researcher/admin roles, private resource ownership, administrator bootstrap and last-active-administrator protection.
- Persistent rate limiting, bounded JSON bodies, safe error envelopes and request IDs, structured logs without credentials, development CORS allowlist and production secure-cookie configuration checks.
- Account preferences/profile, experiment drafts, artifact metadata/downloads, notifications, audit events, private search and dashboard counts from persisted records.
- Durable job queue, separate worker, actual work counters, cancellation, atomic claims, heartbeat/stale-job recovery, failure reporting, per-owner submission idempotency and replayable authenticated SSE.
- A genuine artifact-integrity workflow exercises jobs, checksum validation, report publication and download. It is not a fraud or synthetic-data engine.
- Frontend sign-in/protected workspace, session restoration, account-aware profile/logout, saved preferences, persisted experiment/history views, administrator UI, real notifications and system/API pages.
- Exact Python dependency snapshot, local setup instructions and optional PostgreSQL/API/worker Compose foundation profile.

## Verification

Verified: 22 backend tests, 36 component tests and 8 browser scenarios pass. The production TypeScript/Vite build passes. Backend tests cover SQLite migrations and negative security cases, worker processing, persistence, artifacts and SSE. Component tests retain all 32 route checks. Browser tests run desktop Chromium and mobile WebKit against an isolated real API and worker. Alembic reports no pending metadata changes, pip reports no broken requirements, and npm reports zero dependency vulnerabilities. See TESTING_GUIDE.md for commands and boundaries.

## Remaining limits

- No Docker or PostgreSQL server exists on this machine. PostgreSQL DDL compiles; live PostgreSQL locking/migrations and container startup need verification on a suitable host.
- MLflow is explicitly unconfigured. Its research tracking integration belongs to training/experiment engine work.
- The 14-table initial schema supports the foundation and minimal dataset/model records; later research tables/fields will be added through migrations when their modules are implemented.
- Module interfaces for generation, fraud detection/simulation, robustness, SHAP and research report exports disclose unavailable execution. Do not confuse these with completed research functionality.
- System Health subscribes to live job events and polls as a fallback; full resubscription handling for long research workloads will be extended with those engines.
- Local research accounts have no email delivery/password-recovery service or MFA/SSO. Public deployment requires the operational decisions listed in the architecture.

Next phase: rule/statistical generation, CTGAN/TVAE, dataset validation, quality analysis and actual dataset export.
