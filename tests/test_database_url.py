"""Supabase URLs are normalised onto the psycopg driver. SQLite remains the default."""

from information_hunters.config import normalize_database_url


def test_supabase_uri_uses_psycopg_and_ssl():
    url = normalize_database_url("postgresql://postgres.abc:secret@aws-0-eu-west-2.pooler.supabase.com:5432/postgres")
    assert url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in url
    assert "secret" in url

    legacy = normalize_database_url("postgres://postgres:secret@db.abc.supabase.co:5432/postgres")
    assert legacy.startswith("postgresql+psycopg://")
    assert "sslmode=require" in legacy

    sqlite = normalize_database_url("sqlite:///./information_hunters.db")
    assert sqlite == "sqlite:///./information_hunters.db"


def test_supabase_db_url_overrides_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./should-not-be-used.db")
    monkeypatch.setenv("SUPABASE_DB_URL", f"sqlite:///{tmp_path}/supa.db")
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    from information_hunters.config import get_settings
    from information_hunters.db import init_db, reset_engine, session_scope
    from information_hunters.models import ActivityEvent

    get_settings.cache_clear()
    reset_engine()
    init_db()
    with session_scope() as session:
        session.add(ActivityEvent(message="Searching Companies House for plumbers in Leeds", kind="searching"))
        session.commit()
        stored = session.query(ActivityEvent).one()
        assert "Leeds" in stored.message
    assert (tmp_path / "supa.db").exists()
    assert not (tmp_path / "should-not-be-used.db").exists()
    reset_engine()
    get_settings.cache_clear()
