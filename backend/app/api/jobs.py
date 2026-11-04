import asyncio
import json
import time
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .deps import CurrentUser, DB, owned
from .workspace import page
from ..core.errors import APIError
from ..models import AuditEvent, AuthSession, Job, JobEvent, User, now
from ..schemas import JobSubmission
from ..services.jobs import TERMINAL, finish, job_data, record_event
from ..services.rate_limit import enforce

router = APIRouter(prefix="/jobs", tags=["Background jobs"])


@router.post("", status_code=202)
def submit(payload: JobSubmission, request: Request, user: CurrentUser, db: DB, idempotency_key: str | None = Header(default=None, min_length=1, max_length=80)):
    if idempotency_key:
        existing = db.scalar(select(Job).where(Job.owner_id == user.id, Job.idempotency_key == idempotency_key))
        if existing:
            return submission_data(existing)
    enforce(db, f"job:{user.id}", request.app.state.settings.job_limit, seconds=60)
    job = Job(owner_id=user.id, kind=payload.kind, idempotency_key=idempotency_key)
    db.add(job)
    try:
        db.flush()
        record_event(db, job)
        db.add(AuditEvent(actor_id=user.id, action="job.submit", resource_id=job.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Job).where(Job.owner_id == user.id, Job.idempotency_key == idempotency_key)) if idempotency_key else None
        if not existing:
            raise
        job = existing
    return submission_data(job)


def submission_data(job):
    return {"job_id": job.id, "state": job.state, "status_url": f"/api/v1/jobs/{job.id}", "events_url": f"/api/v1/jobs/{job.id}/events"}


@router.get("")
def list_jobs(user: CurrentUser, db: DB, limit: int = Query(20, ge=1, le=100), cursor: UUID | None = None):
    return page(db, select(Job).where(Job.owner_id == user.id), Job, limit, cursor, job_data)


@router.get("/{job_id}")
def get_job(job_id: UUID, user: CurrentUser, db: DB):
    return job_data(owned(db, Job, job_id, user.id))


@router.post("/{job_id}/cancel")
def cancel_job(job_id: UUID, user: CurrentUser, db: DB):
    job = owned(db, Job, job_id, user.id)
    # Lock through an update before checking current state, so cancellation cannot
    # overwrite a concurrent worker completion on either supported database.
    from sqlalchemy import update
    db.execute(update(Job).where(Job.id == job.id).values(cancel_requested=Job.cancel_requested))
    db.refresh(job)
    if job.state in TERMINAL:
        raise APIError(409, "job_finished", "A finished job cannot be cancelled.")
    job.cancel_requested = True
    if job.state == "queued":
        finish(db, job, "cancelled")
    else:
        job.stage = "Cancellation requested"
        record_event(db, job)
    db.commit()
    return job_data(job)


@router.get("/{job_id}/events")
def job_events(job_id: UUID, request: Request, user: CurrentUser, db: DB, after: int = Query(0, ge=0), last_event_id: int | None = Header(None, ge=0)):
    owned(db, Job, job_id, user.id)
    user_id, session_id = user.id, request.state.auth_session_id
    # End the dependency transaction before a potentially long stream.
    db.rollback()
    sessions, settings = request.app.state.sessions, request.app.state.settings
    token = request.headers["authorization"].split(" ", 1)[1]

    async def events():
        from ..core.security import decode_access
        import jwt
        cursor = max(after, last_event_id or 0)
        deadline = time.monotonic() + settings.sse_max_seconds
        while time.monotonic() < deadline:
            if await request.is_disconnected():
                return
            try:
                decode_access(settings, token)
            except jwt.InvalidTokenError:
                yield 'event: auth_expired\ndata: {"reason":"access_token_expired"}\n\n'
                return
            def snapshot():
                with sessions() as session:
                    account, auth = session.get(User, user_id), session.get(AuthSession, session_id)
                    if not account or not account.active or not auth or auth.revoked_at or auth.expires_at <= now():
                        return None
                    rows = session.scalars(select(JobEvent).where(JobEvent.job_id == str(job_id), JobEvent.id > cursor).order_by(JobEvent.id).limit(100)).all()
                    return [(row.id, row.state, row.stage, row.payload) for row in rows], session.get(Job, str(job_id)).state
            result = await asyncio.to_thread(snapshot)
            if result is None:
                yield 'event: auth_expired\ndata: {"reason":"session_revoked"}\n\n'
                return
            rows, state = result
            for event_id, event_state, stage, payload in rows:
                cursor = event_id
                yield f"id: {event_id}\nevent: job\ndata: {json.dumps({'state': event_state, 'stage': stage, **payload})}\n\n"
            if state in TERMINAL and len(rows) < 100:
                return
            if not rows:
                yield ": keepalive\n\n"
            await asyncio.sleep(settings.poll_seconds)
        yield 'event: reconnect\ndata: {}\n\n'
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
