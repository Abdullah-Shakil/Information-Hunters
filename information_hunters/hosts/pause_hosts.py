"""Koyeb and Render can pause and resume a service. Their free tiers sleep, which this states in every result."""

from __future__ import annotations

from information_hunters.ops import ActionResult, error_text, failure_status, open_client, read_body

KOYEB_NOTE = "The free Koyeb instance sleeps after 1 hour without HTTP traffic and cannot be a background worker, so it does not keep scraping while asleep."
RENDER_NOTE = "A free Render web service sleeps after 15 minutes without traffic and is suspended for the rest of the month after 750 hours."


class KoyebHost:
    provider = "koyeb"

    def test(self, values: dict) -> ActionResult:
        return self.status(values, None)

    def start(self, values: dict) -> ActionResult:
        return _call(values, "KOYEB_API_TOKEN", "KOYEB_SERVICE_ID", "https://app.koyeb.com/v1/services/{id}/resume", "POST", KOYEB_NOTE, "running")

    def stop(self, values: dict, remote_id: str | None) -> ActionResult:
        del remote_id
        return _call(values, "KOYEB_API_TOKEN", "KOYEB_SERVICE_ID", "https://app.koyeb.com/v1/services/{id}/pause", "POST", KOYEB_NOTE, "stopped")

    def status(self, values: dict, remote_id: str | None) -> ActionResult:
        del remote_id
        result = _call(values, "KOYEB_API_TOKEN", "KOYEB_SERVICE_ID", "https://app.koyeb.com/v1/services/{id}", "GET", KOYEB_NOTE, "")
        if not result.ok:
            return result
        return result


class RenderHost:
    provider = "render"

    def test(self, values: dict) -> ActionResult:
        return self.status(values, None)

    def start(self, values: dict) -> ActionResult:
        return _call(values, "RENDER_API_KEY", "RENDER_SERVICE_ID", "https://api.render.com/v1/services/{id}/resume", "POST", RENDER_NOTE, "running")

    def stop(self, values: dict, remote_id: str | None) -> ActionResult:
        del remote_id
        return _call(values, "RENDER_API_KEY", "RENDER_SERVICE_ID", "https://api.render.com/v1/services/{id}/suspend", "POST", RENDER_NOTE, "stopped")

    def status(self, values: dict, remote_id: str | None) -> ActionResult:
        del remote_id
        return _call(values, "RENDER_API_KEY", "RENDER_SERVICE_ID", "https://api.render.com/v1/services/{id}", "GET", RENDER_NOTE, "")


def _call(values: dict, token_field: str, id_field: str, template: str, method: str, note: str, forced_status: str) -> ActionResult:
    token = (values.get(token_field) or "").strip()
    service_id = (values.get(id_field) or "").strip()
    if not token or not service_id or any(char in service_id for char in " /?"):
        return ActionResult(False, "error", "API token and service id are required.")
    url = template.format(id=service_id)
    with open_client() as client:
        response = client.request(method, url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    payload = read_body(response)
    if response.status_code >= 400:
        status = failure_status(response.status_code, payload)
        return ActionResult(False, status, f"The provider rejected the call: {error_text(payload)} {note}")
    if forced_status:
        verb = "resumed" if forced_status == "running" else "paused"
        return ActionResult(True, forced_status, f"Service {verb}. {note}", remote_id=service_id)
    mapped, detail = _read_state(payload, note)
    return ActionResult(True, mapped, detail, remote_id=service_id)


def _read_state(payload, note: str) -> tuple[str, str]:
    body = payload.get("service") if isinstance(payload, dict) and isinstance(payload.get("service"), dict) else payload
    if not isinstance(body, dict):
        return "stopped", note
    if str(body.get("suspended") or "").lower() == "suspended":
        return "stopped", f"Service is suspended. {note}"
    raw = str(body.get("status") or body.get("state") or "")
    upper = raw.upper()
    if upper in {"PAUSED", "STOPPED"} or "PAUS" in upper:
        return "stopped", f"Service is {raw or 'paused'}. {note}"
    if upper in {"HEALTHY", "RUNNING", "STARTED", "LIVE"} or not upper:
        # Render's not_suspended service may still be spun down. Say so.
        if "suspended" in body:
            return "running", f"Service is not suspended. {note}"
        return "running", f"Service is {raw or 'up'}. {note}"
    if "RESUM" in upper or upper in {"STARTING", "DEPLOYING"}:
        return "running", f"Service is {raw}. {note}"
    return "running", f"Service reported {raw}. {note}"
