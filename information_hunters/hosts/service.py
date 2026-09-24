"""Save host settings and apply start, stop, and test results."""

from __future__ import annotations

from dataclasses import asdict

from information_hunters.hosts.catalog import CATALOG, EXCLUDED, ProviderSpec, get_spec
from information_hunters.hosts.registry import get_adapter
from information_hunters.models import Host, Secret, utcnow
from information_hunters.ops import ActionResult, scrub
from information_hunters.providers.connection import scrapingbee_usage
from information_hunters.secrets import resolve_secret, save_secret
from information_hunters.telemetry import record_activity, record_error


class HostRequestError(Exception):
    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


def list_hosts(session) -> dict:
    rows = {row.provider: row for row in session.query(Host).all()}
    return {
        "hosts": [serialize_host(session, spec, rows.get(spec.id)) for spec in CATALOG],
        "excluded": [asdict(item) for item in EXCLUDED],
    }


def save_host(session, provider: str, values: dict) -> dict:
    spec = _require(provider)
    host = ensure_host(session, spec)
    config = {key: value for key, value in (host.config or {}).items() if str(key).startswith("_")}
    for field in spec.fields:
        if field.name not in values:
            continue
        raw = str(values[field.name] or "").strip()
        if field.secret:
            if raw:
                save_secret(session, field.name, raw)
            continue
        config[field.name] = raw
    host = session.query(Host).filter(Host.provider == spec.id).one()
    public = {key: value for key, value in (host.config or {}).items() if not str(key).startswith("_")}
    public.update({key: value for key, value in config.items() if not str(key).startswith("_")})
    hidden = {key: value for key, value in (host.config or {}).items() if str(key).startswith("_")}
    hidden.update({key: value for key, value in config.items() if str(key).startswith("_")})
    host.config = {**public, **hidden}
    host.updated_at = utcnow()
    session.commit()
    return serialize_host(session, spec, host)


def test_host(session, provider: str) -> dict:
    spec = _require(provider)
    host = ensure_host(session, spec)
    result = _invoke(session, spec, host, "test")
    _apply_test(session, host, spec, result)
    return {"host": serialize_host(session, spec, host), "ok": result.ok, "detail": result.detail, "usage": result.usage}


def start_host(session, provider: str) -> dict:
    spec = _require(provider)
    if not spec.controllable:
        raise HostRequestError(spec.uncontrolled_reason or f"{spec.name} cannot be started from this page.")
    host = ensure_host(session, spec)
    result = _invoke(session, spec, host, "start")
    _apply_run(session, host, spec, result, activity=f"Start requested for {spec.name}. {result.detail}")
    return serialize_host(session, spec, host)


def stop_host(session, provider: str) -> dict:
    spec = _require(provider)
    if not spec.controllable:
        raise HostRequestError(spec.uncontrolled_reason or f"{spec.name} cannot be stopped from this page.")
    host = ensure_host(session, spec)
    result = _invoke(session, spec, host, "stop")
    _apply_run(session, host, spec, result, activity=f"Stop requested for {spec.name}. {result.detail}")
    return serialize_host(session, spec, host)


def refresh_host(session, provider: str) -> dict:
    spec = _require(provider)
    host = ensure_host(session, spec)
    if not spec.controllable:
        return serialize_host(session, spec, host)
    result = _invoke(session, spec, host, "status")
    _apply_run(session, host, spec, result, activity="")
    return serialize_host(session, spec, host)


def ensure_host(session, spec: ProviderSpec) -> Host:
    row = session.query(Host).filter(Host.provider == spec.id).one_or_none()
    if row is None:
        row = Host(provider=spec.id, name=spec.name, status="stopped", controllable=spec.controllable, config={})
        session.add(row)
        session.commit()
    return row


def resolved_values(session, host: Host, spec: ProviderSpec) -> dict[str, str]:
    config = host.config or {}
    values: dict[str, str] = {}
    for field in spec.fields:
        if field.secret:
            values[field.name] = resolve_secret(session, field.name)
        else:
            stored = config.get(field.name)
            values[field.name] = str(stored if stored not in (None, "") else field.default)
    return values


