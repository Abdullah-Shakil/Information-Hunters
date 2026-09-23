"""Refuse fetches that are not public http(s) pages."""

import ipaddress
import socket
from urllib.parse import urlparse

from information_hunters.providers.base import ProviderError

SOCIAL_HOSTS = (
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "fb.com",
)


class UnsafeUrl(ProviderError):
    pass


def assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrl("Only public http(s) URLs can be fetched")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeUrl("URL is missing a host")
    if host in {"localhost"} or host.endswith(".local") or host.endswith(".internal"):
        raise UnsafeUrl("Local hosts are blocked")
    if any(host == blocked or host.endswith("." + blocked) for blocked in SOCIAL_HOSTS):
        raise UnsafeUrl("Social and login sites are not fetched")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if not ip.is_global:
            raise UnsafeUrl("Non-public addresses are blocked")
        return
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeUrl("Could not resolve host") from exc
    for info in infos:
        resolved = ipaddress.ip_address(info[4][0])
        if not resolved.is_global:
            raise UnsafeUrl("Non-public addresses are blocked")


def usable_website(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return None
    if any(host == blocked or host.endswith("." + blocked) for blocked in SOCIAL_HOSTS):
        return None
    return url.strip()
