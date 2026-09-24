"""Start and stop the repo's GitHub Actions hunt workflow."""

from __future__ import annotations

from urllib.parse import quote

from information_hunters.ops import ActionResult, error_text, failure_status, open_client, read_body

API = "https://api.github.com"
_ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending", "action_required"}


class GitHubActionsHost:
    provider = "github_actions"

    def test(self, values: dict) -> ActionResult:
        owner, repo = _slug(values.get("GITHUB_OWNER", "")), _slug(values.get("GITHUB_REPO", ""))
        if not owner or not repo or not values.get("GITHUB_TOKEN"):
            return ActionResult(False, "error", "GitHub owner, repository, and token are required.")
        with open_client() as client:
            user = client.get(f"{API}/user", headers=_headers(values["GITHUB_TOKEN"]))
            if user.status_code >= 400:
                return ActionResult(False, failure_status(user.status_code, read_body(user)), f"GitHub rejected the token: {error_text(read_body(user))}")
            user_body = read_body(user)
            login = user_body.get("login", "") if isinstance(user_body, dict) else ""
            repo_response = client.get(f"{API}/repos/{owner}/{repo}", headers=_headers(values["GITHUB_TOKEN"]))
            if repo_response.status_code >= 400:
                return ActionResult(False, "error", f"Could not open {owner}/{repo}: {error_text(read_body(repo_response))}")
            private = bool((read_body(repo_response) or {}).get("private")) if isinstance(read_body(repo_response), dict) else True
            usage = _billing(client, values["GITHUB_TOKEN"], login, private)
            if usage.get("exhausted"):
                return ActionResult(False, "quota_exhausted", usage["summary"], usage=usage)
            return ActionResult(True, "stopped", usage.get("summary") or f"Token works for {login}.", usage=usage)

    def start(self, values: dict) -> ActionResult:
        checked = self.test(values)
        if not checked.ok:
            return checked
        owner, repo = _slug(values["GITHUB_OWNER"]), _slug(values["GITHUB_REPO"])
        workflow = _slug(values.get("GITHUB_WORKFLOW") or "cloud-worker.yml")
        ref = (values.get("GITHUB_REF") or "main").strip()
        if not owner or not repo or not workflow or not ref or " " in ref:
            return ActionResult(False, "error", "GitHub owner, repository, workflow, or ref is not valid.")
        with open_client() as client:
            headers = _headers(values["GITHUB_TOKEN"])
            schedule = _set_schedule(client, headers, owner, repo, True)
            already = _active_run_id(client, headers, owner, repo, workflow)
            if already:
                return ActionResult(True, "running", "A cloud worker run is already in progress." + schedule, remote_id=already, usage=checked.usage)
            dispatched = client.post(
                f"{API}/repos/{owner}/{repo}/actions/workflows/{quote(workflow)}/dispatches",
                headers=headers,
                json={"ref": ref},
            )
            if dispatched.status_code >= 400:
                payload = read_body(dispatched)
                status = failure_status(dispatched.status_code, payload)
                return ActionResult(False, status, f"GitHub did not start the workflow: {error_text(payload)}", usage=checked.usage)
            run_id = _active_run_id(client, headers, owner, repo, workflow)
            detail = "Workflow dispatched. It runs queued hunts, then the 15-minute schedule starts another run while it is enabled." + schedule
            if run_id is None:
                detail += " The run id was not listed yet; Stop will cancel whichever run is in progress."
            return ActionResult(True, "running", detail, remote_id=run_id, usage=checked.usage)

    def stop(self, values: dict, remote_id: str | None) -> ActionResult:
        owner, repo = _slug(values.get("GITHUB_OWNER", "")), _slug(values.get("GITHUB_REPO", ""))
        workflow = _slug(values.get("GITHUB_WORKFLOW") or "cloud-worker.yml")
        if not owner or not repo or not values.get("GITHUB_TOKEN"):
            return ActionResult(False, "error", "GitHub owner, repository, and token are required.")
        with open_client() as client:
            headers = _headers(values["GITHUB_TOKEN"])
            schedule = _set_schedule(client, headers, owner, repo, False)
            run_ids = [remote_id] if remote_id else []
            if not run_ids:
                run_ids = _active_run_ids(client, headers, owner, repo, workflow)
            if not run_ids:
                return ActionResult(True, "stopped", "No GitHub Actions run was in progress." + schedule)
            errors = []
            for run_id in run_ids:
                response = client.post(f"{API}/repos/{owner}/{repo}/actions/runs/{run_id}/cancel", headers=headers)
                if response.status_code >= 400:
                    errors.append(error_text(read_body(response)))
            if errors:
                return ActionResult(False, "error", "GitHub did not cancel the run: " + "; ".join(errors))
            return ActionResult(True, "stopped", "Cancellation requested. The runner stops within a minute." + schedule)

    def status(self, values: dict, remote_id: str | None) -> ActionResult:
        owner, repo = _slug(values.get("GITHUB_OWNER", "")), _slug(values.get("GITHUB_REPO", ""))
        workflow = _slug(values.get("GITHUB_WORKFLOW") or "cloud-worker.yml")
        if not owner or not repo or not values.get("GITHUB_TOKEN"):
            return ActionResult(False, "error", "GitHub owner, repository, and token are required.")
        with open_client() as client:
            headers = _headers(values["GITHUB_TOKEN"])
            user = read_body(client.get(f"{API}/user", headers=headers))
            login = user.get("login", "") if isinstance(user, dict) else ""
            repo_body = read_body(client.get(f"{API}/repos/{owner}/{repo}", headers=headers))
            private = bool(repo_body.get("private")) if isinstance(repo_body, dict) else True
            usage = _billing(client, values["GITHUB_TOKEN"], login, private)
            if remote_id:
                run = read_body(client.get(f"{API}/repos/{owner}/{repo}/actions/runs/{remote_id}", headers=headers))
                state = _run_state(run if isinstance(run, dict) else {})
            else:
                state = "running" if _active_run_ids(client, headers, owner, repo, workflow) else "stopped"
            if usage.get("exhausted") and state != "running":
                return ActionResult(False, "quota_exhausted", usage["summary"], remote_id=remote_id, usage=usage)
            detail = usage.get("summary") or "GitHub status read."
            return ActionResult(True, state, detail, remote_id=remote_id, usage=usage)


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "information-hunters",
    }


