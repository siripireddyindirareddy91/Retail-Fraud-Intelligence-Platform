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
- Latest backend JUnit record at runtime/qa/backend-final.xml: **61 passed, 1 skipped**, no failures/errors. The skipped check requires live PostgreSQL. This browser-focused change did not modify backend code.
- Alembic and dependency checks previously passed; scientific-library deprecation warnings remain distinct from failures.
- Actual generated PDF was rendered with Poppler and visually inspected.
- Docker and live PostgreSQL remain unverified here; the browser checks establish the local SQLite workflow, not a hosted deployment.

Earlier incomplete browser runs were superseded by the clean 12-case passing run above. Reproduce checks using TESTING_GUIDE.md. Avoid concurrent scientific/browser suites on an 8 GB host.
