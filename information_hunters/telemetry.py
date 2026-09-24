"""Activity, errors, and per-run performance rows written by workers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from information_hunters.config import get_settings
from information_hunters.models import ActivityEvent, ErrorEvent, Host, Job, Lead, RunMetric, utcnow

PROVIDER_LABELS = {
    "companies_house": "Companies House",
    "companies_house_public": "Companies House",
    "demo": "the demo catalogue",
    "google_places": "Google Places",
    "registry": "the Companies House register",
    "scrapingbee": "ScrapingBee",
    "brightdata": "Bright Data",
    "apify": "Apify",
    "direct": "a direct page fetch",
    "playwright": "Playwright",
}


def provider_label(name: str) -> str:
    return PROVIDER_LABELS.get(name, name or "the registry")


def found_message(name: str, email: str | None, mobile: str | None, phone: str | None, has_website: bool, website: str | None) -> str:
    parts = [f"Found {name}"]
    if email:
        parts.append(f"email {email}")
    if mobile:
        parts.append(f"mobile {mobile}")
    elif phone:
        parts.append(f"phone {phone}")
    if has_website:
        parts.append(f"website {website}" if website else "has a website")
    else:
        parts.append("no website")
    return ", ".join(parts)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def record_activity(
    session,
    message: str,
    *,
    kind: str = "status",
    job: Job | None = None,
    worker_id: str = "",
    host_provider: str = "",
    detail: dict | None = None,
    commit: bool = False,
) -> None:
    session.add(
        ActivityEvent(
            host_provider=host_provider or get_settings().host_id or "",
            worker_id=worker_id or (job.worker_id if job is not None else "") or "",
            job_id=job.id if job is not None else "",
            kind=kind[:24],
            message=(message or "")[:500],
            detail=detail or {},
            created_at=utcnow(),
        )
    )
    if commit:
        session.commit()


def record_error(
    session,
    message: str,
    *,
    error_type: str = "error",
    provider: str = "",
    job: Job | None = None,
    worker_id: str = "",
    host_provider: str = "",
    context: dict | None = None,
    commit: bool = False,
) -> None:
    session.add(
        ErrorEvent(
            host_provider=host_provider or get_settings().host_id or "",
            worker_id=worker_id or (job.worker_id if job is not None else "") or "",
            job_id=job.id if job is not None else "",
            provider=(provider or "")[:40],
            error_type=(error_type or "error")[:80],
            message=(message or "")[:2000],
            context=context or {},
            created_at=utcnow(),
        )
    )
    if commit:
        session.commit()


def mark_quota(session, provider: str, detail: str, *, commit: bool = True) -> None:
    row = session.query(Host).filter(Host.provider == provider).one_or_none()
    now = utcnow()
    if row is None:
        row = Host(provider=provider, name=provider, status="quota_exhausted", controllable=False)
        session.add(row)
    row.status = "quota_exhausted"
    row.status_detail = (detail or "")[:500]
    row.last_error = (detail or "")[:500]
    row.updated_at = now
    row.stopped_at = now
    record_error(
        session,
        detail,
        error_type="quota_exhausted",
        provider=provider,
        host_provider=provider,
        commit=False,
    )
    if commit:
        session.commit()


def touch_run_metric(session, job: Job) -> None:
    session.flush()
    started = _aware(job.started_at)
    query = session.query(Lead).filter(Lead.job_id == job.id)
    leads = query.all()
    if started is not None:
        cutoff = started - timedelta(seconds=2)
        leads = [lead for lead in leads if (_aware(lead.updated_at) or started) >= cutoff]
    row = (
        session.query(RunMetric)
        .filter(RunMetric.job_id == job.id, RunMetric.finished_at.is_(None))
        .order_by(RunMetric.created_at.desc())
        .first()
    )
    now = utcnow()
    if row is None:
        row = RunMetric(job_id=job.id, created_at=now)
        session.add(row)
    finished = _aware(job.finished_at)
    end = finished or now
    anchor = started or now
    row.host_provider = get_settings().host_id or ""
    row.worker_id = job.worker_id or ""
    row.discovery_provider = job.discovery_provider or ""
    row.companies_searched = job.discovered_count or 0
    row.leads_found = job.qualified_count or 0
    row.leads_with_email = sum(1 for lead in leads if lead.email)
    row.leads_with_mobile = sum(1 for lead in leads if lead.mobile)
    row.leads_no_website = sum(1 for lead in leads if not lead.has_website)
    row.rejected_count = job.rejected_count or 0
    searched = row.companies_searched
    row.success_rate = int(round(100 * row.leads_found / searched)) if searched else 0
    row.duration_seconds = max(0, int((end - anchor).total_seconds()))
    row.status = job.status
    row.started_at = anchor
    row.finished_at = finished
    row.updated_at = now
