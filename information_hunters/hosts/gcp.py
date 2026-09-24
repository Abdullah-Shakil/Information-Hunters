"""Google Cloud Run Jobs plus Cloud Scheduler, using a service account JSON key."""

from __future__ import annotations

import base64

from information_hunters.hosts.signing import gcp_assertion, parse_service_account
from information_hunters.ops import ActionResult, error_text, failure_status, open_client, read_body

_USAGE = {
    "summary": "Google does not report remaining free-tier seconds on this API. Jobs stay free for the first 240,000 vCPU-seconds and 450,000 GiB-seconds each month in a US region. Scheduler stays free for 3 jobs per billing account. A quota response marks this host exhausted.",
    "unit": "vCPU-seconds",
}


class GoogleCloudRunHost:
    provider = "gcp_cloud_run"

    def test(self, values: dict) -> ActionResult:
        try:
            account, project, region, job = _identity(values)
        except ValueError as exc:
            return ActionResult(False, "error", str(exc))
        with open_client() as client:
            token, failure = _token(client, account)
            if failure:
                return failure
            response = client.get(_job_url(project, region, job), headers=_auth(token))
            payload = read_body(response)
            if response.status_code == 404:
                return ActionResult(False, "error", "The token works, but that Cloud Run job does not exist yet. Deploy it once with the README command.")
            if response.status_code >= 400:
                return ActionResult(False, failure_status(response.status_code, payload), f"Cloud Run rejected the check: {error_text(payload)}", usage=_USAGE)
            return ActionResult(True, "stopped", f"Cloud Run job {job} is reachable. {_USAGE['summary']}", usage=_USAGE)

    def start(self, values: dict) -> ActionResult:
        try:
            account, project, region, job = _identity(values)
        except ValueError as exc:
            return ActionResult(False, "error", str(exc))
        scheduler = _segment(values.get("GCP_SCHEDULER_JOB") or "information-hunters-tick", "Scheduler job id")
        with open_client() as client:
            token, failure = _token(client, account)
            if failure:
                return failure
            note = _ensure_scheduler(client, token, account, project, region, job, scheduler)
            if note.startswith("quota:"):
                return ActionResult(False, "quota_exhausted", note[6:], usage=_USAGE)
            response = client.post(_job_url(project, region, job) + ":run", headers=_auth(token), json={})
            payload = read_body(response)
            if response.status_code >= 400:
                status = failure_status(response.status_code, payload)
                return ActionResult(False, status, f"Cloud Run did not start: {error_text(payload)} {note}".strip(), usage=_USAGE)
            execution = _execution_name(payload)
            detail = "Cloud Run job started. " + note
            return ActionResult(True, "running", detail.strip(), remote_id=execution, usage=_USAGE)

    def stop(self, values: dict, remote_id: str | None) -> ActionResult:
        try:
            account, project, region, job = _identity(values)
        except ValueError as exc:
            return ActionResult(False, "error", str(exc))
        scheduler = _segment(values.get("GCP_SCHEDULER_JOB") or "information-hunters-tick", "Scheduler job id")
        with open_client() as client:
            token, failure = _token(client, account)
            if failure:
                return failure
            headers = _auth(token)
            pause = client.post(_scheduler_url(project, region, scheduler) + ":pause", headers=headers)
            pause_note = "Scheduler paused." if pause.status_code < 400 else f"Scheduler pause: {error_text(read_body(pause))}"
            names = [remote_id] if remote_id else _running_executions(client, headers, project, region, job)
            errors = []
            for name in names:
                if not name:
                    continue
                response = client.post(f"https://run.googleapis.com/v2/{name}:cancel", headers=headers)
                if response.status_code >= 400:
                    errors.append(error_text(read_body(response)))
            if errors:
                return ActionResult(False, "error", "Could not cancel the execution: " + "; ".join(errors))
            if not names:
                pause_note += " No execution was running."
            return ActionResult(True, "stopped", pause_note)

    def status(self, values: dict, remote_id: str | None) -> ActionResult:
        try:
            account, project, region, job = _identity(values)
        except ValueError as exc:
            return ActionResult(False, "error", str(exc))
        with open_client() as client:
            token, failure = _token(client, account)
            if failure:
                return failure
            headers = _auth(token)
            if remote_id:
                response = client.get(f"https://run.googleapis.com/v2/{remote_id}", headers=headers)
                payload = read_body(response)
                if response.status_code >= 400:
                    return ActionResult(False, failure_status(response.status_code, payload), error_text(payload), usage=_USAGE)
                running = not (isinstance(payload, dict) and payload.get("completionTime"))
                return ActionResult(running, "running" if running else "stopped", _USAGE["summary"], remote_id=remote_id, usage=_USAGE)
            names = _running_executions(client, headers, project, region, job)
            running = bool(names)
            return ActionResult(running, "running" if running else "stopped", _USAGE["summary"], remote_id=names[0] if names else None, usage=_USAGE)


