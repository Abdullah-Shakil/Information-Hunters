"""Desk Start/Stop for the GitHub Actions cloud worker.

This is a thin wrapper around GitHubActionsHost so the Scrapers page and the
Hosts page share one client, one workflow file, and the encrypted key store.
"""

from __future__ import annotations

from typing import Any

from information_hunters.config import get_settings
from information_hunters.hosts.catalog import get_spec
from information_hunters.hosts.github_actions import GitHubActionsHost, peek_run
from information_hunters.hosts.service import HostRequestError, ensure_host, resolved_values, start_host, stop_host
from information_hunters.secrets import resolve_secret

_ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending", "running"}


def seed_github_host(session) -> None:
    """Fill empty Hosts fields from GITHUB_REPO=owner/name and the other GITHUB_* env vars."""
    spec = get_spec("github_actions")
    if spec is None:
        raise RuntimeError("GitHub Actions host is not in the catalogue")
    host = ensure_host(session, spec)
    settings = get_settings()
    config = dict(host.config or {})
    repo = (settings.github_repo or "").strip()
    owner, _, name = repo.partition("/")
    changed = False
    if not str(config.get("GITHUB_OWNER") or "").strip() and owner and "/" not in owner and " " not in owner:
        config["GITHUB_OWNER"] = owner
        changed = True
    if not str(config.get("GITHUB_REPO") or "").strip() and name and "/" not in name and " " not in name:
        config["GITHUB_REPO"] = name
        changed = True
    if not str(config.get("GITHUB_WORKFLOW") or "").strip():
        config["GITHUB_WORKFLOW"] = (settings.github_workflow or "cloud-worker.yml").strip() or "cloud-worker.yml"
        changed = True
    if not str(config.get("GITHUB_REF") or "").strip():
        config["GITHUB_REF"] = (settings.github_ref or "main").strip() or "main"
        changed = True
    if changed:
        host.config = config
        session.commit()


def github_ready(session) -> bool:
    seed_github_host(session)
    spec = get_spec("github_actions")
    host = ensure_host(session, spec)
    values = resolved_values(session, host, spec)
    return bool(values.get("GITHUB_TOKEN") and values.get("GITHUB_OWNER") and values.get("GITHUB_REPO"))


def latest_run(session) -> dict[str, Any] | None:
    if not (resolve_secret(session, "GITHUB_TOKEN") or "").strip():
        return None
    seed_github_host(session)
    spec = get_spec("github_actions")
    host = ensure_host(session, spec)
    return peek_run(resolved_values(session, host, spec))


def cloud_scraper_status(session, *, db_cloud: bool, active_jobs: int) -> str:
    run = latest_run(session)
    if run and run.get("status") in _ACTIVE:
        return "live"
    if not db_cloud:
        return "paused"
    if active_jobs:
        return "ready"
    return "ready"


def start_cloud_worker(session) -> dict[str, Any]:
    seed_github_host(session)
    try:
        host = start_host(session, "github_actions")
    except HostRequestError as exc:
        raise RuntimeError(exc.message) from exc
    if host.get("status") != "running":
        detail = host.get("status_detail") or host.get("last_error") or "Could not start the cloud worker"
        raise RuntimeError(detail)
    return {
        "started": True,
        "status": host.get("status"),
        "detail": host.get("status_detail"),
        "remote_id": host.get("remote_id"),
        "workflow": (get_settings().github_workflow or "cloud-worker.yml"),
        "run": latest_run(session),
    }


def stop_cloud_worker(session) -> dict[str, Any]:
    seed_github_host(session)
    try:
        host = stop_host(session, "github_actions")
    except HostRequestError as exc:
        raise RuntimeError(exc.message) from exc
    if host.get("status") not in {"stopped", "unconfigured"}:
        detail = host.get("status_detail") or host.get("last_error") or "Could not stop the cloud worker"
        raise RuntimeError(detail)
    return {
        "stopped": True,
        "status": host.get("status"),
        "detail": host.get("status_detail"),
        "run": latest_run(session),
    }


# Re-export so a caller can construct the adapter without a second HTTP stack.
CloudWorkerHost = GitHubActionsHost
