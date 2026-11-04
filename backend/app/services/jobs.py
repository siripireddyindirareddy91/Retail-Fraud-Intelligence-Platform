from sqlalchemy import select

from ..models import Job, JobEvent, Notification, UserSettings, now

TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}


def record_event(db, job):
    db.add(JobEvent(job_id=job.id, state=job.state, stage=job.stage, payload={"completed_units": job.completed_units, "total_units": job.total_units, "error": job.error, "result_artifact_id": job.result_artifact_id}))


def finish(db, job, state, error=None):
    job.state, job.error, job.finished_at = state, error, now()
    job.stage = {"succeeded": "Completed", "cancelled": "Cancelled", "failed": "Failed", "interrupted": "Worker interrupted"}[state]
    record_event(db, job)
    preferences = db.get(UserSettings, job.owner_id)
    if not preferences or preferences.job_notifications:
        db.add(Notification(user_id=job.owner_id, job_id=job.id, severity="info" if state in {"succeeded", "cancelled"} else "error", message=f"{job.kind}: {job.stage.lower()}"))


def job_data(job):
    percentage = int(100 * job.completed_units / job.total_units) if job.total_units else None
    return {"id": job.id, "kind": job.kind, "state": job.state, "stage": job.stage, "completed_units": job.completed_units, "total_units": job.total_units, "progress_percentage": percentage, "cancel_requested": job.cancel_requested, "error": job.error, "result_artifact_id": job.result_artifact_id, "created_at": job.created_at.isoformat() + "Z", "started_at": job.started_at.isoformat() + "Z" if job.started_at else None, "finished_at": job.finished_at.isoformat() + "Z" if job.finished_at else None}


def claim_next(db, worker_id):
    from sqlalchemy import update
    query = select(Job.id).where(Job.state == "queued").order_by(Job.created_at, Job.id).limit(1)
    if db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    job_id = db.scalar(query)
    if not job_id:
        db.rollback()
        return None
    claimed = db.execute(update(Job).where(Job.id == job_id, Job.state == "queued").values(state="running", stage="Starting", worker_id=worker_id, started_at=now(), heartbeat_at=now())).rowcount
    if claimed != 1:
        db.rollback()
        return None
    job = db.get(Job, job_id)
    record_event(db, job)
    db.commit()
    return job_id