def _identity(values: dict):
    account = parse_service_account(values.get("GCP_SERVICE_ACCOUNT_JSON") or "")
    project = _segment(values.get("GCP_PROJECT_ID", ""), "Project id")
    region = _segment(values.get("GCP_REGION", ""), "Region")
    job = _segment(values.get("GCP_JOB_NAME") or "information-hunters", "Job name")
    return account, project, region, job


def _segment(value: str, label: str) -> str:
    text = (value or "").strip()
    if not text or any(char in text for char in "/ ?#"):
        raise ValueError(f"{label} is not valid.")
    return text


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _job_url(project: str, region: str, job: str) -> str:
    return f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job}"


def _scheduler_url(project: str, region: str, name: str) -> str:
    return f"https://cloudscheduler.googleapis.com/v1/projects/{project}/locations/{region}/jobs/{name}"


def _token(client, account: dict) -> tuple[str, ActionResult | None]:
    response = client.post(
        "https://oauth2.googleapis.com/token",
        data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": gcp_assertion(account)},
    )
    payload = read_body(response)
    if response.status_code >= 400 or not isinstance(payload, dict) or not payload.get("access_token"):
        return "", ActionResult(False, failure_status(response.status_code, payload), f"Google rejected the service account: {error_text(payload)}")
    return str(payload["access_token"]), None


def _ensure_scheduler(client, token: str, account: dict, project: str, region: str, job: str, scheduler: str) -> str:
    headers = _auth(token)
    url = _scheduler_url(project, region, scheduler)
    current = client.get(url, headers=headers)
    if current.status_code == 404:
        body = {
            "name": f"projects/{project}/locations/{region}/jobs/{scheduler}",
            "schedule": "*/15 * * * *",
            "timeZone": "Etc/UTC",
            "description": "Information Hunters keeps launching the Cloud Run job.",
            "httpTarget": {
                "uri": _job_url(project, region, job) + ":run",
                "httpMethod": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": base64.b64encode(b"{}").decode(),
                "oauthToken": {
                    "serviceAccountEmail": account["client_email"],
                    "scope": "https://www.googleapis.com/auth/cloud-platform",
                },
            },
        }
        created = client.post(
            f"https://cloudscheduler.googleapis.com/v1/projects/{project}/locations/{region}/jobs",
            headers={**headers, "Content-Type": "application/json"},
            json=body,
        )
        if created.status_code >= 400:
            payload = read_body(created)
            if failure_status(created.status_code, payload) == "quota_exhausted":
                return "quota:" + error_text(payload)
            return f"Scheduler was not created ({error_text(payload)}). One job run was still requested. The free allowance is 3 scheduler jobs."
        note = "Scheduler job created (every 15 minutes, within the 3 free jobs)."
    elif current.status_code >= 400:
        return f"Could not read the scheduler job: {error_text(read_body(current))}."
    else:
        note = "Scheduler job found."
    resumed = client.post(url + ":resume", headers=headers)
    if resumed.status_code >= 400 and "already" not in error_text(read_body(resumed)).lower():
        note += f" Resume failed: {error_text(read_body(resumed))}."
    else:
        note += " Scheduler is resumed, so hunts continue while this laptop is off."
    return note


def _execution_name(payload) -> str | None:
    if not isinstance(payload, dict):
        return None
    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    for candidate in (meta.get("name"), payload.get("name")):
        if isinstance(candidate, str) and "/executions/" in candidate:
            return candidate
    return None


def _running_executions(client, headers, project: str, region: str, job: str) -> list[str]:
    response = client.get(_job_url(project, region, job) + "/executions", headers=headers)
    payload = read_body(response)
    items = payload.get("executions") if isinstance(payload, dict) else None
    names = []
    for item in items or []:
        if isinstance(item, dict) and item.get("name") and not item.get("completionTime"):
            names.append(item["name"])
    return names