def _slug(value: str) -> str:
    text = (value or "").strip()
    if not text or "/" in text or ".." in text or " " in text:
        return ""
    return text


def _billing(client, token: str, login: str, private: bool) -> dict:
    if not private:
        return {"used": None, "limit": None, "unit": "minutes", "exhausted": False, "summary": "Public repository: Actions minutes are free. Private repos get 2,000 minutes/month."}
    if not login:
        return {"summary": "Could not read Actions billing with this token. A rejected run is how GitHub reports exhausted minutes.", "exhausted": False}
    response = client.get(f"{API}/users/{quote(login)}/settings/billing/actions", headers=_headers(token))
    if response.status_code >= 400:
        return {"summary": "This token cannot read Actions billing. Quota is marked if GitHub rejects the run for minutes.", "exhausted": False}
    body = read_body(response)
    if not isinstance(body, dict):
        return {"summary": "Actions billing response was not readable.", "exhausted": False}
    used = body.get("total_minutes_used")
    included = body.get("included_minutes")
    exhausted = isinstance(used, (int, float)) and isinstance(included, (int, float)) and included > 0 and used >= included
    summary = f"{used} of {included} private-repo minutes used this month."
    if exhausted:
        summary += " Free minutes are used up, so this host is marked quota exhausted."
    return {"used": used, "limit": included, "unit": "minutes", "exhausted": exhausted, "summary": summary}


def _runs(client, headers, owner, repo, workflow) -> list[dict]:
    response = client.get(
        f"{API}/repos/{owner}/{repo}/actions/workflows/{quote(workflow)}/runs",
        headers=headers,
        params={"per_page": 5},
    )
    body = read_body(response)
    items = body.get("workflow_runs") if isinstance(body, dict) else None
    return [item for item in items or [] if isinstance(item, dict)]


def _active_run_ids(client, headers, owner, repo, workflow) -> list[str]:
    return [str(item["id"]) for item in _runs(client, headers, owner, repo, workflow) if item.get("status") in _ACTIVE and item.get("id")]


def _active_run_id(client, headers, owner, repo, workflow) -> str | None:
    found = _active_run_ids(client, headers, owner, repo, workflow)
    return found[0] if found else None


def _run_state(run: dict) -> str:
    status = run.get("status") or ""
    if status in _ACTIVE:
        return "running"
    return "stopped"


def _set_schedule(client, headers, owner: str, repo: str, enabled: bool) -> str:
    """Turn the cloud-worker cron on or off via the CLOUD_WORKER_ENABLED repository variable.

    The workflow runs when the variable is unset or true, and skips when it is false.
    A token that cannot write Actions variables still starts or cancels the current run.
    """
    name = "CLOUD_WORKER_ENABLED"
    body = {"name": name, "value": "true" if enabled else "false"}
    try:
        patched = client.patch(f"{API}/repos/{owner}/{repo}/actions/variables/{name}", headers=headers, json=body)
        if patched.status_code == 404:
            created = client.post(f"{API}/repos/{owner}/{repo}/actions/variables", headers=headers, json=body)
            if created.status_code >= 400:
                return " The 15-minute schedule was not changed; this token may not be allowed to write Actions variables, so the cron can start another run."
        elif patched.status_code >= 400:
            return " The 15-minute schedule was not changed; this token may not be allowed to write Actions variables, so the cron can start another run."
    except Exception:
        return " The 15-minute schedule was not changed, so the cron can start another run."
    if enabled:
        return " The 15-minute schedule is on."
    return " The 15-minute schedule stays off until you press Start."


def peek_run(values: dict) -> dict | None:
    """Latest workflow run for the desk. None when credentials are missing or GitHub cannot be read."""
    owner, repo = _slug(values.get("GITHUB_OWNER", "")), _slug(values.get("GITHUB_REPO", ""))
    workflow = _slug(values.get("GITHUB_WORKFLOW") or "cloud-worker.yml")
    token = (values.get("GITHUB_TOKEN") or "").strip()
    if not owner or not repo or not workflow or not token:
        return None
    try:
        with open_client() as client:
            runs = _runs(client, _headers(token), owner, repo, workflow)
    except Exception:
        return None
    if not runs:
        return None
    run = runs[0]
    return {
        "id": run.get("id"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "html_url": run.get("html_url"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
    }
