# API reference

Base URL: /api/v1. Live Swagger and exact Pydantic schemas: /api/v1/docs. Machine-readable contract: /api/v1/openapi.json. Unknown input fields are rejected. Every workspace endpoint requires a current bearer session; ownership is checked server-side. Liveness/readiness and documentation are public.

## Implemented resource groups

| Domain | Endpoints |
|---|---|
| Authentication | POST /auth/register, /auth/login, /auth/refresh, /auth/logout; GET /auth/me |
| Account/admin | GET/PATCH /settings; PATCH /profile; GET /users; PATCH /users/{id} |
| Dataset generation | POST /datasets/generate; GET /datasets; GET /datasets/{id}, /preview, /statistics, /download?format=csv or json |
| Generative models | POST /generative-models/train; GET /generative-models |
| Scenarios | GET /scenarios/catalog; POST /scenarios/execute |
| Detection models | POST /models/train, /models/comparison; GET /models, /models/{id}; PATCH /models/{id}/status |
| Predictions | POST /predictions, /predictions/batch; GET /predictions, /predictions/{id}; POST /predictions/{id}/explanation |
| Analyses | POST /analysis with a typed analysis selector |
| Robustness | POST /robustness/runs |
| Research results | GET /runs, /runs/{id}; GET /jobs/{id}/result |
| Reports | POST/GET /reports; authenticated output download through artifact endpoints |
| Experiments | POST/GET /experiments; GET /experiments/{id} |
| Artifacts | GET /artifacts; GET /artifacts/{id}/download |
| Durable jobs | POST/GET /jobs; GET /jobs/{id}, /jobs/{id}/events; POST /jobs/{id}/cancel |
| Simulation streams | POST /streams; GET /streams/{id}, /streams/{id}/events; POST /streams/{id}/stop |
| Workspace/system | GET /dashboard, /analytics/overview, /search, /notifications, /capabilities, /system/status; PATCH /notifications/{id}; GET /health/live, /health/ready |

## Research requests

Dataset generation accepts name, method (rule_based/statistical/ctgan/tvae), rows, fraud_rate, seed, distribution, categories, payment_methods, device_types, regions, start_at and end_at. Learned methods additionally require a fitted generative_model_id and can constrain other fitted fields through conditions. Label quotas use fraud_rate. No real payment credentials or personal data are required or generated.

Generative training takes dataset_id, method, epochs, seed and name. Detector training takes dataset_id, algorithm, name, seed, split (chronological/customer_grouped) and trials (1–5). Comparisons reject incompatible held-out hashes and duplicate model selections.

POST /analysis supports quality, validation, patterns, risk, drift, imbalance, noise, unseen, performance, shap, importance and permutation. Depending on type, it requires an owned dataset/model/reference/prediction. Controls include samples, background_samples, levels, noise_mode, source, group_by, threshold, target_fpr and unseen_scenario. Model-performance/SHAP/sensitivity analyses use the stored model's held-out/background data as documented; they do not silently refit preprocessing on the selected population.

POST /robustness/runs takes dataset_id, name, algorithm, augmentation, ratio, seeds and optional learned-model epochs. It produces actual paired A–F conditions and the signed scorecard. POST /reports takes a saved run_id and pdf/csv format. Explanations describe model behavior, not proof of fraud.

Research operations return HTTP 202 with job_id/state/status_url/events_url. This is queue acceptance, not completion. GET /jobs/{id} reports actual state/stage, errors and known work counters. GET /jobs/{id}/result returns a committed research-run result once published. Unsupported/malformed requests fail explicitly.

## Authentication and controls

Registration takes email, display_name and a 12–128-character password with exact whitespace preserved. It never accepts an administrator role. JWT access tokens stay in browser memory, with issuer/audience/expiry validation and server-side session checks. Rotating opaque refresh cookies are HttpOnly and scoped to auth routes. Refresh/logout require X-CSRF-Token from the readable CSRF cookie, validated against the session hash. Untrusted origins are rejected. Logout, replay revocation and account deactivation invalidate access immediately.

Lists use bounded limits and stable UUID cursors where provided; preview/prediction endpoints use bounded offset pagination. Research/synthesizer/history selection views currently load at most 100 recent resources. Search covers owned dataset/model/experiment names and saved transaction identifiers. List ordering is documented in each response; recent dashboards are ordered by creation time.

Sensitive endpoints use persistent fixed-window rate limits; 429 responses include Retry-After. Queued/running research work is capped at five jobs per account. JSON bodies are bounded to 64 KiB. Validation errors omit raw submitted values. Standard errors use {error:{code,message,details,request_id}} and request identifiers accompany logs/responses. Credentials and request bodies are not logged.

## Events

Authenticated SSE uses fetch with a bearer header. Job and transaction events have increasing durable IDs; clients reconnect using Last-Event-ID or after. Job terminal events close the stream. Access expiry/revocation ends authenticated streams; clients refresh access and reconnect or poll persisted status. Monitoring sessions generate fictional records only while subscribed, stop explicitly or at their bound, and retain events/history for inspection.

Dataset CSV/JSON exports, Parquet files, trusted model bundles, research JSON and PDF/CSV reports are authenticated downloads. There is no arbitrary filesystem read, pickle upload or execution endpoint.

Implementation references: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ ; https://docs.sdv.dev/sdv/ ; https://shap.readthedocs.io/en/latest/ ; https://mlflow.org/docs/latest/ml/tracking/ .
