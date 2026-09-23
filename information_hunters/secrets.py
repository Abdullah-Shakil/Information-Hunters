"""Server-side secret store. Values are encrypted at rest and never returned in full."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from information_hunters.config import get_settings
from information_hunters.models import Secret, utcnow

SECRET_NAMES = (
    "COMPANIES_HOUSE_API_KEY",
    "GOOGLE_PLACES_API_KEY",
    "SCRAPINGBEE_API_KEY",
    "BRIGHTDATA_API_TOKEN",
    "BRIGHTDATA_ZONE",
    "APIFY_TOKEN",
    "APIFY_ACTOR_ID",
)


def _fernet() -> Fernet | None:
    master = get_settings().secrets_master_key
    if not master:
        return None
    digest = hashlib.sha256(master.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def resolve_secret(session: Session, name: str) -> str:
    row = session.get(Secret, name)
    if row is not None:
        cipher = _fernet()
        if cipher is None:
            return ""
        try:
            return cipher.decrypt(row.ciphertext.encode()).decode()
        except InvalidToken:
            return ""
    settings = get_settings()
    return getattr(settings, name.lower(), "") or ""


def secret_status(session: Session, name: str) -> dict:
    value = resolve_secret(session, name)
    source = None
    if session.get(Secret, name) is not None and value:
        source = "database"
    elif value:
        source = "environment"
    return {
        "name": name,
        "configured": bool(value),
        "source": source,
        "last4": value[-4:] if len(value) >= 4 else None,
    }


def save_secret(session: Session, name: str, value: str) -> None:
    if name not in SECRET_NAMES:
        raise ValueError("Unknown secret")
    cipher = _fernet()
    if cipher is None:
        raise RuntimeError("SECRETS_MASTER_KEY is not set")
    row = session.get(Secret, name)
    token = cipher.encrypt(value.encode()).decode()
    if row is None:
        session.add(Secret(name=name, ciphertext=token, updated_at=utcnow()))
    else:
        row.ciphertext = token
        row.updated_at = utcnow()
    session.commit()
