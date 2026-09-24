"""Control-plane API. Next.js desk proxies here with no user login."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from information_hunters.catalogue import (
    BOT_PROFILES,
    MODEL_PROFILES,
    SCRAPER_PROFILES,
    build_agent,
    enrich_model,
)
from information_hunters.categories import categories, regions
from information_hunters.cloud_worker import cloud_scraper_status, latest_run, start_cloud_worker, stop_cloud_worker
from information_hunters.config import get_settings
from information_hunters.db import get_session_factory, init_db
from information_hunters.models import Job, JobLog, Lead, Worker, utcnow
from information_hunters.secrets import SECRET_NAMES, save_secret, secret_status


class LeadPatch(BaseModel):
    do_not_contact: bool


class JobIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    categories: list[str] = Field(min_length=1)
    regions: list[str] = Field(min_length=1)
    limit_per_search: int = Field(default=8, ge=1, le=100)
    discovery_provider: str = "auto"
    verification_provider: str = "auto"
    contact_fetcher: str = "auto"
    incorporated_after: date | None = None


class SecretIn(BaseModel):
    name: str
    value: str = Field(min_length=1)


def create_app() -> FastAPI:
    app = FastAPI(title="Information Hunters", version="0.1.0")

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    def db() -> Session:
        session = get_session_factory()()
        try:
            yield session
        finally:
            session.close()

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/categories")
    def list_categories() -> dict:
        return {"categories": categories(), "regions": regions()}

    @app.get("/stats")
    def stats(session: Session = Depends(db)) -> dict:
        now = datetime.now(timezone.utc)
        week = now - timedelta(days=7)
        leads = session.query(func.count(Lead.id)).scalar() or 0
        recent = session.query(func.count(Lead.id)).filter(Lead.created_at >= week).scalar() or 0
        with_email = session.query(func.count(Lead.id)).filter(Lead.email.is_not(None), Lead.email != "").scalar() or 0
        with_mobile = session.query(func.count(Lead.id)).filter(Lead.mobile.is_not(None), Lead.mobile != "").scalar() or 0
        no_site = session.query(func.count(Lead.id)).filter(Lead.has_website.is_(False)).scalar() or 0
        high = session.query(func.count(Lead.id)).filter(Lead.priority_score >= 80).scalar() or 0
        active = session.query(func.count(Job.id)).filter(Job.status.in_(["queued", "running", "paused"])).scalar() or 0
        workers = [
            {
                "id": row.id,
                "hostname": row.hostname,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
                "current_job_id": row.current_job_id,
            }
            for row in session.query(Worker).order_by(Worker.last_seen.desc()).all()
        ]
        return {
            "leads": leads,
            "new_leads_7d": recent,
            "with_email": with_email,
            "with_mobile": with_mobile,
            "no_website": no_site,
            "high_priority": high,
            "active_jobs": active,
            "workers": workers,
        }

    @app.get("/leads")
    def list_leads(
        session: Session = Depends(db),
        q: str | None = None,
        category: str | None = None,
        location: str | None = None,
        has_email: bool = False,
        has_mobile: bool = False,
        no_website: bool = False,
        incorporated_after: date | None = None,
        min_priority: int | None = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ) -> dict:
        query = _lead_query(session, q, category, location, has_email, has_mobile, no_website, incorporated_after, min_priority)
        total = query.count()
        rows = query.order_by(Lead.priority_score.desc(), Lead.incorporation_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {"items": [_lead_out(row) for row in rows], "total": total, "page": page, "page_size": page_size}

    @app.get("/leads/export")
    def export_leads(
        session: Session = Depends(db),
        q: str | None = None,
        category: str | None = None,
        location: str | None = None,
        has_email: bool = False,
        has_mobile: bool = False,
        no_website: bool = False,
        incorporated_after: date | None = None,
        min_priority: int | None = None,
        include_suppressed: bool = False,
    ) -> Response:
        query = _lead_query(session, q, category, location, has_email, has_mobile, no_website, incorporated_after, min_priority)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["name", "company_number", "category", "location", "postcode", "phone", "mobile", "email", "website", "has_website", "incorporation_date", "priority_score", "priority_band", "trading_status", "do_not_contact", "verification_notes"]
        )
        for lead in query.order_by(Lead.priority_score.desc()).all():
            if lead.do_not_contact and not include_suppressed:
                continue
            writer.writerow(
                [
                    lead.name,
                    lead.company_number,
                    lead.category,
                    lead.location,
                    lead.postcode,
                    lead.phone or "",
                    lead.mobile or "",
                    lead.email or "",
                    lead.website or "",
                    "yes" if lead.has_website else "no",
                    lead.incorporation_date.isoformat() if lead.incorporation_date else "",
                    lead.priority_score,
                    lead.priority_band,
                    lead.trading_status,
                    "yes" if lead.do_not_contact else "no",
                    lead.verification_notes,
                ]
            )
        return Response(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=information-hunters-leads.csv"},
        )

    @app.get("/leads/{lead_id}")
    def get_lead(lead_id: str, session: Session = Depends(db)) -> dict:
        lead = session.get(Lead, lead_id)
        if lead is None:
            raise HTTPException(404, "Lead not found")
        return _lead_out(lead)

    @app.patch("/leads/{lead_id}")
    def patch_lead(lead_id: str, body: LeadPatch, session: Session = Depends(db)) -> dict:
        lead = session.get(Lead, lead_id)
        if lead is None:
            raise HTTPException(404, "Lead not found")
        lead.do_not_contact = body.do_not_contact
        lead.updated_at = utcnow()
        session.commit()
        return _lead_out(lead)

    @app.post("/leads/purge-synthetic")
    def purge(session: Session = Depends(db)) -> dict:
        deleted = session.query(Lead).filter(Lead.synthetic.is_(True)).delete()
        session.commit()
        return {"deleted": deleted}

    @app.post("/jobs")
    def create_job(body: JobIn, session: Session = Depends(db)) -> dict:
        known_c = {item["id"] for item in categories()}
        known_r = {item["id"] for item in regions()}
        if set(body.categories) - known_c or set(body.regions) - known_r:
            raise HTTPException(400, "Unknown category or region")
        job = Job(
            name=body.name.strip(),
            categories=body.categories,
            regions=body.regions,
            limit_per_search=body.limit_per_search,
            discovery_provider=body.discovery_provider,
            verification_provider=body.verification_provider,
            contact_fetcher=body.contact_fetcher,
            incorporated_after=body.incorporated_after,
            status="queued",
            stage="Queued",
        )
        session.add(job)
        session.commit()
        session.add(JobLog(job_id=job.id, level="info", message="Hunt queued."))
        session.commit()
        return _job_out(job)

    @app.get("/jobs")
    def list_jobs(session: Session = Depends(db)) -> dict:
        rows = session.query(Job).order_by(Job.created_at.desc()).limit(100).all()
        return {"items": [_job_out(row) for row in rows]}

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str, session: Session = Depends(db)) -> dict:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Hunt not found")
        return _job_out(job)

    @app.get("/jobs/{job_id}/logs")
    def job_logs(job_id: str, session: Session = Depends(db)) -> dict:
        if session.get(Job, job_id) is None:
            raise HTTPException(404, "Hunt not found")
        rows = session.query(JobLog).filter(JobLog.job_id == job_id).order_by(JobLog.created_at.asc()).limit(300).all()
        return {"items": [{"id": row.id, "level": row.level, "message": row.message, "created_at": row.created_at.isoformat()} for row in rows]}

    @app.post("/jobs/{job_id}/start")
    def start_job(job_id: str, session: Session = Depends(db)) -> dict:
        job = _require_job(session, job_id)
        if job.status == "running":
            return _job_out(job)
        if job.status in {"completed", "failed", "stopped"}:
            job.checkpoint = None
            job.progress = 0
            job.discovered_count = 0
            job.qualified_count = 0
            job.rejected_count = 0
            job.error = None
            job.finished_at = None
        job.status = "queued"
        job.stage = "Queued"
        session.commit()
        session.add(JobLog(job_id=job.id, level="info", message="Hunt queued to start."))
        session.commit()
        return _job_out(job)

    @app.post("/jobs/{job_id}/pause")
    def pause_job(job_id: str, session: Session = Depends(db)) -> dict:
        job = _require_job(session, job_id)
        if job.status not in {"queued", "running"}:
            raise HTTPException(409, "Only a queued or running hunt can be paused")
        job.status = "paused"
        job.stage = "Paused"
        session.commit()
        return _job_out(job)

    @app.post("/jobs/{job_id}/stop")
    def stop_job(job_id: str, session: Session = Depends(db)) -> dict:
        job = _require_job(session, job_id)
        if job.status in {"completed", "stopped"}:
            return _job_out(job)
        if job.status == "running":
            job.status = "stopping"
            job.stage = "Stopping"
        else:
            job.status = "stopped"
            job.stage = "Stopped"
            job.finished_at = utcnow()
        session.commit()
        return _job_out(job)

    @app.get("/fleet")
    def fleet(session: Session = Depends(db)) -> dict:
        """Scrapers (cloud workers) + bots (pipeline roles), Find-style."""
        return _fleet_payload(session)

    @app.post("/fleet/cloud/start")
    def fleet_cloud_start() -> dict:
        try:
            return start_cloud_worker()
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/fleet/cloud/stop")
    def fleet_cloud_stop() -> dict:
        try:
            return stop_cloud_worker()
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/bots")
    def bots(session: Session = Depends(db)) -> list:
        data = _fleet_payload(session)
        return data["scrapers"] + data["bots"]

    @app.get("/models")
    def models(session: Session = Depends(db)) -> list:
        return list(_fleet_payload(session)["models_by_id"].values())

    @app.get("/settings")
    def settings_view(session: Session = Depends(db)) -> dict:
        settings = get_settings()
        return {
            "demo_mode": settings.demo_mode,
            "database": "postgres" if settings.database_url.startswith("postgresql") else "sqlite",
            "can_edit_secrets": bool(settings.secrets_master_key),
            "secrets": [secret_status(session, name) for name in SECRET_NAMES],
        }

    @app.post("/settings/secrets")
    def put_secret(body: SecretIn, session: Session = Depends(db)) -> dict:
        try:
            save_secret(session, body.name, body.value.strip())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        return secret_status(session, body.name)

    return app


def _fleet_payload(session: Session) -> dict:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    workers = session.query(Worker).order_by(Worker.last_seen.desc()).all()
    live_workers = [
        w
        for w in workers
        if w.last_seen and (now - (w.last_seen if w.last_seen.tzinfo else w.last_seen.replace(tzinfo=timezone.utc))).total_seconds() < 90
    ]
    active_jobs = session.query(func.count(Job.id)).filter(Job.status.in_(["queued", "running"])).scalar() or 0
    running = session.query(func.count(Job.id)).filter(Job.status == "running").scalar() or 0

    def secret_on(name: str) -> tuple[bool, str | None]:
        if not name:
            return True, None
        status = secret_status(session, name)
        hint = f"···{status['last4']}" if status.get("last4") else name
        return bool(status.get("configured")), hint if status.get("configured") else name

    models_by_id: dict[str, dict] = {}
    for mid, meta in MODEL_PROFILES.items():
        env = meta.get("api_key_env") or ""
        if mid == "apify":
            ok_token, hint = secret_on("APIFY_TOKEN")
            ok_actor, _ = secret_on("APIFY_ACTOR_ID")
            connected = ok_token and ok_actor
            hint = hint if ok_token else "APIFY_TOKEN + APIFY_ACTOR_ID"
        elif env:
            connected, hint = secret_on(env)
        else:
            connected, hint = True, None
        models_by_id[mid] = enrich_model(mid, connected, hint)

    # Also expose ScrapingBee as a helper model even if not primary for extract
    if "scrapingbee" in models_by_id:
        ok, hint = secret_on("SCRAPINGBEE_API_KEY")
        models_by_id["scrapingbee"] = enrich_model("scrapingbee", ok, hint)

    def model_for(model_id: str | None) -> dict | None:
        if not model_id:
            return None
        return models_by_id.get(model_id)

    # Scraper statuses — only cloud worker(s) you start/stop
    db_cloud = settings.database_url.startswith("postgresql")
    run = latest_run()
    scrapers = []
    for sid, profile in SCRAPER_PROFILES.items():
        if sid == "github-actions":
            status = cloud_scraper_status(db_cloud=db_cloud, active_jobs=active_jobs)
        else:
            status = "idle"
        agent = build_agent(sid, profile, status=status, model=model_for(profile.get("model_id")))
        if sid == "github-actions":
            if not db_cloud:
                agent["activation"] = {
                    "state": "needs_activate",
                    "label": "Needs cloud DB",
                    "detail": "Point DATABASE_URL at Supabase so the cloud worker shares hunts with this desk.",
                    "key_hint": "DATABASE_URL",
                }
            elif not (settings.github_token or "").strip():
                agent["activation"] = {
                    "state": "needs_activate",
                    "label": "Needs GITHUB_TOKEN",
                    "detail": "Add a GitHub PAT (Actions write) to .env as GITHUB_TOKEN to use Start / Stop here.",
                    "key_hint": "GITHUB_TOKEN",
                }
            elif status == "live":
                agent["activation"] = {
                    "state": "connected",
                    "label": "Running",
                    "detail": "Cloud worker run is in progress. Bots process queued hunts automatically.",
                    "key_hint": None,
                }
            else:
                agent["activation"] = {
                    "state": "connected",
                    "label": "Ready",
                    "detail": "Press Start to run now, or wait for the 15-minute schedule. Device can be off.",
                    "key_hint": None,
                }
            agent["cloud_run"] = run
        scrapers.append(agent)

    # Bot statuses from secrets + whether hunts are running
    bots = []
    for bid, profile in BOT_PROFILES.items():
        model = model_for(profile.get("model_id"))
        env = (MODEL_PROFILES.get(profile.get("model_id") or "", {}) or {}).get("api_key_env") or ""
        if bid == "score" or bid == "extract":
            # extract works without key (direct); score always local
            status = "live" if running else "ready"
        elif env and model and not model.get("connected"):
            status = "paused"
        elif running:
            status = "live"
        elif model and model.get("connected"):
            status = "ready"
        elif settings.demo_mode:
            status = "ready"
        else:
            status = "idle"
        # Prefer ScrapingBee model detail on extract when that key is set
        if bid == "extract" and models_by_id.get("scrapingbee", {}).get("connected"):
            model = models_by_id["scrapingbee"]
        bots.append(build_agent(bid, profile, status=status, model=model))

    scrapers.sort(key=lambda row: (-row["importance"], row["name"]))
    bots.sort(key=lambda row: (-row["importance"], row["name"]))

    return {
        "scrapers": scrapers,
        "bots": bots,
        "models_by_id": models_by_id,
        "workers": [
            {
                "id": w.id,
                "hostname": w.hostname,
                "last_seen": w.last_seen.isoformat() if w.last_seen else None,
                "current_job_id": w.current_job_id,
                "live": w in live_workers,
            }
            for w in workers
        ],
        "active_jobs": active_jobs,
        "database": "postgres" if db_cloud else "sqlite",
        "cloud_run": run,
        "can_start_cloud": bool((settings.github_token or "").strip()) and db_cloud,
    }


def _require_job(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Hunt not found")
    return job


def _lead_query(session, q, category, location, has_email, has_mobile, no_website, incorporated_after, min_priority):
    query = session.query(Lead)
    if q:
        safe = q.replace("%", "")[:80].lower()
        query = query.filter(func.lower(Lead.name).like(f"%{safe}%"))
    if category:
        query = query.filter(Lead.category == category)
    if location:
        query = query.filter(Lead.location == location)
    if has_email:
        query = query.filter(Lead.email.is_not(None), Lead.email != "")
    if has_mobile:
        query = query.filter(Lead.mobile.is_not(None), Lead.mobile != "")
    if no_website:
        query = query.filter(Lead.has_website.is_(False))
    if incorporated_after:
        query = query.filter(Lead.incorporation_date >= incorporated_after)
    if min_priority is not None:
        query = query.filter(Lead.priority_score >= min_priority)
    return query


def _lead_out(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "company_number": lead.company_number,
        "name": lead.name,
        "location": lead.location,
        "address": lead.address,
        "postcode": lead.postcode,
        "category": lead.category,
        "sic_codes": lead.sic_codes or [],
        "sic_labels": lead.sic_labels or [],
        "phone": lead.phone,
        "mobile": lead.mobile,
        "email": lead.email,
        "website": lead.website,
        "has_website": lead.has_website,
        "incorporation_date": lead.incorporation_date.isoformat() if lead.incorporation_date else None,
        "company_status": lead.company_status,
        "trading_status": lead.trading_status,
        "priority_score": lead.priority_score,
        "priority_band": lead.priority_band,
        "priority_reasons": lead.priority_reasons or [],
        "sources": lead.sources or [],
        "verification_notes": lead.verification_notes,
        "do_not_contact": lead.do_not_contact,
        "synthetic": lead.synthetic,
        "job_id": lead.job_id,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


def _job_out(job: Job) -> dict:
    return {
        "id": job.id,
        "name": job.name,
        "categories": job.categories or [],
        "regions": job.regions or [],
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "limit_per_search": job.limit_per_search,
        "discovery_provider": job.discovery_provider,
        "verification_provider": job.verification_provider,
        "contact_fetcher": job.contact_fetcher,
        "incorporated_after": job.incorporated_after.isoformat() if job.incorporated_after else None,
        "discovered_count": job.discovered_count,
        "qualified_count": job.qualified_count,
        "rejected_count": job.rejected_count,
        "error": job.error,
        "worker_id": job.worker_id,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
