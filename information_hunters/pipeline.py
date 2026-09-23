"""Run one hunt job to completion, pause, or stop.

The website never calls this. Workers do.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime, timezone

from information_hunters.config import get_settings
from information_hunters.db import session_scope
from information_hunters.models import Job, JobLog, Lead
from information_hunters.providers.base import DiscoveredCompany, EnrichedCompany, Verification
from information_hunters.providers.demo import DemoDiscovery, DemoEnricher
from information_hunters.providers.factory import build_providers
from information_hunters.scoring import ScoreInput, score_lead


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_log(session, job: Job, level: str, message: str) -> None:
    session.add(JobLog(job_id=job.id, level=level, message=message))
    job.heartbeat_at = _utcnow()
    session.commit()


def _halt(session, job: Job, should_stop: Callable[[], bool] | None) -> str | None:
    session.refresh(job)
    if job.status in {"paused", "stopping", "stopped"}:
        return job.status
    if should_stop and should_stop():
        job.status = "queued"
        job.stage = "Requeued while the worker shut down"
        add_log(session, job, "info", "Worker shutting down. Hunt requeued from its checkpoint.")
        return "requeued"
    return None


def _finish_halt(session, job: Job, reason: str) -> None:
    if reason == "paused":
        job.stage = "Paused"
        add_log(session, job, "info", "Paused by operator.")
        return
    if reason == "requeued":
        return
    job.status = "stopped"
    job.stage = "Stopped"
    job.finished_at = _utcnow()
    add_log(session, job, "info", "Stopped by operator.")


def _upsert_lead(session, job: Job, enriched: EnrichedCompany, verification: Verification, discovered: DiscoveredCompany) -> None:
    trading = verification.actively_trading
    if trading is None:
        trading = bool(discovered.raw.get("actively_trading"))
    result = score_lead(
        ScoreInput(
            has_website=enriched.has_website,
            email=enriched.email,
            mobile=enriched.mobile,
            phone=enriched.phone,
            incorporation_date=enriched.incorporation_date,
            company_status=enriched.company_status,
            actively_trading=trading,
        )
    )
    if not result.qualified:
        job.rejected_count += 1
        add_log(session, job, "info", f"Rejected {enriched.name}: {result.reasons[0]}")
        return

    existing = session.query(Lead).filter(Lead.company_number == enriched.company_number).one_or_none()
    now = _utcnow()
    lead = existing or Lead(company_number=enriched.company_number, name=enriched.name, created_at=now)
    suppressed = bool(existing and existing.do_not_contact)
    lead.name = enriched.name
    lead.location = enriched.region
    lead.address = enriched.address
    lead.postcode = enriched.postcode
    lead.category = enriched.category
    lead.sic_codes = enriched.sic_codes
    lead.sic_labels = enriched.sic_labels
    lead.phone = enriched.phone
    lead.mobile = enriched.mobile
    lead.email = enriched.email
    lead.website = enriched.website
    lead.has_website = enriched.has_website
    lead.incorporation_date = enriched.incorporation_date
    lead.company_status = enriched.company_status
    lead.trading_status = "verified_active"
    lead.priority_score = result.score
    lead.priority_band = result.band
    lead.priority_reasons = result.reasons
    lead.sources = enriched.sources + [{"provider": verification.source, "reference": verification.notes}]
    lead.verification_notes = verification.notes
    lead.synthetic = enriched.synthetic
    lead.job_id = job.id
    lead.updated_at = now
    lead.do_not_contact = suppressed
    if existing is None:
        session.add(lead)
    job.qualified_count += 1
    add_log(session, job, "info", f"Qualified {enriched.name} · priority {result.score} ({result.band})")


def process_job(job_id: str, worker_id: str, should_stop: Callable[[], bool] | None = None, step_delay: float | None = None) -> None:
    settings = get_settings()
    delay = settings.demo_step_delay_ms / 1000 if step_delay is None else step_delay
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        if job.status in {"stopping", "stopped"}:
            job.status = "stopped"
            job.finished_at = _utcnow()
            session.commit()
            return
        job.status = "running"
        job.worker_id = worker_id
        job.started_at = job.started_at or _utcnow()
        job.heartbeat_at = _utcnow()
        job.error = None
        session.commit()
        try:
            _run(session, job, delay, should_stop)
        except Exception as exc:
            session.rollback()
            job = session.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:2000]
                job.finished_at = _utcnow()
                job.stage = "Failed"
                add_log(session, job, "error", f"Hunt failed: {exc}")
            raise


def _run(session, job: Job, delay: float, should_stop: Callable[[], bool] | None) -> None:
    discovery, enricher, verifier = build_providers(session, job)
    pairs = [(c, r) for c in job.categories for r in job.regions]
    total = max(len(pairs), 1)
    start_pair, start_company = _checkpoint(job)
    add_log(session, job, "info", f"Hunt started with {discovery.name} / {verifier.name}.")

    for pair_index, (category, region) in enumerate(pairs):
        if pair_index < start_pair:
            continue
        halt = _halt(session, job, should_stop)
        if halt:
            _finish_halt(session, job, halt)
            return
        job.stage = f"Discovering {category} in {region}"
        session.commit()
        after = job.incorporated_after
        if isinstance(after, datetime):
            after = after.date()
        found = discovery.discover(category, region, job.limit_per_search, after)
        add_log(session, job, "info", f"Found {len(found)} companies for {category} in {region}.")
        for company_index, discovered in enumerate(found):
            if pair_index == start_pair and company_index < start_company:
                continue
            halt = _halt(session, job, should_stop)
            if halt:
                job.checkpoint = {"pair_index": pair_index, "company_index": company_index}
                session.commit()
                _finish_halt(session, job, halt)
                return
            job.stage = f"Checking {discovered.name}"
            job.checkpoint = {"pair_index": pair_index, "company_index": company_index}
            job.discovered_count += 1
            session.commit()
            enriched = enricher.enrich(discovered)
            verification = _verify(verifier, discovered, enriched)
            _upsert_lead(session, job, enriched, verification, discovered)
            done = pair_index + (company_index + 1) / max(len(found), 1)
            job.progress = min(99, int(done / total * 100))
            session.commit()
            if delay:
                time.sleep(delay)
        start_company = 0

    job.status = "completed"
    job.stage = "Completed"
    job.progress = 100
    job.checkpoint = None
    job.finished_at = _utcnow()
    add_log(session, job, "info", f"Completed. {job.qualified_count} qualified, {job.rejected_count} rejected.")


def _checkpoint(job: Job) -> tuple[int, int]:
    point = job.checkpoint or {}
    return int(point.get("pair_index") or 0), int(point.get("company_index") or 0)


def _verify(verifier, discovered: DiscoveredCompany, enriched: EnrichedCompany) -> Verification:
    if verifier.name == "demo":
        trading = bool(discovered.raw.get("actively_trading"))
        note = "Demo verifier: simulated active-trading check. This is not a live Google result."
        if not trading:
            note = "Demo verifier: marked not actively trading."
        return Verification(actively_trading=trading, notes=note, source="demo")
    return verifier.verify(enriched)


# Imported for tests that want the catalogue without the factory.
_ = (DemoDiscovery, DemoEnricher)
