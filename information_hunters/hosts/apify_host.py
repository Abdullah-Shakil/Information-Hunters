"""Run an Apify actor until the owner stops it or the free $5 credit is gone."""

from __future__ import annotations

from urllib.parse import quote

from information_hunters.ops import ActionResult, error_text, failure_status, open_client, read_body

API = "https://api.apify.com/v2"
SCHEDULE_NAME = "information-hunters"


class ApifyHost:
    provider = "apify"

    def test(self, values: dict) -> ActionResult:
        token = (values.get("APIFY_TOKEN") or "").strip()
        actor = (values.get("APIFY_ACTOR_ID") or "").strip()
        if not token or not actor:
            return ActionResult(False, "error", "Apify token and actor id are required.")
        with open_client() as client:
            usage, failure = _usage(client, token)
            if failure:
                return failure
            if usage.get("exhausted"):
                return ActionResult(False, "quota_exhausted", usage["summary"], usage=usage)
            actor_response = client.get(f"{API}/acts/{quote(actor, safe='~')}", headers=_headers(token))
            if actor_response.status_code >= 400:
                payload = read_body(actor_response)
                return ActionResult(False, failure_status(actor_response.status_code, payload), f"Apify could not open the actor: {error_text(payload)}", usage=usage)
            return ActionResult(True, "stopped", usage["summary"], usage=usage)

    def start(self, values: dict) -> ActionResult:
        checked = self.test(values)
        if not checked.ok:
            return checked
        token = values["APIFY_TOKEN"].strip()
        actor = values["APIFY_ACTOR_ID"].strip()
        with open_client() as client:
            headers = _headers(token)
            actor_body = read_body(client.get(f"{API}/acts/{quote(actor, safe='~')}", headers=headers))
            actor_id = actor
            if isinstance(actor_body, dict) and isinstance(actor_body.get("data"), dict) and actor_body["data"].get("id"):
                actor_id = actor_body["data"]["id"]
            schedule_note = _enable_schedule(client, headers, actor_id)
            run = client.post(f"{API}/acts/{quote(actor, safe='~')}/runs", headers=headers, params={"timeout": "36000"})
            payload = read_body(run)
            if run.status_code >= 400:
                status = failure_status(run.status_code, payload)
                return ActionResult(False, status, f"Apify did not start the actor: {error_text(payload)} {schedule_note}".strip(), usage=checked.usage)
            data = payload.get("data") if isinstance(payload, dict) else {}
            run_id = str((data or {}).get("id") or "") or None
            detail = "Actor run started. It keeps polling until you stop it or the $5 monthly credit is used. " + schedule_note
            return ActionResult(True, "running", detail.strip(), remote_id=run_id, usage=checked.usage)

    def stop(self, values: dict, remote_id: str | None) -> ActionResult:
        token = (values.get("APIFY_TOKEN") or "").strip()
        if not token:
            return ActionResult(False, "error", "Apify token is required.")
        with open_client() as client:
            headers = _headers(token)
            notes = [_disable_schedule(client, headers)]
            if remote_id:
                response = client.post(f"{API}/actor-runs/{quote(remote_id)}/abort", headers=headers)
                if response.status_code >= 400:
                    return ActionResult(False, failure_status(response.status_code, read_body(response)), "Apify did not abort the run: " + error_text(read_body(response)))
                notes.append("Run abort requested.")
            else:
                notes.append("No run id was stored.")
            return ActionResult(True, "stopped", " ".join(note for note in notes if note))

    def status(self, values: dict, remote_id: str | None) -> ActionResult:
        token = (values.get("APIFY_TOKEN") or "").strip()
        if not token:
            return ActionResult(False, "error", "Apify token is required.")
        with open_client() as client:
            usage, failure = _usage(client, token)
            if failure:
                return failure
            if not remote_id:
                status = "quota_exhausted" if usage.get("exhausted") else "stopped"
                return ActionResult(status == "stopped", status, usage["summary"], usage=usage)
            response = client.get(f"{API}/actor-runs/{quote(remote_id)}", headers=_headers(token))
            payload = read_body(response)
            if response.status_code >= 400:
                return ActionResult(False, failure_status(response.status_code, payload), error_text(payload), usage=usage)
            data = payload.get("data") if isinstance(payload, dict) else {}
            state = str((data or {}).get("status") or "")
            running = state in {"READY", "RUNNING", "ABORTING"}
            if usage.get("exhausted") and not running:
                return ActionResult(False, "quota_exhausted", usage["summary"], remote_id=remote_id, usage=usage)
            mapped = "running" if running else "stopped"
            return ActionResult(True, mapped, f"Actor run is {state or 'unknown'}. {usage['summary']}", remote_id=remote_id, usage=usage)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _usage(client, token: str) -> tuple[dict, ActionResult | None]:
    response = client.get(f"{API}/users/me", headers=_headers(token))
    payload = read_body(response)
    if response.status_code >= 400:
        return {}, ActionResult(False, failure_status(response.status_code, payload), f"Apify rejected the token: {error_text(payload)}")
    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        data = {}
    plan = data.get("plan") if isinstance(data.get("plan"), dict) else {}
    limit = _number(plan.get("monthlyUsageCreditsUsd"))
    if limit is None:
        limit = _number(plan.get("maxMonthlyUsageUsd"))
    used = _number(data.get("monthlyUsageUsd"))
    monthly = data.get("monthlyUsage") if isinstance(data.get("monthlyUsage"), dict) else {}
    if used is None:
        used = _number(monthly.get("totalUsageCreditsUsdAfterVolumeDiscount") or monthly.get("totalUsageUsd") or monthly.get("usageUsd"))
    exhausted = limit is not None and used is not None and used >= limit
    if limit is None:
        summary = "Apify token works. The free plan includes $5 of credits per month; this response did not include a limit."
    else:
        shown_used = 0 if used is None else used
        summary = f"${shown_used:.2f} of ${limit:.2f} free monthly credits used."
        if exhausted:
            summary += " The free credit is used up, so runs stay stopped until next month."
    return {"used": used, "limit": limit, "unit": "USD", "exhausted": exhausted, "summary": summary}, None


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _enable_schedule(client, headers, actor_id: str) -> str:
    schedule_id = _find_schedule(client, headers)
    body = {
        "name": SCHEDULE_NAME,
        "title": "Information Hunters",
        "cronExpression": "15 * * * *",
        "isEnabled": True,
        "isExclusive": True,
        "actions": [{"type": "RUN_ACTOR", "actorId": actor_id}],
    }
    if schedule_id:
        response = client.put(f"{API}/schedules/{quote(schedule_id)}", headers=headers, json={"isEnabled": True, "isExclusive": True})
    else:
        response = client.post(f"{API}/schedules", headers=headers, json=body)
    if response.status_code >= 400:
        return f"Hourly restart schedule was not saved ({error_text(read_body(response))})."
    return "Hourly restart schedule is enabled in case Apify ends the run."


def _disable_schedule(client, headers) -> str:
    schedule_id = _find_schedule(client, headers)
    if not schedule_id:
        return ""
    response = client.put(f"{API}/schedules/{quote(schedule_id)}", headers=headers, json={"isEnabled": False})
    if response.status_code >= 400:
        return "Could not disable the schedule: " + error_text(read_body(response))
    return "Hourly schedule disabled."


def _find_schedule(client, headers) -> str | None:
    response = client.get(f"{API}/schedules", headers=headers)
    payload = read_body(response)
    data = payload.get("data") if isinstance(payload, dict) else None
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("name") == SCHEDULE_NAME and item.get("id"):
            return str(item["id"])
    return None
