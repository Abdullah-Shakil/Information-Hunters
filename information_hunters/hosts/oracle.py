"""Start and stop an Oracle Cloud Always Free compute instance."""

from __future__ import annotations

from information_hunters.hosts.signing import oci_headers
from information_hunters.ops import ActionResult, error_text, failure_status, open_client, read_body

_USAGE = {
    "summary": "Always Free includes an Ampere A1 shape up to 2 OCPUs and 12 GB (the June 2026 limit) and AMD micro instances. Out of host capacity is marked quota exhausted.",
    "unit": "instance",
}


class OracleCloudHost:
    provider = "oracle_cloud"

    def test(self, values: dict) -> ActionResult:
        try:
            target = _target(values)
        except ValueError as exc:
            return ActionResult(False, "error", str(exc))
        return _instance(values, target, "GET", None)

    def start(self, values: dict) -> ActionResult:
        try:
            target = _target(values)
        except ValueError as exc:
            return ActionResult(False, "error", str(exc))
        return _action(values, target, "START")

    def stop(self, values: dict, remote_id: str | None) -> ActionResult:
        del remote_id
        try:
            target = _target(values)
        except ValueError as exc:
            return ActionResult(False, "error", str(exc))
        return _action(values, target, "STOP")

    def status(self, values: dict, remote_id: str | None) -> ActionResult:
        del remote_id
        return self.test(values)


def _target(values: dict) -> tuple[str, str]:
    region = (values.get("OCI_REGION") or "").strip()
    instance = (values.get("OCI_INSTANCE_OCID") or "").strip()
    if not region or any(char in region for char in "/ ?"):
        raise ValueError("Oracle region is not valid.")
    if not instance.startswith("ocid1.instance.") or any(char in instance for char in " /?"):
        raise ValueError("Oracle instance OCID is not valid.")
    for label, key in (("Tenancy OCID", "OCI_TENANCY_OCID"), ("User OCID", "OCI_USER_OCID"), ("Fingerprint", "OCI_FINGERPRINT"), ("Private key", "OCI_PRIVATE_KEY")):
        if not (values.get(key) or "").strip():
            raise ValueError(f"Oracle {label} is required.")
    url = f"https://iaas.{region}.oraclecloud.com/20160918/instances/{instance}"
    return url, instance


def _signed(values: dict, method: str, url: str, body: bytes) -> dict[str, str]:
    return oci_headers(
        method,
        url,
        body,
        tenancy=values["OCI_TENANCY_OCID"].strip(),
        user=values["OCI_USER_OCID"].strip(),
        fingerprint=values["OCI_FINGERPRINT"].strip(),
        private_key_pem=values["OCI_PRIVATE_KEY"],
    )


def _instance(values: dict, target: tuple[str, str], method: str, action: str | None) -> ActionResult:
    url, instance = target
    request_url = url if action is None else f"{url}?action={action}"
    body = b""
    with open_client() as client:
        response = client.request(method, request_url, headers=_signed(values, method, request_url, body), content=body)
    payload = read_body(response)
    if response.status_code >= 400:
        status = failure_status(response.status_code, payload)
        prefix = "Oracle could not " + (action or "read").lower() + " the instance: "
        return ActionResult(False, status, prefix + error_text(payload), remote_id=instance, usage=_USAGE)
    state = payload.get("lifecycleState", "") if isinstance(payload, dict) else ""
    mapped = _map_state(state)
    detail = f"Instance is {state or 'unknown'}. {_USAGE['summary']}"
    return ActionResult(True, mapped, detail, remote_id=instance, usage=_USAGE)


def _action(values: dict, target: tuple[str, str], action: str) -> ActionResult:
    result = _instance(values, target, "POST", action)
    if result.status == "quota_exhausted" or not result.ok:
        return result
    if action == "STOP":
        return ActionResult(True, "stopped", result.detail, remote_id=result.remote_id, usage=result.usage)
    return ActionResult(True, "running", "Start requested. " + result.detail, remote_id=result.remote_id, usage=result.usage)


def _map_state(state: str) -> str:
    value = (state or "").upper()
    if value in {"RUNNING"}:
        return "running"
    if value in {"STARTING", "PROVISIONING"}:
        return "starting"
    if value in {"STOPPING"}:
        return "stopping"
    if value in {"STOPPED", "STOP"}:
        return "stopped"
    return "error" if not value else "stopped"
