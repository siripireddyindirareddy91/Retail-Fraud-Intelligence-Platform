# Working agreements

- Read SYSTEM_ARCHITECTURE.md before changing architecture. The full local research workflow is implemented; preserve real engine execution and consult docs/ACCEPTANCE.md for verification boundaries.
- Preserve the 32 named catalog routes and individual page components. Keep shared layout and form primitives reusable.
- Never invent dataset statistics, progress, predictions, backend capabilities or experimental results.
- Keep ground truth separate from predictions. Backend-dependent controls must disclose unavailable execution until integrated.
- Store only non-sensitive UI preferences and drafts locally. Enforce real authorization on the backend in Phase 3.
- Run `npm run build` and `npm test` in frontend after meaningful frontend changes. Use Playwright for browser navigation and responsive verification.
- Keep README and verification notes current; distinguish passing checks from unavailable checks.
- Backend: use backend/.venv, SQLAlchemy transactions and Alembic migrations. Never call create_all on application startup or dynamically import current model metadata from a historical migration.
- Check active accounts, live sessions, role and resource ownership on the server. Keep JWTs out of localStorage; never print secrets or passwords. Browser tests must use their isolated API/database/worker profile.
- Run `python -m pytest -q` and `python -m alembic -c alembic.ini check` from backend after backend changes. PostgreSQL SQL compilation does not replace live PostgreSQL verification.
- Keep worker work out of the API event loop. Progress reflects actual completed work; stale workers produce interrupted jobs. Do not add automatic retries for non-idempotent research operations.
