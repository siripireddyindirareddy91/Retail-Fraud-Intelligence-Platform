"""Persistent bounded worker. Run separately from the HTTP service."""
import argparse
import logging
import signal
import threading
from datetime import timedelta

from filelock import FileLock, Timeout
from sqlalchemy import delete, select, update

from ..core.config import Settings
from ..database import make_database
from ..models import Artifact, Job, RateBucket, WorkerHeartbeat, now, uid
from ..services.artifacts import inspect_artifact, write_json
from ..services.jobs import claim_next, finish, record_event

log = logging.getLogger("retail.worker")


class Cancelled(Exception):
    pass


def recover_stale(sessions, settings):
    with sessions() as db:
        stale = db.scalars(select(Job).where(Job.state == "running", Job.heartbeat_at < now() - timedelta(seconds=settings.stale_seconds)).with_for_update()).all()
        for job in stale:
            finish(db, job, "interrupted", {"code": "worker_lost", "message": "Worker heartbeat expired. Submit a new job explicitly."})
        db.execute(delete(RateBucket).where(RateBucket.expires_at < now()))
        db.commit()


def checkpoint(sessions, job_id, worker_id, stage, completed=None, total=None):
    with sessions() as db:
        db.execute(update(Job).where(Job.id == job_id, Job.state == "running").values(heartbeat_at=Job.heartbeat_at))
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.worker_id != worker_id or job.state != "running":
            raise Cancelled()
        if job.cancel_requested:
            finish(db, job, "cancelled")
            db.commit()
            raise Cancelled()
        job.stage, job.heartbeat_at = stage, now()
        if completed is not None:
            job.completed_units = completed
        if total is not None:
            job.total_units = total
        record_event(db, job)
        db.commit()


def execute(sessions, settings, job_id, worker_id):
    try:
        with sessions() as db:
            job = db.get(Job, job_id)
            owner_id, kind = job.owner_id, job.kind
            artifacts = db.scalars(select(Artifact).where(Artifact.owner_id == owner_id).order_by(Artifact.id)).all()
        if kind != "system.integrity_check":
            from ..research.processor import process
            process(sessions, settings, job_id, worker_id, lambda stage: checkpoint(sessions, job_id, worker_id, stage))
            return
        # Progress counts actual artifact inspections plus report publication.
        total, results = len(artifacts) + 1, []
        checkpoint(sessions, job_id, worker_id, "Inspecting artifact checksums", 0, total)
        for index, artifact in enumerate(artifacts):
            results.append(inspect_artifact(settings.artifact_root, artifact))
            checkpoint(sessions, job_id, worker_id, "Inspecting artifact checksums", index + 1, total)
        checkpoint(sessions, job_id, worker_id, "Publishing integrity report")
        with sessions() as db:
            db.execute(update(Job).where(Job.id == job_id, Job.state == "running").values(heartbeat_at=Job.heartbeat_at))
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job.state != "running" or job.worker_id != worker_id:
                return
            if job.cancel_requested:
                finish(db, job, "cancelled")
            else:
                artifact = write_json(db, settings.artifact_root, owner_id, "artifact-integrity-report.json", {"job_id": job_id, "checked_at": now().isoformat() + "Z", "checked_count": len(results), "invalid_count": sum(not item["valid"] for item in results), "artifacts": results})
                job.result_artifact_id, job.completed_units = artifact.id, total
                finish(db, job, "succeeded")
            db.commit()
    except Cancelled:
        pass
    except Exception as error:
        log.exception("job_failed", extra={"job_id": job_id})
        with sessions() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job and job.state == "running" and job.worker_id == worker_id:
                message = str(error)[:350] if isinstance(error, ValueError) else "The worker could not complete this job. See server logs using its job identifier."
                finish(db, job, "failed", {"code": "execution_failed", "message": message})
                db.commit()


def run_worker(settings=None, once=False, stop=None):
    settings = settings or Settings()
    engine, sessions = make_database(settings.database_url)
    stop = stop or threading.Event()
    worker_id = uid()
    settings.artifact_root.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(settings.artifact_root / ".sqlite-worker.lock")) if engine.dialect.name == "sqlite" else None
    heartbeat_stop = threading.Event()
    active_job: list[str | None] = [None]

    def beat():
        while not heartbeat_stop.is_set():
            try:
                with sessions() as db:
                    row = db.get(WorkerHeartbeat, worker_id)
                    if row:
                        row.last_seen = now()
                    else:
                        db.add(WorkerHeartbeat(id=worker_id, last_seen=now()))
                    if active_job[0]:
                        db.execute(update(Job).where(Job.id == active_job[0], Job.worker_id == worker_id, Job.state == "running").values(heartbeat_at=now()))
                    db.commit()
            except Exception:
                log.exception("worker_heartbeat_failed")
            heartbeat_stop.wait(2)

    heartbeat = threading.Thread(target=beat, daemon=True)
    try:
        if lock:
            lock.acquire(timeout=0)
        recover_stale(sessions, settings)
        heartbeat.start()
        while not stop.is_set():
            recover_stale(sessions, settings)
            with sessions() as db:
                job_id = claim_next(db, worker_id)
            if job_id:
                active_job[0] = job_id
                execute(sessions, settings, job_id, worker_id)
                active_job[0] = None
            if once:
                break
            stop.wait(settings.poll_seconds)
    except Timeout:
        raise RuntimeError("SQLite permits one worker per artifact store. Stop the existing worker first.")
    finally:
        heartbeat_stop.set()
        if heartbeat.is_alive():
            heartbeat.join(timeout=10)
        with sessions() as db:
            db.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.id == worker_id))
            db.commit()
        if lock and lock.is_locked:
            lock.release()
        engine.dispose()


def main():
    from ..middleware import configure_logging
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process at most one queued job")
    args = parser.parse_args()
    settings = Settings()
    configure_logging(settings.log_level)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    run_worker(settings, args.once, stop)


if __name__ == "__main__":
    main()
