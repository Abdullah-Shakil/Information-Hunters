import pytest
from fastapi.testclient import TestClient


class _AuthedClient:
    """Sends the test bearer token unless a call sets X-Test-No-Auth."""

    def __init__(self, inner: TestClient):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def request(self, method, url, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        if headers.pop("X-Test-No-Auth", None):
            headers.pop("Authorization", None)
        else:
            headers.setdefault("Authorization", "Bearer test-token")
        return self._inner.request(method, url, headers=headers, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("SECRETS_MASTER_KEY", "test-master-key")
    monkeypatch.setenv("DEMO_STEP_DELAY_MS", "0")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-token")
    from information_hunters.config import get_settings
    from information_hunters.db import reset_engine

    get_settings.cache_clear()
    reset_engine()
    from information_hunters.ops import reset_http_client_factory

    reset_http_client_factory()
    from information_hunters.api import create_app

    with TestClient(create_app()) as test_client:
        yield _AuthedClient(test_client)
    reset_http_client_factory()
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture()
def auth_header():
    return {"Authorization": "Bearer test-token"}
