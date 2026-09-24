"""Request signing for Google service accounts and Oracle Cloud API keys."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from email.utils import formatdate
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def normalize_pem(value: str) -> str:
    text = (value or "").strip()
    if "\\n" in text and "BEGIN" in text:
        text = text.replace("\\n", "\n")
    return text


def parse_service_account(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Service account JSON could not be parsed") from exc
    if not isinstance(data, dict) or not data.get("client_email") or not data.get("private_key"):
        raise ValueError("Service account JSON needs client_email and private_key")
    data["private_key"] = normalize_pem(str(data["private_key"]))
    return data


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _load_key(pem: str):
    return serialization.load_pem_private_key(normalize_pem(pem).encode(), password=None)


def gcp_assertion(service_account: dict, now: int | None = None) -> str:
    issued = int(time.time()) if now is None else now
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": service_account["client_email"],
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": issued,
        "exp": issued + 3600,
    }
    signing_input = _b64(json.dumps(header, separators=(",", ":")).encode()) + "." + _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = _load_key(service_account["private_key"]).sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    return signing_input + "." + _b64(signature)


def oci_headers(method: str, url: str, body: bytes, *, tenancy: str, user: str, fingerprint: str, private_key_pem: str) -> dict[str, str]:
    parsed = urlparse(url)
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    method_l = method.lower()
    signed = ["date", "(request-target)", "host"]
    values = {
        "date": date,
        "(request-target)": f"{method_l} {target}",
        "host": parsed.netloc,
    }
    headers = {"date": date, "host": parsed.netloc}
    if method_l in {"post", "put", "patch"}:
        digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
        content_type = "application/json"
        content_length = str(len(body))
        values.update({"x-content-sha256": digest, "content-type": content_type, "content-length": content_length})
        signed.extend(["x-content-sha256", "content-type", "content-length"])
        headers.update({"x-content-sha256": digest, "content-type": content_type, "content-length": content_length})
    signing_string = "\n".join(f"{name}: {values[name]}" for name in signed)
    signature = base64.b64encode(_load_key(private_key_pem).sign(signing_string.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()
    key_id = f"{tenancy}/{user}/{fingerprint}"
    headers["authorization"] = (
        f'Signature version="1",keyId="{key_id}",algorithm="rsa-sha256",headers="{" ".join(signed)}",signature="{signature}"'
    )
    return headers
