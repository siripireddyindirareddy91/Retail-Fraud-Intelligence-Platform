# Vercel web-only API bundle

## What is established about the repeated 5,940.71 MB error

The baseline is commit bb0666c. Its default dependencies still included NumPy,
pandas, SciPy, scikit-learn, Joblib, CPU XGBoost and Fastparquet. They were not a
web-only install: the earlier measured component estimate was approximately
449 MB including bytecode, before unmeasured platform packaging overhead.

The original full research graph contains SDV/PyTorch, GPU-capable dependencies,
SHAP, MLflow, PyArrow and PDF libraries. The full worker snapshot remains in
requirements.lock.txt for containers/workers. Installing that snapshot, selecting
research extras, or building an older commit can bring back the multi-GB graph.

The exact reason the inaccessible cloud deployment still reports the identical
5,940.71 MB is NOT established. The supplied deployment URL belongs to a Projects
team unavailable to the currently authenticated CLI scope. Read-only inspection
failed; no cloud settings were changed. The deployed commit, installer and cache
contents could not be verified. These possibilities are hypotheses, not findings.

The current public Vercel Python builder source uses uv sync with --no-dev and
user lockfile selection; it does not select all optional extras by default. An
optional package appearing in uv.lock is not proof it was installed. Neither
.vercelignore nor lazy imports can uninstall a dependency selected by an installer.

## Deterministic install

backend/vercel.json now explicitly runs:

```text
python scripts/install_vercel_api.py
```

That script refuses an implicit environment, then synchronizes the builder's
active virtualenv with the frozen lockfile, no development/default groups, and
explicitly excludes the research and test extras. UV synchronization removes
extraneous dependencies. The follow-up checker fails the build if scientific or
NVIDIA packages are installed or imported while loading the application factory.
It prints API_INSTALL_PROFILE=web, research_packages=0 and the lock SHA-256.
Copy mode is explicit: a Windows cleanup permission error and an incompatible
OneDrive hardlink error were observed during follow-up installs. A new untouched
environment passed with copy mode; neither failed attempt is counted as passing.

This exact command passed in a fresh Python 3.12 virtualenv: 36 application
packages, zero scientific/research packages. NumPy, pandas, SciPy, scikit-learn,
Joblib, CPU XGBoost, Fastparquet, SDV, Torch, SHAP, MLflow, PyArrow, Matplotlib and
ReportLab are all in the optional research extra. requirements.lock.txt remains
the full worker snapshot and is not used by the Vercel installer. uv.lock locks
both profiles but the web installation selects only the default profile.

## Preserved execution and safe unavailability

All 55 API paths, the existing ASGI factory, authentication, roles, live-session
checks and ownership rules remain. No research implementation was deleted.

- Auth, metadata, stored results, model comparison, job monitoring and an empty
  dashboard work without scientific dependencies.
- Research submissions check a fresh database worker heartbeat in thin or
  readiness-enforced deployments. An unavailable/stale worker produces HTTP 503
  with research_worker_unavailable; no job is created. Full local profiles can
  still deliberately queue work before starting a worker, as before.
- For dataset preview/statistics/exports, analytics, manual predictions and
  simulated streams, configure RF_RESEARCH_API_ORIGIN to the HTTPS origin of the
  existing full research backend. That service installs .[research] and uses the
  same PostgreSQL database and JWT secret/issuer/audience. Keep the variable unset
  on the full research service. The setting accepts no embedded credentials,
  path or query; no credentials or service URL are invented by this change.
- The thin API delegates only these specific operations using the authenticated
  bearer token. The full backend rechecks session validity and resource ownership.
  Cookies and passwords are not forwarded; redirects and automatic retries are
  disabled. Transport failures produce sanitized HTTP 503 responses with
  research_service_unavailable. With no service configured, required operations
  return the same clear error instead of an ImportError or fake result.
- Artifact downloads can come from the full service's durable filesystem when
  the thin API has no local file. Both API sides enforce ownership. PostgreSQL
  stores shared metadata; model/data/report files stay with the research service
  and worker on their existing persistent volume.
- SSE bytes, replay cursors, response types and download filenames are relayed.
  Streaming I/O runs through Starlette's thread pool, not blocking the API event
  loop. This is HTTP delegation, not a replacement ML implementation.
- With RF_REQUIRE_WORKER_READY=true, readiness checks the real worker heartbeat
  and the research service's readiness instead of pretending the Function's
  temporary filesystem is a durable artifact store. The default false readiness
  setting continues to check DB/schema only.

The real full-runtime ASGI service was exercised through the delegation boundary
for model scores, PyArrow-written datasets, CSV exports, artifact checksums and
simulated SSE events, including tenant ownership. Cloud networking, credentials,
shared PostgreSQL and persistent volume deployment remain operator configuration,
not verified cloud capabilities.

## Function contents and measurement