def serialize_host(session, spec: ProviderSpec, host: Host | None) -> dict:
    config = (host.config or {}) if host is not None else {}
    fields = []
    for field in spec.fields:
        if field.secret:
            status = _secret_view(session, field.name)
            fields.append({**_field_dict(field), "value": "", **status})
        else:
            stored = config.get(field.name)
            value = str(stored if stored not in (None, "") else field.default)
            fields.append({**_field_dict(field), "value": value, "configured": bool(value), "last4": None, "source": "config" if stored not in (None, "") else ("default" if field.default else None)})
    missing = [field["label"] for field in fields if field["required"] and not field["configured"] and not field.get("value")]
    status = host.status if host is not None else "stopped"
    if missing and status == "stopped":
        status = "unconfigured"
    return {
        "id": host.id if host is not None else None,
        "provider": spec.id,
        "name": spec.name,
        "kind": spec.kind,
        "controllable": spec.controllable,
        "status": status,
        "status_detail": (host.status_detail if host is not None else "") or "",
        "free_limits": spec.free_limits,
        "summary": spec.summary,
        "setup_hint": spec.setup_hint,
        "setup_url": spec.setup_url,
        "manual_setup": spec.manual_setup,
        "keeps_running": spec.keeps_running,
        "uncontrolled_reason": spec.uncontrolled_reason,
        "remote_id": host.remote_id if host is not None else None,
        "usage": host.usage if host is not None else None,
        "last_error": host.last_error if host is not None else None,
        "fields": fields,
        "checked_at": host.checked_at.isoformat() if host is not None and host.checked_at else None,
        "updated_at": host.updated_at.isoformat() if host is not None and host.updated_at else None,
    }


def _invoke(session, spec: ProviderSpec, host: Host, action: str) -> ActionResult:
    values = resolved_values(session, host, spec)
    missing = [field.label for field in spec.fields if field.required and not values.get(field.name)]
    if missing and action in {"test", "start", "status"}:
        return ActionResult(False, "error", "Add " + ", ".join(missing) + " first.")
    if spec.kind == "scraper" and spec.id == "scrapingbee":
        return scrapingbee_usage(values.get("SCRAPINGBEE_API_KEY", ""))
    if spec.kind != "host":
        return ActionResult(True, "stopped", spec.uncontrolled_reason or spec.summary)
    try:
        adapter = get_adapter(spec.id)
        if action == "stop":
            return adapter.stop(values, host.remote_id)
        if action == "start":
            return adapter.start(values)
        if action == "status":
            return adapter.status(values, host.remote_id)
        return adapter.test(values)
    except ValueError as exc:
        return ActionResult(False, "error", str(exc))
    except Exception as exc:
        record_error(session, str(exc)[:500], error_type=type(exc).__name__, provider=spec.id, host_provider=spec.id, commit=True)
        return ActionResult(False, "error", f"{spec.name} call failed: {type(exc).__name__}")


def _apply_test(session, host: Host, spec: ProviderSpec, result: ActionResult) -> None:
    secrets = list(resolved_values(session, host, spec).values())
    host.checked_at = utcnow()
    host.updated_at = utcnow()
    detail = scrub(result.detail, secrets)
    if result.usage is not None:
        host.usage = result.usage
    if result.status == "quota_exhausted":
        host.status = "quota_exhausted"
        host.last_error = detail
        host.status_detail = detail
        host.stopped_at = utcnow()
        record_error(session, detail, error_type="quota_exhausted", provider=spec.id, host_provider=spec.id, commit=False)
    elif not result.ok:
        host.last_error = detail
        host.status_detail = detail
    else:
        host.last_error = None
        host.status_detail = detail
    session.commit()


def _apply_run(session, host: Host, spec: ProviderSpec, result: ActionResult, activity: str) -> None:
    secrets = list(resolved_values(session, host, spec).values())
    detail = scrub(result.detail, secrets)
    now = utcnow()
    host.checked_at = now
    host.updated_at = now
    host.status_detail = detail
    if result.remote_id:
        host.remote_id = result.remote_id[:400]
    if result.usage is not None:
        host.usage = result.usage
    if result.status == "quota_exhausted" or (not result.ok and result.status == "error"):
        host.status = result.status if result.status == "quota_exhausted" else "error"
        host.last_error = detail
        if host.status == "quota_exhausted":
            host.stopped_at = now
        record_error(session, detail, error_type=host.status, provider=spec.id, host_provider=spec.id, commit=False)
    else:
        host.status = result.status or host.status
        if host.status == "running":
            host.started_at = host.started_at or now
            host.stopped_at = None
            host.last_error = None
        elif host.status == "stopped":
            host.stopped_at = now
            host.last_error = None
    if activity:
        record_activity(session, scrub(activity, secrets), kind="status", host_provider=spec.id, commit=False)
    session.commit()


def _require(provider: str) -> ProviderSpec:
    spec = get_spec(provider)
    if spec is None:
        raise HostRequestError("Unknown host", 404)
    return spec


def _field_dict(field) -> dict:
    return {
        "name": field.name,
        "label": field.label,
        "hint": field.hint,
        "secret": field.secret,
        "required": field.required,
        "multiline": field.multiline,
    }


def _secret_view(session, name: str) -> dict:
    value = resolve_secret(session, name)
    return {
        "configured": bool(value),
        "last4": value[-4:] if len(value) >= 4 else None,
        "source": "database" if value and session.get(Secret, name) is not None else ("environment" if value else None),
    }
