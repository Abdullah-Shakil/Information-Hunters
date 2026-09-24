"""Trigger / cancel the GitHub Actions cloud worker from the desk."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from information_hunters.config import get_settings


def _repo_parts() -> tuple[str, str]:
    settings = get_settings()
    repo = (settings.github_repo or "Abdullah-Shakil/Information-Hunters").strip()
    owner, _, name = repo.partition("/")
    if not owner or not name:
        raise ValueError("GITHUB_REPO must look like owner/name")
    return owner, name


def _token() -> str:
    token = (get_settings().github_token or "").strip()
    if not token:
        raise RuntimeError(
            "Set GITHUB_TOKEN in .env (PAT with Actions write) so Start can run the cloud worker."
        )
    return token


def _request(method: str, path: str, body: dict | None = None) -> Any:
    owner, name = _repo_parts()
    url = f"https://api.github.com/repos/{owner}/{name}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {_token()}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "information-hunters-desk",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return {"ok": True, "status": resp.status}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"GitHub API {exc.code}: {detail}") from exc


def workflow_file() -> str:
    return (get_settings().github_workflow or "cloud-worker.yml").strip()


def latest_run() -> dict[str, Any] | None:
    """Best-effort latest Cloud worker run (None if token missing or API fails)."""
    try:
        file = workflow_file()
        payload = _request("GET", f"/actions/workflows/{file}/runs?per_page=1")
    except (RuntimeError, ValueError, urllib.error.URLError):
        return None
    runs = (payload or {}).get("workflow_runs") or []
    if not runs:
        return None
    run = runs[0]
    return {
        "id": run.get("id"),
        "status": run.get("status"),  # queued | in_progress | completed
        "conclusion": run.get("conclusion"),
        "html_url": run.get("html_url"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
    }


def start_cloud_worker() -> dict[str, Any]:
    file = workflow_file()
    branch = (get_settings().github_ref or "main").strip() or "main"
    _request("POST", f"/actions/workflows/{file}/dispatches", {"ref": branch})
    return {"started": True, "workflow": file, "ref": branch, "run": latest_run()}


def stop_cloud_worker() -> dict[str, Any]:
    """Cancel queued / in-progress runs of the cloud worker workflow."""
    file = workflow_file()
    payload = _request(
        "GET",
        f"/actions/workflows/{file}/runs?status=in_progress&per_page=10",
    )
    queued = _request(
        "GET",
        f"/actions/workflows/{file}/runs?status=queued&per_page=10",
    )
    runs = list((payload or {}).get("workflow_runs") or []) + list((queued or {}).get("workflow_runs") or [])
    cancelled: list[int] = []
    for run in runs:
        run_id = run.get("id")
        if not run_id:
            continue
        try:
            _request("POST", f"/actions/runs/{run_id}/cancel")
            cancelled.append(int(run_id))
        except RuntimeError:
            continue
    return {"stopped": True, "cancelled_run_ids": cancelled, "run": latest_run()}


def cloud_scraper_status(*, db_cloud: bool, active_jobs: int) -> str:
    run = latest_run()
    if run and run.get("status") in {"queued", "in_progress", "waiting", "requested", "pending"}:
        return "live"
    if not db_cloud:
        return "paused"
    if active_jobs:
        return "ready"
    return "ready"
