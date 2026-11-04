# Vercel Python bundle reduction

## Cause and dependency profiles

The reported 5,940.71 MB bundle installed the entire research dependency graph.
The old default manifest included SDV, SHAP, MLflow, Matplotlib, ReportLab,
PyArrow and GPU-capable XGBoost. SDV brings PyTorch. Official PyPI metadata for
Torch 2.15 on Linux requires NVIDIA cuDNN, cuSPARSELt, NCCL, NVSHMEM and Triton;
GPU-capable XGBoost also requires NCCL on Linux. Those binaries can occupy
multiple GB even when the application only requests CPU execution. Exact
allocation of the original 5,940.71 MB needs its build manifest; that number was
reported by the user, not reproduced locally.

Lazy imports do not remove installed dependencies from Python Function bundles.
The installation profile has therefore changed as well as the startup imports.

| Runtime | Install | Dependencies/features |
| --- | --- | --- |
| Vercel API | Default `pyproject.toml` dependencies with `uv.lock`; no extras | FastAPI/auth/SQLAlchemy/PostgreSQL, NumPy/pandas/SciPy/scikit-learn, official CPU-only XGBoost, Fastparquet. All existing API routes and all four CPU detector types remain. |
| Full worker/local research | `pip install -e ".[research]"` from backend, or the updated full `requirements.lock.txt` snapshot | Adds SDV/PyTorch, SHAP, MLflow, PyArrow, Matplotlib and ReportLab. Generation, training, augmentation, explanations and PDF reporting remain real worker operations. |

The standard `uv.lock` records optional research packages too, but the default
export does not install them. Do not configure Vercel to install `.[research]`,
`--all-extras`, or the full worker `requirements.lock.txt`. Clear any old custom
install command that does so. The existing container Dockerfile intentionally
continues installing the full worker snapshot.

The CPU XGBoost distribution supplies the same `xgboost` Python module. It omits
GPU/federated algorithms; this application's existing workflows use CPU. No
implemented GPU feature was removed. Do not install `xgboost` and `xgboost-cpu`
over each other in one environment. Use a fresh environment when changing an
older install, or uninstall the old distribution before installing the new one.

## Startup and model loading

| Library | Previous behavior | Current behavior |
| --- | --- | --- |
| NumPy/pandas/SciPy/scikit-learn | Imported by API routers/data/ML modules during startup | Imported within feature functions or when unpickling a real detector |
| XGBoost | Already algorithm-specific import, but full GPU distribution installed | Algorithm-specific import/unpickle using `xgboost-cpu` |
| SDV/PyTorch | Function-scoped fitting/sampling, but installed in API | Worker extra only; still function-scoped |
| SHAP | Function-scoped explanation, but installed in API | Worker extra only |
| MLflow | Function-scoped worker tracking, but installed in API | Worker extra only |
| PyArrow | Implicit Parquet loading, installed in API | Worker writes unchanged Parquet using PyArrow; API explicitly reads it with Fastparquet |
| Matplotlib/ReportLab | Function-scoped PDF report, but installed in API | Worker extra only |

An actual cold ASGI import loads none of these scientific packages. Pickled
detectors still load only from checksummed, internally produced artifacts with
server-side ownership checks. No untrusted pickle upload or substitute model
implementation was introduced. Worker-to-API tests reproduce scores for all four
detector types and verify Parquet interoperability.

Capability responses now disclose API-local library availability and separate
worker execution instead of always claiming a complete local research runtime.
Authentication, authorization, database transactions and route paths are retained.

## Source inclusion

`backend/vercel.json` configures the actual `asgi.py` Function and explicitly
includes `app/**`. No API router, research implementation, worker module or
model-loading code is excluded. Both Function exclusions and `.vercelignore`
exclude local virtual environments, tests, audit scripts, caches, secrets and
private local runtime/data/artifact directories. No committed backend virtual
environment, database, pickle, Parquet artifact or cache was found in the source
audit. Required deployment artifacts must be served from the configured durable
store; these exclusions do not implement that store or delete local user data.

## Size evidence

See API_BUNDLE_MEASUREMENT.json for exact bytes, wheel names and SHA-256 hashes.
The audited target is CPython 3.12, Linux x86_64. Wheels were cross-downloaded on
Windows from the default API export of `uv.lock`; host marker evaluation can
include small additional pure-Python packages, so this is not a Linux execution
test. All wheel members are counted uncompressed, including vendored tests and
unused modules inside dependencies; dependencies were not manually stripped.

- Locked dependency wheels: approximately **338.08 MB** uncompressed.
- Included backend source/configuration/lockfiles: approximately **0.95 MB**.
- Additional bytecode estimate: approximately **109.99 MB**, compiling all
  compilable shipped Python sources without executing their code.
- Component estimate: approximately **449.03 MB decimal / 428.23 MiB**.
- Vercel's own runtime/wrapper overhead is **not measured**. The final cloud
  Function bundle has **not** been built or verified under 500 MB.

The preliminary API profile retaining PyArrow was 477.02 MB in dependency
wheels alone, before bytecode/overhead. Fastparquet provides margin while keeping
the application's Parquet preview/statistics/export behavior. Exact packaged
size still depends on the Vercel builder, platform and generated files.

Reproduce using `backend/scripts/audit_bundle.py --prepare`, export the default
API requirements from `uv.lock`, download their Linux Python 3.12 wheels, then
run the script with `--wheels` pointing to that download directory. The script
prints component bytes and always records `actual_vercel_bundle_verified=false`.
Its module docstring contains the complete cross-platform download command.

## Verification and remaining hosting work

An isolated API install without SDV, Torch, SHAP, MLflow, PyArrow, Matplotlib or
ReportLab has been exercised through authentication and all four prediction
APIs. A separate complete research environment exercises the original worker
workflows. Final results: **20 API-only tests passed; 74 full backend tests
passed, with one live-PostgreSQL check skipped**. Both dependency checks and the
Alembic check passed. Current evidence is recorded in VERIFICATION.md.

Keep Vercel Root Directory `backend`, FastAPI preset, Python 3.12, and the existing
`asgi:app` entrypoint. Keep frontend npm/dist overrides cleared. Commit `uv.lock`
and `vercel.json`, then request a fresh deployment without the previous build
cache once. Inspect the new Function's actual size before declaring the size
error resolved in the cloud. No large-function beta setting is used by this fix.

SDV/PyTorch, SHAP/robustness studies, reporting and MLflow belong on the separate
worker with the research extra. PostgreSQL migrations remain a release step.
The current filesystem artifact store still requires a genuinely shared durable
storage integration if API and worker are on different hosts; PostgreSQL alone
does not provide that. The existing combined container API/worker deployment
remains the ready-to-configure shared-volume option.

If the actual API bundle still exceeds the limit after platform overhead, the
next architecture is a private inference service hosting the existing four
pipelines and Parquet operations. Keep authentication/ownership and job routes
on the API and use authenticated internal calls; do not remove detector options
or substitute predictions. That service is a proposal, not implemented here.

References: [Vercel Python packaging](https://vercel.com/docs/functions/runtimes/python),
[Function limits](https://vercel.com/docs/functions/limitations),
[official CPU XGBoost package](https://xgboost.readthedocs.io/en/stable/install.html),
and [pandas Parquet engines](https://pandas.pydata.org/pandas-docs/version/2.3/reference/api/pandas.read_parquet.html).
