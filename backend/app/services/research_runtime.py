"""Optional research execution boundary, after normal auth/ownership checks."""
from datetime import timedelta
import importlib.util

import httpx
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from starlette.background import BackgroundTask

from ..core.errors import APIError
from ..models import WorkerHeartbeat, now


def modules_available(*names):
    return all(importlib.util.find_spec(name) is not None for name in names)


def require_worker(db, settings):
    # Full local research profiles may deliberately queue work before a worker
    # starts. Thin API installs and production readiness-enabled profiles fail
    # closed when no genuine recent worker heartbeat exists.
    if settings.require_worker_ready or settings.research_api_origin or not modules_available("sdv", "torch", "pyarrow"):
        worker = db.scalar(select(WorkerHeartbeat.id).where(WorkerHeartbeat.last_seen >= now() - timedelta(seconds=settings.stale_seconds)).limit(1))
        if not worker:
            raise APIError(503, "research_worker_unavailable", "The research worker is unavailable. No job was queued. Start the configured research worker and try again.", headers={"Retry-After": "30"})


def forward_if_needed(request, *modules, payload=None, stream=False, force=False):
    origin = request.app.state.settings.research_api_origin
    if not force and not origin and modules_available(*modules):
        return None
    if not origin or request.headers.get("x-research-delegated"):
        raise APIError(503, "research_service_unavailable", "This operation requires the research runtime. Configure the research service or run the backend with its research dependencies.", headers={"Retry-After": "30"})
    # The allowlisted origin is operator configuration, never request input.
    # Forward only the already authenticated bearer token, not cookies/passwords
    # or arbitrary inbound headers. The full service rechecks the live session,
    # role and resource ownership using the same database and JWT configuration.
    headers = {"Authorization": request.headers["authorization"], "X-Research-Delegated": "1"}
    if request.headers.get("last-event-id"):
        headers["Last-Event-ID"] = request.headers["last-event-id"]
    client = httpx.Client(timeout=httpx.Timeout(30, connect=5), follow_redirects=False, trust_env=False)
    upstream = None
    try:
        target = origin + request.url.path
        if request.url.query:
            target += "?" + request.url.query
        outgoing = client.build_request(request.method, target, headers=headers, json=payload if payload is not None else None)
        upstream = client.send(outgoing, stream=bool(stream))
        if upstream.is_redirect or upstream.status_code >= 500:
            raise APIError(503, "research_service_unavailable", "The research service could not complete this operation. Try again later.", headers={"Retry-After": "30"})
        returned_headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
        if upstream.headers.get("content-disposition"):
            returned_headers["Content-Disposition"] = upstream.headers["content-disposition"]
        media_type = upstream.headers.get("content-type", "application/json")
        if stream and upstream.is_success:
            if stream is True and "text/event-stream" not in media_type:
                raise APIError(503, "research_service_unavailable", "The research service did not provide an event stream.")

            def close():
                upstream.close()
                client.close()

            def chunks():
                try:
                    yield from upstream.iter_bytes()
                finally:
                    close()

            return StreamingResponse(chunks(), status_code=upstream.status_code, media_type=media_type, headers=returned_headers, background=BackgroundTask(close))
        content = upstream.read()
        if not upstream.is_success and "application/json" not in media_type:
            raise APIError(503, "research_service_unavailable", "The research service could not complete this operation.")
        return Response(content, status_code=upstream.status_code, headers=returned_headers, media_type=media_type)
    except httpx.HTTPError:
        raise APIError(503, "research_service_unavailable", "The research service is unavailable. Try again later.", headers={"Retry-After": "30"}) from None
    finally:
        # A successful SSE response owns these until completion/disconnection.
        if not (stream and upstream is not None and upstream.is_success and (stream is not True or "text/event-stream" in upstream.headers.get("content-type", ""))):
            if upstream is not None:
                upstream.close()
            client.close()
