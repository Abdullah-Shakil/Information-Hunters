"""Long-polling worker. Safe to run on a separate host from the website.

The process only needs DATABASE_URL and provider secrets. Pause and stop are
rows in the jobs table, so the control plane can steer a remote worker.
"""

from __future__ import annotations

import logging
import signal
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone

from information_hunters.config import get_settings
from information_hunters.db import session_scope
from information_hunters.models import Job, Worker
from information_hunters.pipeline import process_job

log = logging.getLogger("information_hunters.worker")

_stop = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def request_stop(_signum=None, _frame=None) -> None:
    global _stop
    _stop = True


def worker_identity() -> str:
    settings = get_settings()
    if settings.worker_id:
        return settings.worker_id
    return f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


def _touch(worker_id: str, job_id: str | None) -> None:
    with session_scope() as session:
        row = session.get(Worker, worker_id)
        now = _utcnow()
        if row is None:
            row = Worker(id=worker_id, hostname=socket.gethostname(), last_seen=now, current_job_id=job_id)
            session.add(row)
        else:
            row.last_seen = now
            row.current_job_id = job_id
            row.hostname = socket.gethostname()
        session.commit()


def claim_next_job(worker_id: str) -> str | None:
    settings = get_settings()
    stale_before = _utcnow() - timedelta(seconds=settings.heartbeat_stale_seconds)
    with session_scope() as session:
        bind = session.get_bind()
        query = session.query(Job).filter(Job.status == "queued").order_by(Job.created_at.asc())
        if bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        job = query.first()
        if job is None:
            stale = (
                session.query(Job)
                .filter(Job.status == "running", Job.heartbeat_at.is_not(None), Job.heartbeat_at < stale_before)
                .order_by(Job.heartbeat_at.asc())
            )
            if bind.dialect.name == "postgresql":
                stale = stale.with_for_update(skip_locked=True)
            job = stale.first()
        if job is None:
            return None
        job.status = "running"
        job.worker_id = worker_id
        job.heartbeat_at = _utcnow()
        job.started_at = job.started_at or _utcnow()
        session.commit()
        return job.id


def serve_forever() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    worker_id = worker_identity()
    log.info("Worker %s polling %s", worker_id, settings.resolved_database_url().split("@")[-1])
    while not _stop:
        _touch(worker_id, None)
        job_id = claim_next_job(worker_id)
        if not job_id:
            time.sleep(settings.poll_interval_seconds)
            continue
        _touch(worker_id, job_id)
        log.info("Running job %s", job_id)
        try:
            process_job(job_id, worker_id, should_stop=lambda: _stop)
        except Exception:
            log.exception("Job %s failed", job_id)
        _touch(worker_id, None)
    log.info("Worker %s stopped", worker_id)


def main() -> None:
    from information_hunters.db import init_db

    init_db()
    serve_forever()


if __name__ == "__main__":
    main()
