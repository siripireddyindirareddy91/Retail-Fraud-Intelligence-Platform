# Railway PostgreSQL for the Vercel API

## Current evidence

On 4 November 2026 the Vercel backend at commit `5df5160` deployed a Python 3.12 Function of 18.5 MB. Runtime initialization fails because `RF_JWT_SECRET` is missing. Production PostgreSQL has not been connected or verified. The supplied frontend deployment's `/api/v1/health/live` returns Vercel `404 NOT_FOUND`; its API proxy is not verified.

## Connect the database

1. In your intended Railway project/environment, add a PostgreSQL service if one does not already exist. Review Railway's displayed cost before provisioning. Wait for the service to become healthy. Keep its persistent volume attached.
2. In PostgreSQL's Connect/Public Network settings, locate `DATABASE_PUBLIC_URL`. Vercel is outside Railway's private network: it needs the public TCP proxy hostname **and its assigned port**, not a `*.railway.internal` address. Enabling public networking exposes the database listener; use strong provider credentials and TLS. Do not paste the URL into chat, Git, screenshots or build commands.
3. In Vercel's **backend** project, add `RF_DATABASE_URL` for Production using that public URL. Change only the URI driver prefix from `postgresql://` (or `postgres://`) to `postgresql+psycopg://`. Preserve the encoded username/password, hostname, assigned port, database and existing query options. Require TLS with `sslmode=require` (append using `?`, or `&` if a query already exists); use provider CA/hostname verification where available. Do not disable TLS to work around connection failures.
4. Add `RF_JWT_SECRET` (a securely generated production secret of at least 32 bytes), `RF_ENVIRONMENT=production`, and `RF_COOKIE_SECURE=true`. Keep secrets in provider settings only. If a full research service shares the database/authentication, use the same JWT secret, issuer and audience there.
5. Set `RF_ALLOWED_ORIGINS` to a JSON list of the actual HTTPS frontend origins. The supplied clickable frontend URL is `https://frontend-jnda-8xf75iy4v-projects-0a3d.vercel.app`; the differently labelled `https://retail-fraud-intelligence-platform.vercel.app` must be checked before treating it as the production alias. Do not use wildcard origins. Include only domains you own and intend to use.

## Apply the schema once

Use a trusted release environment with the backend installed, and inject `RF_DATABASE_URL` and `RF_JWT_SECRET` through its secret settings. For a local release shell, set these privately for that process; do not type literal credentials into command history. Confirm the intended Railway project/environment and take a backup of an existing database before applying migrations.

From `backend`, using its existing virtual environment on Windows:

```powershell
.venv/Scripts/python.exe -m alembic -c alembic.ini current
.venv/Scripts/python.exe -m alembic -c alembic.ini upgrade head
.venv/Scripts/python.exe -m alembic -c alembic.ini check
```

Expected head is `0003_streams`. Never run migrations on ASGI import, per request, or against the default local SQLite URL by accident. PostgreSQL connectivity is established only by executing against the real service, not by URL validation. Keep production environment variables out of the test suite; browser acceptance requires its own isolated database/API/worker profile.

## Redeploy and connect the frontend

After saving Production variables, redeploy the latest backend commit with **Use existing Build Cache unchecked**. Check liveness (`/api/v1/health/live`, 200), readiness (`/api/v1/health/ready`, 200 and `status=ready`), OpenAPI (`/api/v1/openapi.json`), and anonymous authorization (`/api/v1/auth/me`, 401). Readiness returns 503 for an unavailable database or missing migrations. A Ready deployment badge alone is insufficient.

Once the stable backend alias actually passes readiness, run from the repository root:

```powershell
node frontend/scripts/prepare-vercel.mjs https://backend-opal-kappa-29.vercel.app
```

This generates an ignored `frontend/vercel.json` with the API reverse proxy and SPA fallback. Include that generated file in the frontend CLI source upload; a Git-triggered build does **not** include ignored files. For Git deployment, review and explicitly track the resulting non-secret configuration before pushing. Do not put database credentials or JWT secrets in frontend variables. Deploy with Root Directory `frontend`, build `npm run build`, output `dist`.

Verify the same health/OpenAPI/401 results through the frontend `/api/v1` proxy, deep-link navigation, secure refresh/CSRF cookie behavior, login/session restoration/logout and SSE on an isolated staging profile. Keep relative API URLs: Axios, download links and fetch/SSE all depend on the same-origin proxy.

## Research remains separate

PostgreSQL provides metadata and sessions, not training execution or artifact storage. A full Railway research application needs the existing hosted container, a persistent volume and its separate worker. Use Railway's private database URL for that service, and the public one for Vercel, pointing to the same database. Configure `RF_RESEARCH_API_ORIGIN` on Vercel only after the full service is ready; keep it unset on that service itself. Missing research execution must continue to return an explicit 503. Do not claim complete research readiness after only a database connection test.

References: [Railway PostgreSQL](https://docs.railway.com/databases/postgresql), [Railway TCP proxy](https://docs.railway.com/networking/tcp-proxy), [Vercel external rewrites](https://vercel.com/docs/routing/rewrites).
