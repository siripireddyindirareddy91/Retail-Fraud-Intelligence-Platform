# Persistence schema

Current Alembic revision: 0003_streams. The application uses SQLAlchemy 2.0 with PostgreSQL support and a verified SQLite fallback. Normal startup runs migrations explicitly and never calls create_all.

## Tables

| Table | Stored resources |
|---|---|
| users | Normalized email, Argon2id password hash, role and active state |
| auth_sessions | Hashed rotating refresh/CSRF tokens, expiry and revocation |
| used_refresh_tokens | Hash history for replay detection |
| user_settings | Per-account theme, guidance and notification preferences |
| artifacts | Owner, immutable relative storage key, content type, size and SHA-256 |
| datasets | Name, method, counts, artifact reference and versioned generation/lineage configuration |
| experiments | Named drafts or completed training/robustness configurations |
| ml_models | Versioned fitted pipeline artifacts, source experiment, algorithm, threshold and status |
| jobs | Owner, configuration, state, real work counters, cancellation, heartbeat and result artifact |
| job_events | Increasing event IDs and durable progress/state snapshots |
| worker_heartbeats | Last-seen worker instances |
| notifications | Owned job outcomes and simulated high-risk alerts |
| audit_events | Account/admin/submission actions without secrets |
| rate_buckets | Hashed persistent fixed-window counters and expiry |
| research_runs | Typed workflow kind, config/result JSON, dataset/model/job references, output artifact and MLflow run ID |
| generative_models | CTGAN/TVAE artifacts, source dataset, method, training parameters and ownership |
| predictions | Saved feature vector, model version, separate probability/anomaly output, class, risk and nullable ground truth |
| stream_sessions | Bounded fictional stream configuration, owner/model, count, state and expiry |
| stream_events | Persisted transaction events with replay cursors |

IDs are UUID strings except increasing SSE event cursors. UTC timestamps use portable naive-UTC database columns and explicit Z-suffixed API serialization. Important owner/time/queue/session/event/search fields are indexed. Foreign keys and domain check constraints are enforced in both dialects. SQLite uses WAL and a busy timeout.

## Research output organization

The target architecture is implemented with relational ownership/lineage references plus versioned JSON configurations/results rather than one table for every metric type. Generation parameters and dataset metadata live in dataset/configuration and research-run records. Scenario executions, quality evaluations, training metrics, robustness conditions, SHAP results and report metadata are typed research runs. Large data/model/report payloads live in immutable artifacts, not JSON database blobs.

Dataset artifacts are Parquet. Model/synthesizer artifacts are trusted internal pickle bundles; they are never accepted as uploads, and hashes are checked before loading. JSON/PDF/CSV research outputs reference their source run. There is no arbitrary artifact upload or filesystem-path API.

Chronological/grouped split row identifiers and hashes are stored inside fitted model bundles. Research result JSON records split/source hashes, parameters, library versions and evaluation values. All resource endpoints enforce ownership separately from foreign-key consistency. An inaccessible resource returns 404. Historical outputs are preserved; no automatic destructive cleanup runs.

## Migrations

- 0001_foundation: accounts, artifacts, initial dataset/model/experiment records, jobs and system data.
- 0002_research: research results, fitted generative models, predictions and stream sessions.
- 0003_streams: persisted transaction stream events.

Run `python -m alembic -c alembic.ini upgrade head` from backend. `python -m alembic -c alembic.ini check` checks model/schema agreement. Downgrades are destructive and belong only in disposable test databases or a reviewed backup/recovery procedure.

Upgrade/downgrade tests execute on temporary SQLite databases. PostgreSQL DDL is compiled offline; a live PostgreSQL service is unavailable on this host and remains an explicit verification limitation.