All application runtime modules remain included under app/**. Tests, build tools,
audit scripts, local virtualenvs, caches, generated build/ copies, secrets and
private local runtime/data directories are excluded from the Function. Build
scripts remain in the source upload because the installer needs them, then are
excluded from the runtime bundle. No datasets or models were deleted. Generated
backend/build/ output is also ignored by Git.

API_BUNDLE_MEASUREMENT.json records wheel names, SHA-256 hashes and exact bytes.
The measured target is Linux x86_64 CPython 3.12, cross-downloaded on Windows:

| Component | Approximate decimal MB |
| --- | ---: |
| Web dependencies plus published vercel-runtime 0.24.1 wheel | 54.96 |
| Application source/configuration/lockfiles | 0.96 |
| Additional all-source bytecode estimate | 23.68 |
| Component estimate | 79.61 |

The runtime version is taken from the current public Vercel Python builder source,
not the inaccessible failed deployment. Remaining platform wrapper overhead and
any builder-specific duplication are unmeasured. All wheel members are counted;
third-party binaries or required modules were not stripped. This is not Linux
execution and is NOT a built Vercel Function. actual_vercel_bundle_verified stays
false. The prior 449 MB estimate is historical and superseded for this profile.

Reproduce with backend/scripts/audit_bundle.py, exporting the default uv.lock
profile with research/test excluded, downloading Linux Python 3.12 wheels and
including the published Vercel runtime wheel. The script compiles source without
executing it to estimate additional bytecode. Final test counts are in
VERIFICATION.md.

## Next deployment check

Use the backend project, Root Directory backend, FastAPI, Python 3.12, asgi:app.
Commit the changed manifest, lock, configuration, scripts and runtime guards.
For the next authorized deployment, confirm the new commit and the exact install
command in the log; look for API_INSTALL_PROFILE=web and research_packages=0.
Request a cache-free rebuild once and inspect the resulting Function's actual
size. A missing marker means the verified installer did not run. An unchanged
5,940.71 MB is not evidence this new dependency profile was built.

No deployment success or sub-500 MB cloud bundle is claimed here. The final
Function must be verified by Vercel before declaring LAMBDA_SIZE_EXCEEDED solved.

References: [Vercel Python installer source](https://github.com/vercel/vercel/blob/main/packages/python/src/uv.ts),
[custom installer handling](https://github.com/vercel/vercel/blob/main/packages/python/src/index.ts),
[Python packaging](https://vercel.com/docs/functions/runtimes/python), and
[Function limits](https://vercel.com/docs/functions/limitations).

## File-by-file changes in this fix

| File | Explanation |
| --- | --- |
| `.gitignore` | Ignore generated backend/build output; no user data is deleted. |
| `backend/.vercelignore` | Keep build scripts in source uploads, exclude generated build copies. |
| `backend/vercel.json` | Explicit web installer; exclude generated build/tool files from the Function, retain application modules. |
| `backend/pyproject.toml` | Move every scientific/inference dependency into research; retain HTTPX in the web runtime for delegation. |
| `backend/uv.lock` | Lock the new web default and optional research graphs consistently. |
| `backend/app/core/config.py` | Validate optional HTTPS research-service origin and hide sensitive configuration inputs in errors. |
| `backend/app/services/research_runtime.py` | Live-worker gate and bounded, authenticated research HTTP/SSE delegation with sanitized failures and no automatic retries. |
| `backend/app/api/jobs.py` | Gate worker-dependent submissions before creating jobs. |
| `backend/app/api/research.py` | Guard or delegate scientific reads/inference; keep metadata local and validate numerical inputs with the standard library. |
| `backend/app/api/streams.py` | Delegate generation/event streams while retaining local authorization, state and replay behavior. |
| `backend/app/api/workspace.py` | Delegate an owned artifact download when its file is held on the full service. |
| `backend/app/api/system.py` | Readiness checks delegated storage/service rather than ephemeral local storage when configured. |
| `backend/scripts/install_vercel_api.py` | Frozen, no-extra, copy-mode synchronization in an explicitly active API environment. |
| `backend/scripts/check_api_install.py` | Reject scientific/NVIDIA packages and startup imports; emit safe profile/lock fingerprint. |
| `backend/scripts/audit_bundle.py` | Identify the included runtime wheel separately from unmeasured platform overhead. |
| `backend/tests/test_api_profile.py` | Reflect web-only dependencies and safe unavailability; scientific tests remain for the full profile. |
| `backend/tests/test_web_profile.py` | Cover core functionality, no-job 503s, worker freshness, service errors, origins and delegated readiness. |
| `backend/tests/test_research_delegation.py` | Exercise real upstream scientific operations, downloads, SSE, score equality and tenant isolation. |
| `docs/API_BUNDLE_MEASUREMENT.json` | Save current measured wheel sizes, hashes, bytecode and source estimate. |
| `docs/VERCEL_BUNDLE_SIZE.md` | Root-cause evidence boundaries, corrected profile, installation, delegation and this manifest. |
| `docs/VERCEL_BACKEND.md` | Update required service configuration and web-only behavior. |
| `docs/VERIFICATION.md` | Record final passes/skips, installation failures and cloud-verification limits. |
| `README.md` | Describe the web-only default and separate research execution. |
| `SYSTEM_ARCHITECTURE.md` | Record the minimal web/control-plane and full-service boundary. |
| `INSTALLATION_GUIDE.md` | Separate web installation from the full research profile. |
| `DEPLOYMENT_GUIDE.md` | Document the explicit installer, service delegation and current Git availability. |

`backend/asgi.py`, `backend/requirements.lock.txt`, the trained-model files,
datasets, worker engine implementations and application factory were inspected
and retained. The entrypoint still exposes the real existing FastAPI application.
