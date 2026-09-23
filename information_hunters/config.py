"""Runtime configuration from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./information_hunters.db"
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
    poll_interval_seconds: float = 2.0
    heartbeat_stale_seconds: int = 60
    companies_house_rps: float = 2.0
    demo_step_delay_ms: int = 120
    worker_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
