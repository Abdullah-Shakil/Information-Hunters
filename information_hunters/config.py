"""Runtime configuration from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./information_hunters.db"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_db_url: str = ""
    internal_api_token: str = "dev-internal-token"
    demo_mode: bool = True
    secrets_master_key: str = ""
    companies_house_api_key: str = ""
    google_places_api_key: str = ""
    scrapingbee_api_key: str = ""
    brightdata_api_token: str = ""
    brightdata_zone: str = ""
    apify_token: str = ""
    apify_actor_id: str = ""
    contact_fetcher: str = "auto"
    worker_id: str = ""
    host_id: str = ""
    poll_interval_seconds: float = 2.0
    heartbeat_stale_seconds: int = 60
    companies_house_rps: float = 2.0
    demo_step_delay_ms: int = 120
    worker_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def resolved_database_url(self) -> str:
        raw = (self.supabase_db_url or "").strip() or self.database_url
        return normalize_database_url(raw)


def normalize_database_url(url: str) -> str:
    """Accept Supabase's postgres URI and point SQLAlchemy at the psycopg driver."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    if ("supabase.co" in url or "pooler.supabase.com" in url) and "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
