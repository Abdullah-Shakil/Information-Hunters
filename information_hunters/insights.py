"""Queries for the performance and live activity tabs."""

from __future__ import annotations

from information_hunters.models import ActivityEvent, ErrorEvent, Job, RunMetric


def performance_view(session, host: str | None = None, worker: str | None = None, limit: int = 100) -> dict:
    query = session.query(RunMetric)
    if host == "local":
        query = query.filter(RunMetric.host_provider == "")
    elif host:
        query = query.filter(RunMetric.host_provider == host)
    if worker:
        query = query.filter(RunMetric.worker_id == worker)
    rows = query.order_by(RunMetric.updated_at.desc()).limit(limit).all()
    items = [_run_out(session, row) for row in rows]
    searched = sum(item["companies_searched"] for item in items)
    found = sum(item["leads_found"] for item in items)
    by_host: dict[str, dict] = {}
    for item in items:
        bucket = by_host.setdefault(
            item["host_provider"] or "local",
            {"host": item["host_provider"] or "local", "runs": 0, "companies_searched": 0, "leads_found": 0, "leads_with_email": 0, "leads_with_mobile": 0, "leads_no_website": 0},
        )
        bucket["runs"] += 1
        bucket["companies_searched"] += item["companies_searched"]
        bucket["leads_found"] += item["leads_found"]
        bucket["leads_with_email"] += item["leads_with_email"]
        bucket["leads_with_mobile"] += item["leads_with_mobile"]
        bucket["leads_no_website"] += item["leads_no_website"]
    for bucket in by_host.values():
        bucket["success_rate"] = int(round(100 * bucket["leads_found"] / bucket["companies_searched"])) if bucket["companies_searched"] else 0
    return {
        "totals": {
            "runs": len(items),
            "companies_searched": searched,
            "leads_found": found,
            "leads_with_email": sum(item["leads_with_email"] for item in items),
            "leads_with_mobile": sum(item["leads_with_mobile"] for item in items),
            "leads_no_website": sum(item["leads_no_website"] for item in items),
            "success_rate": int(round(100 * found / searched)) if searched else 0,
        },
        "by_host": list(by_host.values()),
        "runs": items,
    }


def errors_view(session, host: str | None = None, provider: str | None = None, error_type: str | None = None, limit: int = 200) -> dict:
    query = session.query(ErrorEvent)
    if host == "local":
        query = query.filter(ErrorEvent.host_provider == "")
    elif host:
        query = query.filter(ErrorEvent.host_provider == host)
    if provider:
        query = query.filter(ErrorEvent.provider == provider)
    if error_type:
        query = query.filter(ErrorEvent.error_type == error_type)
    rows = query.order_by(ErrorEvent.created_at.desc()).limit(limit).all()
    return {"items": [_error_out(row) for row in rows], "total": len(rows)}


def activity_view(session, host: str | None = None, kind: str | None = None, limit: int = 80) -> dict:
    query = session.query(ActivityEvent)
    if host == "local":
        query = query.filter(ActivityEvent.host_provider == "")
    elif host:
        query = query.filter(ActivityEvent.host_provider == host)
    if kind:
        query = query.filter(ActivityEvent.kind == kind)
    rows = query.order_by(ActivityEvent.created_at.desc()).limit(limit).all()
    return {"items": [_activity_out(row) for row in rows]}


def _run_out(session, row: RunMetric) -> dict:
    job = session.get(Job, row.job_id)
    return {
        "id": row.id,
        "job_id": row.job_id,
        "job_name": job.name if job is not None else row.job_id,
        "host_provider": row.host_provider or "",
        "worker_id": row.worker_id,
        "discovery_provider": row.discovery_provider,
        "companies_searched": row.companies_searched,
        "leads_found": row.leads_found,
        "leads_with_email": row.leads_with_email,
        "leads_with_mobile": row.leads_with_mobile,
        "leads_no_website": row.leads_no_website,
        "rejected_count": row.rejected_count,
        "success_rate": row.success_rate,
        "duration_seconds": row.duration_seconds,
        "credits_consumed": row.credits_consumed,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _error_out(row: ErrorEvent) -> dict:
    return {
        "id": row.id,
        "host_provider": row.host_provider,
        "worker_id": row.worker_id,
        "job_id": row.job_id,
        "provider": row.provider,
        "error_type": row.error_type,
        "message": row.message,
        "context": row.context or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _activity_out(row: ActivityEvent) -> dict:
    return {
        "id": row.id,
        "host_provider": row.host_provider,
        "worker_id": row.worker_id,
        "job_id": row.job_id,
        "kind": row.kind,
        "message": row.message,
        "detail": row.detail or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
