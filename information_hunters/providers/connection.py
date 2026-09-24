"""Test saved provider keys without returning them."""

from __future__ import annotations

import base64

from information_hunters.config import get_settings
from information_hunters.ops import ActionResult, error_text, failure_status, open_client, read_body
from information_hunters.secrets import resolve_secret


def test_provider(session, provider: str) -> ActionResult:
    if provider == "supabase":
        return _supabase()
    if provider == "companies_house":
        return _companies_house(resolve_secret(session, "COMPANIES_HOUSE_API_KEY"))
    if provider == "google_places":
        return _places(resolve_secret(session, "GOOGLE_PLACES_API_KEY"))
    if provider == "scrapingbee":
        return scrapingbee_usage(resolve_secret(session, "SCRAPINGBEE_API_KEY"))
    if provider == "brightdata":
        return _brightdata(resolve_secret(session, "BRIGHTDATA_API_TOKEN"), resolve_secret(session, "BRIGHTDATA_ZONE"))
    return ActionResult(False, "error", "This provider has no connection test.")


def scrapingbee_usage(api_key: str) -> ActionResult:
    if not api_key:
        return ActionResult(False, "error", "ScrapingBee API key is not set.")
    with open_client() as client:
        response = client.get("https://app.scrapingbee.com/api/v1/usage", params={"api_key": api_key})
    payload = read_body(response)
    if response.status_code >= 400:
        return ActionResult(False, failure_status(response.status_code, payload), f"ScrapingBee rejected the key (HTTP {response.status_code}).")
    if not isinstance(payload, dict):
        return ActionResult(False, "error", "ScrapingBee usage response was not readable.")
    limit = _int(payload.get("max_api_credit", payload.get("max_api_credits")))
    used = _int(payload.get("used_api_credit", payload.get("used_api_credits")))
    exhausted = limit is not None and used is not None and used >= limit
    summary = f"{used if used is not None else '?'} of {limit if limit is not None else '?'} ScrapingBee credits used. The free plan includes 1,000."
    usage = {"used": used, "limit": limit, "unit": "credits", "exhausted": exhausted, "summary": summary}
    if exhausted:
        return ActionResult(False, "quota_exhausted", summary + " Free credits are used up.", usage=usage)
    return ActionResult(True, "stopped", summary, usage=usage)


def _companies_house(api_key: str) -> ActionResult:
    if not api_key:
        return ActionResult(False, "error", "Companies House API key is not set.")
    token = base64.b64encode(f"{api_key}:".encode()).decode()
    with open_client() as client:
        response = client.get(
            "https://api.company-information.service.gov.uk/search/companies",
            params={"q": "tesco", "items_per_page": 1},
            headers={"Authorization": f"Basic {token}"},
        )
    if response.status_code in {401, 403}:
        return ActionResult(False, "error", "Companies House rejected the key.")
    if response.status_code == 429:
        return ActionResult(True, "stopped", "The key was accepted. Companies House is rate limiting right now (about 600 requests per 5 minutes).")
    if response.status_code >= 400:
        return ActionResult(False, "error", f"Companies House returned HTTP {response.status_code}.")
    return ActionResult(True, "stopped", "Companies House accepted the key. The public API is free and rate limited.")


def _places(api_key: str) -> ActionResult:
    if not api_key:
        return ActionResult(False, "error", "Google Places API key is not set.")
    with open_client() as client:
        response = client.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "places.id", "Content-Type": "application/json"},
            json={"textQuery": "plumber in Leeds", "pageSize": 1},
        )
    payload = read_body(response)
    if response.status_code in {401, 403}:
        return ActionResult(False, "error", "Google Places rejected the key. Enable Places API (New) on the same project.")
    if response.status_code >= 400:
        return ActionResult(False, failure_status(response.status_code, payload), f"Google Places returned {error_text(payload)}")
    return ActionResult(True, "stopped", "Places accepted the key. This test uses one small text search against the monthly Maps credit.")


def _brightdata(token: str, zone: str) -> ActionResult:
    if not token or not zone:
        return ActionResult(False, "error", "Bright Data token and zone are both required.")
    with open_client() as client:
        response = client.get("https://api.brightdata.com/customer/balance", headers={"Authorization": f"Bearer {token}"})
    if response.status_code in {401, 403}:
        return ActionResult(False, "error", "Bright Data rejected the token.")
    if response.status_code >= 400:
        return ActionResult(False, "error", f"Bright Data returned HTTP {response.status_code}. This fetcher is optional and is not a free tier.")
    return ActionResult(True, "stopped", f"Bright Data accepted the token for zone {zone}. This is a paid fetcher, not a free host.")


def _supabase() -> ActionResult:
    settings = get_settings()
    database = settings.resolved_database_url()
    using_postgres = database.startswith("postgresql")
    if not settings.supabase_url or not settings.supabase_service_role_key:
        if using_postgres:
            return ActionResult(True, "stopped", "The API is using a Postgres URL. SUPABASE_URL or the service role key is not set, so the REST check was skipped. Workers use the database URL directly.")
        return ActionResult(False, "error", "Supabase is not configured. Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_DB_URL on the server. Those cannot be stored in the database they are meant to open. Local demo keeps using SQLite.")
    url = settings.supabase_url.rstrip("/") + "/rest/v1/"
    with open_client() as client:
        response = client.get(
            url,
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
            },
        )
    if response.status_code >= 400:
        return ActionResult(False, "error", f"Supabase REST returned HTTP {response.status_code}. The service role key stayed on the server.")
    suffix = " Postgres is the API database." if using_postgres else " The API is still on SQLite until SUPABASE_DB_URL or DATABASE_URL points at Supabase."
    return ActionResult(True, "stopped", "Supabase accepted the service role key." + suffix)


def _int(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
