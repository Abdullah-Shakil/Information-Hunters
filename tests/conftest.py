import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-token")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("SECRETS_MASTER_KEY", "test-master-key")
    monkeypatch.setenv("DEMO_STEP_DELAY_MS", "0")
    from information_hunters.config import get_settings
    from information_hunters.db import reset_engine

    get_settings.cache_clear()
    reset_engine()
    from information_hunters.ops import reset_http_client_factory

    reset_http_client_factory()
    from information_hunters.api import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    reset_http_client_factory()
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture()
def auth_header():
    return {"Authorization": "Bearer test-token"}
