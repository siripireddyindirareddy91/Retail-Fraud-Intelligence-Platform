# Personal PC research host (no paid services)

The Vercel frontend and lightweight API use the existing Neon Free PostgreSQL database. Real research execution runs in `backend/.venv` on this Windows PC, using separate API and worker processes supervised by `app.hosted`. The API listens only on `127.0.0.1:8010`. Tailscale Funnel forwards its HTTPS endpoint to that loopback listener. No router port forwarding or paid compute is required.

## Configuration and storage

- Production database and JWT configuration are protected by Windows CurrentUser DPAPI at `%LOCALAPPDATA%\RetailFraudResearchHost\production.dpapi`, outside OneDrive. They are decrypted only in the launcher process and inherited by its child processes. No plaintext credentials are in Git, command arguments or application logs. The encrypted file is tied to this Windows account and machine; it is not a portable backup.
- Datasets, models, reports and tracking files are under `%LOCALAPPDATA%\RetailFraudResearchHost\retail-fraud`. Preserve this directory and the matching database when backing up research.
- Development services, accounts and the local SQLite database remain separate. This research host uses production PostgreSQL and production authentication.
- Vercel Production uses `RF_RESEARCH_API_ORIGIN=https://indu.tail6f7188.ts.net` and `RF_REQUIRE_WORKER_READY=true`. The research host itself leaves `RF_RESEARCH_API_ORIGIN` unset. Both APIs check active sessions and resource ownership.

## Start and stop

From the repository root, start the research host:

```powershell
./scripts/start-research-host.ps1
```

It runs migrations once before supervising the API and worker. The launcher runs in the background and records its process identity. Startup output is not a readiness guarantee; check `http://127.0.0.1:8010/api/v1/health/ready`. Logs are in `%LOCALAPPDATA%\RetailFraudResearchHost\host.log` and `host-errors.log`.

After signing in to the free Tailscale Personal account and enabling Funnel for this device:

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' funnel --bg http://127.0.0.1:8010
& 'C:\Program Files\Tailscale\tailscale.exe' funnel status
```

Stop when no research work is running:

```powershell
./scripts/stop-research-host.ps1
& 'C:\Program Files\Tailscale\tailscale.exe' funnel --https=443 off
```

The stop script verifies the recorded process creation time before terminating its process tree. Files are preserved. Forced shutdown during a job can interrupt it; stale jobs are marked interrupted rather than retried automatically. The public frontend remains available when this PC is off, but research requests return unavailable.

## Operating limits

Keep this PC awake and online while using research. No automatic PC wake or paid fallback is configured. Funnel has bandwidth limits and is suitable for a personal demonstration, not an uptime guarantee. Polling workers can keep Neon compute awake: stop the host when unused to conserve the Free plan's compute allowance. Exhausting a free quota may suspend execution; do not enable billing to bypass it. Heavy training remains bounded by this PC's CPU, RAM, disk and internet connection.

## Verification boundary

Local and public research readiness returned 200 with PostgreSQL revision `0003_streams`; anonymous account access returned 401. The full backend suite passed 84 tests with 1 live-PostgreSQL test skipped; the newly added loopback-binding regression passed separately. Alembic reported no new upgrade operations. These checks do not alone establish website dataset output or all hosted research workflows.
