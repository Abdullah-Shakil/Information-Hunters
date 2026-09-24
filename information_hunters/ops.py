"""Small shared types for host calls and connection tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import httpx

_factory: Callable[[], httpx.Client] | None = None


@dataclass
class ActionResult:
    ok: bool
    status: str
    detail: str
    remote_id: str | None = None
    usage: dict | None = None


def set_http_client_factory(factory: Callable[[], httpx.Client] | None) -> None:
    global _factory
    _factory = factory


def reset_http_client_factory() -> None:
    global _factory
    _factory = None


@contextmanager
def open_client() -> Iterator[httpx.Client]:
    if _factory is not None:
        client = _factory()
        try:
            yield client
        finally:
            client.close()
        return
    with httpx.Client(timeout=45) as client:
        yield client


def read_body(response: httpx.Response):
    if not response.content:
        return {}
    try:
        return response.json()
    except Exception:
        return {"text": response.text[:300]}


def error_text(payload) -> str:
    if isinstance(payload, str):
        return payload[:400]
    if not isinstance(payload, dict):
        return str(payload)[:400]
    err = payload.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("status") or err)[:400]
    if isinstance(err, str):
        return str(payload.get("error_description") or err)[:400]
    message = payload.get("message") or payload.get("text")
    if message:
        return str(message)[:400]
    return str(payload)[:400]


_QUOTA_PHRASES = (
    "quota exceeded",
    "resource_exhausted",
    "resource exhausted",
    "monthly usage",
    "usage limit",
    "out of host capacity",
    "limitexceeded",
    "free instance hours",
    "insufficient credits",
    "credits exhausted",
    "credit limit",
    "exceeded your included",
    "hard limit",
    "plan limit",
    "payment required",
    "usage credits",
    "monthly limit",
    "credits are exhausted",
)


def is_quota(status_code: int, payload) -> bool:
    if status_code == 402:
        return True
    text = error_text(payload).lower()
    if any(phrase in text for phrase in _QUOTA_PHRASES):
        return True
    if status_code == 429 and "rate" not in text:
        return True
    return False


def failure_status(status_code: int, payload) -> str:
    if is_quota(status_code, payload):
        return "quota_exhausted"
    return "error"


def scrub(detail: str, secrets: list[str]) -> str:
    cleaned = detail or ""
    for secret in secrets:
        if secret and len(secret) >= 6:
            cleaned = cleaned.replace(secret, "•••")
    return cleaned[:500]
