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
    "GITHUB_TOKEN",
    "GCP_SERVICE_ACCOUNT_JSON",
    "OCI_PRIVATE_KEY",
    "KOYEB_API_TOKEN",
    "RENDER_API_KEY",
)

SECRET_META = {
    "COMPANIES_HOUSE_API_KEY": {
        "label": "Companies House API key",
        "hint": "developer.company-information.service.gov.uk — create a free application. The live API allows about 600 requests per 5 minutes.",
        "group": "companies_house",
        "placement": "settings",
    },
    "GOOGLE_PLACES_API_KEY": {
        "label": "Google Places API key",
        "hint": "console.cloud.google.com — enable Places API (New). Requests spend the monthly Maps credit. Restrict the key before you paste it.",
        "group": "google_places",
        "placement": "settings",
    },
    "SCRAPINGBEE_API_KEY": {
        "label": "ScrapingBee API key",
        "hint": "app.scrapingbee.com — the free plan includes 1,000 API credits and does not need a card. This is a fetch API, not a machine you start.",
        "group": "scrapingbee",
        "placement": "settings",
    },
    "BRIGHTDATA_API_TOKEN": {
        "label": "Bright Data API token",
        "hint": "brightdata.com — optional paid fetcher. There is no standing free tier; trial credit is not treated as a free host.",
        "group": "brightdata",
        "placement": "settings",
    },
    "BRIGHTDATA_ZONE": {
        "label": "Bright Data zone",
        "hint": "The Web Unlocker zone name from the Bright Data dashboard. Not a secret, but stored encrypted with the token.",
        "group": "brightdata",
        "placement": "settings",
    },
    "APIFY_TOKEN": {
        "label": "Apify API token",
        "hint": "console.apify.com/account/integrations — free plan includes $5 of platform credits per month. The same token starts the actor and enriches contacts.",
        "group": "apify",
        "placement": "host",
    },
    "APIFY_ACTOR_ID": {
        "label": "Apify actor id",
        "hint": "The actor you created from this repo (username~information-hunters). Set DATABASE_URL on that actor once.",
        "group": "apify",
        "placement": "host",
    },
    "GITHUB_TOKEN": {
        "label": "GitHub personal access token",
        "hint": "github.com/settings/tokens — classic token with repo and workflow scopes, or a fine-grained token with Actions read/write on this repository.",
        "group": "github_actions",
        "placement": "host",
    },
    "GCP_SERVICE_ACCOUNT_JSON": {
        "label": "Google Cloud service account JSON",
        "hint": "IAM → service account → Keys → JSON. Grant Cloud Run Admin and Cloud Scheduler Admin. This file is the credential; a plain API key cannot start jobs.",
        "group": "gcp_cloud_run",
        "placement": "host",
    },
    "OCI_PRIVATE_KEY": {
        "label": "Oracle API private key",
        "hint": "OCI profile → API keys → Add API key. Paste the PEM. The fingerprint and OCIDs go in the other fields on the host card.",
        "group": "oracle_cloud",
        "placement": "host",
    },
    "KOYEB_API_TOKEN": {
        "label": "Koyeb API token",
        "hint": "app.koyeb.com/account/api — the free instance is one web service (512 MB, sleeps after 1 hour with no traffic) and cannot be a background worker.",
        "group": "koyeb",
        "placement": "host",
    },
    "RENDER_API_KEY": {
        "label": "Render API key",
        "hint": "dashboard.render.com/u/settings#api-keys — free web services only (750 hours/month, sleep after 15 minutes idle). Background workers are paid.",
        "group": "render",
        "placement": "host",
    },
}


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
    meta = SECRET_META.get(name, {})
    return {
        "name": name,
        "configured": bool(value),
        "source": source,
        "last4": value[-4:] if len(value) >= 4 else None,
        "label": meta.get("label", name),
        "hint": meta.get("hint", ""),
        "group": meta.get("group", name),
        "placement": meta.get("placement", "settings"),
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
