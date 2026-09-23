"""Persistence models. SQLite locally; Postgres via DATABASE_URL."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    location: Mapped[str] = mapped_column(String(120), default="", index=True)
    address: Mapped[str] = mapped_column(Text, default="")
    postcode: Mapped[str] = mapped_column(String(16), default="")
    category: Mapped[str] = mapped_column(String(64), default="", index=True)
    sic_codes: Mapped[list] = mapped_column(JSON, default=list)
    sic_labels: Mapped[list] = mapped_column(JSON, default=list)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website: Mapped[str | None] = mapped_column(String(400), nullable=True)
    has_website: Mapped[bool] = mapped_column(Boolean, default=False)
    incorporation_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    company_status: Mapped[str] = mapped_column(String(32), default="active")
    trading_status: Mapped[str] = mapped_column(String(32), default="verified_active")
    priority_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    priority_band: Mapped[str] = mapped_column(String(2), default="D")
    priority_reasons: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    verification_notes: Mapped[str] = mapped_column(Text, default="")
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    categories: Mapped[list] = mapped_column(JSON, default=list)
    regions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(200), default="Queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    limit_per_search: Mapped[int] = mapped_column(Integer, default=8)
    discovery_provider: Mapped[str] = mapped_column(String(40), default="auto")
    verification_provider: Mapped[str] = mapped_column(String(40), default="auto")
    contact_fetcher: Mapped[str] = mapped_column(String(40), default="auto")
    incorporated_after: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    discovered_count: Mapped[int] = mapped_column(Integer, default=0)
    qualified_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    checkpoint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(200), default="")
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    current_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Secret(Base):
    __tablename__ = "secrets"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
