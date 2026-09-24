"""Fleet catalogue: scrapers (cloud workers) and bots (pipeline roles).

Mirrors Find's profiles model for the desk UI — static metadata plus live
worker / secret status from the API layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Cloud workers that keep bots running — only things you start/stop for hunting.
# Pipeline stages (Discover/Verify/Extract/Score) are bots; they need no approval.
SCRAPER_PROFILES: dict[str, dict[str, Any]] = {
    "github-actions": {
        "name": "Cloud worker",
        "role": "GitHub Actions · hunts while your PC is off",
        "kind": "scraper",
        "description": (
            "The only scraper you control. Start it to claim queued hunts in the cloud "
            "(Supabase + your API keys as Action secrets). Bots run automatically — "
            "no per-bot approval. Schedule also ticks every 15 minutes."
        ),
        "source_name": "GitHub Actions",
        "source_url": "https://github.com/Abdullah-Shakil/Information-Hunters/actions/workflows/cloud-worker.yml",
        "docs_url": "https://docs.github.com/en/actions",
        "origin": ".github/workflows/cloud-worker.yml",
        "profile_summary": (
            "Press Start on Scrapers to run now, or leave the 15-minute schedule on. "
            "Needs the same DATABASE_URL and provider keys in GitHub Action secrets as your desk."
        ),
        "model_id": "cloud-engine",
        "is_engine": True,
        "importance": 1000,
        "importance_label": "Cloud · device can sleep",
        "modules": [
            {"name": "once", "path": "information_hunters/once.py", "purpose": "Claim and finish queued hunts"},
            {"name": "pipeline", "path": "information_hunters/pipeline.py", "purpose": "Run bots end-to-end"},
            {"name": "workflow", "path": ".github/workflows/cloud-worker.yml", "purpose": "Start now + 15-minute schedule"},
        ],
    },
}

# Pipeline bots — what each stage is functioned to do
BOT_PROFILES: dict[str, dict[str, Any]] = {
    "discover": {
        "name": "Discover",
        "role": "Finds UK trade companies",
        "kind": "bot",
        "description": (
            "Looks up Companies House (API or public pages) or the demo catalogue "
            "for local-service businesses in the hunt’s trades and cities."
        ),
        "source_name": "Companies House",
        "source_url": "https://developer.company-information.service.gov.uk/",
        "docs_url": "https://developer-specs.company-information.service.gov.uk/",
        "origin": "Official UK company register",
        "profile_summary": "Bot stage 1. Needs COMPANIES_HOUSE_API_KEY for the official API; otherwise public search or demo.",
        "model_id": "ch-public-api",
        "is_engine": False,
        "importance": 850,
        "importance_label": "Bot · discovers companies",
        "modules": [
            {"name": "companies_house", "path": "information_hunters/providers/companies_house.py", "purpose": "Official REST API"},
            {"name": "companies_house_public", "path": "information_hunters/providers/companies_house_public.py", "purpose": "Public HTML fallback"},
            {"name": "demo", "path": "information_hunters/providers/demo.py", "purpose": "Synthetic catalogue"},
        ],
    },
    "verify": {
        "name": "Verify",
        "role": "Confirms trading + contact fields",
        "kind": "bot",
        "description": (
            "Checks Google Places (or registry status) so only active businesses stay, "
            "and fills phone / website when Places is configured."
        ),
        "source_name": "Google Places API",
        "source_url": "https://console.cloud.google.com/google/maps-apis",
        "docs_url": "https://developers.google.com/maps/documentation/places/web-service/text-search",
        "origin": "Google Maps Platform",
        "profile_summary": "Bot stage 2. Needs GOOGLE_PLACES_API_KEY for live verification; otherwise registry/demo.",
        "model_id": "google-places",
        "is_engine": False,
        "importance": 800,
        "importance_label": "Bot · verifies + phone/website",
        "modules": [
            {"name": "google_places", "path": "information_hunters/providers/google_places.py", "purpose": "Trading status, phone, website"},
        ],
    },
    "extract": {
        "name": "Extract",
        "role": "Pulls email & mobile from public pages",
        "kind": "bot",
        "description": (
            "Fetches a public business page (direct, ScrapingBee, or Playwright) "
            "and reads visible email / phone. Optional Apify actor for enrichment."
        ),
        "source_name": "Direct / ScrapingBee / Playwright / Apify",
        "source_url": "https://www.scrapingbee.com/documentation/",
        "docs_url": "",
        "origin": "information_hunters/providers/fetchers.py + contacts.py",
        "profile_summary": (
            "Bot stage 3. Default is direct public HTTP. ScrapingBee/Playwright/Apify are unlockers — "
            "not separate scrapers."
        ),
        "model_id": "direct-http",
        "is_engine": False,
        "importance": 750,
        "importance_label": "Bot · extracts contacts",
        "modules": [
            {"name": "fetchers", "path": "information_hunters/providers/fetchers.py", "purpose": "Page fetch adapters"},
            {"name": "contacts", "path": "information_hunters/providers/contacts.py", "purpose": "Email/phone extraction"},
            {"name": "apify", "path": "information_hunters/providers/apify.py", "purpose": "Optional actor enrichment"},
        ],
    },
    "score": {
        "name": "Score",
        "role": "Ranks best leads first",
        "kind": "bot",
        "description": (
            "Scores each lead so high-priority rows rise — e.g. no website, has mobile/email, "
            "recent incorporation."
        ),
        "source_name": "Information Hunters scoring",
        "source_url": "http://127.0.0.1:3000/leads",
        "docs_url": "",
        "origin": "information_hunters/scoring.py",
        "profile_summary": "Bot stage 4. Local rules only — no API key.",
        "model_id": "rules-engine",
        "is_engine": False,
        "importance": 700,
        "importance_label": "Bot · ranks leads",
        "modules": [
            {"name": "scoring", "path": "information_hunters/scoring.py", "purpose": "Priority bands and reasons"},
        ],
    },
}

MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "cloud-engine": {
        "display_name": "Cloud / local worker loop",
        "provider": "Information Hunters",
        "api_key_env": "",
        "limit_units": None,
        "unit_label": "hunt cycles",
        "reset_period": "unlimited",
        "reset_mode": "none",
        "reset_label": "No usage cap",
        "profile_summary": "Execution host for scrapers. Not a metered API.",
        "source_url": "https://github.com/Abdullah-Shakil/Information-Hunters/actions",
        "console_url": "https://github.com/Abdullah-Shakil/Information-Hunters/actions",
    },
    "ch-public-api": {
        "display_name": "Companies House API",
        "provider": "UK Government",
        "api_key_env": "COMPANIES_HOUSE_API_KEY",
        "limit_units": 600,
        "unit_label": "requests / 5 min",
        "reset_period": "rolling",
        "reset_mode": "auto_rolling",
        "rolling_minutes": 5,
        "reset_label": "Rolling 5-minute window",
        "profile_summary": "Soft limit ~600 requests per 5 minutes; refreshes automatically.",
        "source_url": "https://developer.company-information.service.gov.uk/",
        "console_url": "https://developer.company-information.service.gov.uk/",
        "docs_url": "https://developer-specs.company-information.service.gov.uk/",
    },
    "google-places": {
        "display_name": "Google Places",
        "provider": "Google Cloud",
        "api_key_env": "GOOGLE_PLACES_API_KEY",
        "limit_units": 200,
        "unit_label": "USD credit / month",
        "reset_period": "monthly",
        "reset_mode": "auto_calendar",
        "reset_label": "Calendar month",
        "profile_summary": "Typical Maps credit resets automatically each billing month.",
        "source_url": "https://console.cloud.google.com/google/maps-apis",
        "console_url": "https://console.cloud.google.com/billing",
        "docs_url": "https://developers.google.com/maps/documentation/places/web-service/text-search",
    },
    "direct-http": {
        "display_name": "Direct public HTTP",
        "provider": "httpx",
        "api_key_env": "",
        "limit_units": None,
        "unit_label": "pages",
        "reset_period": "unlimited",
        "reset_mode": "none",
        "reset_label": "No usage cap",
        "profile_summary": "Local fetch of public pages. No account.",
        "source_url": "https://www.python-httpx.org/",
        "console_url": "",
        "docs_url": "",
    },
    "scrapingbee": {
        "display_name": "ScrapingBee",
        "provider": "ScrapingBee",
        "api_key_env": "SCRAPINGBEE_API_KEY",
        "limit_units": 1000,
        "unit_label": "credits",
        "reset_period": "lifetime",
        "reset_mode": "manual_portal",
        "reset_label": "Manual — visit portal",
        "manual_reset_url": "https://app.scrapingbee.com/account/login",
        "manual_reset_note": "Trial credits do not auto-reset. Top up in the portal when empty.",
        "profile_summary": "Optional unlocker for Extract when sites block direct fetch.",
        "source_url": "https://www.scrapingbee.com/",
        "console_url": "https://app.scrapingbee.com/account/login",
        "docs_url": "https://www.scrapingbee.com/documentation/",
    },
    "apify": {
        "display_name": "Apify actor",
        "provider": "Apify",
        "api_key_env": "APIFY_TOKEN",
        "limit_units": None,
        "unit_label": "actor runs",
        "reset_period": "plan",
        "reset_mode": "manual_portal",
        "reset_label": "Manual — Apify console",
        "manual_reset_url": "https://console.apify.com/",
        "manual_reset_note": "Usage depends on your Apify plan.",
        "profile_summary": "Optional actor enrichment. Needs APIFY_TOKEN and APIFY_ACTOR_ID.",
        "source_url": "https://apify.com/",
        "console_url": "https://console.apify.com/",
        "docs_url": "https://docs.apify.com/",
    },
    "rules-engine": {
        "display_name": "Scoring rules",
        "provider": "Local",
        "api_key_env": "",
        "limit_units": None,
        "unit_label": "runs",
        "reset_period": "unlimited",
        "reset_mode": "none",
        "reset_label": "No usage cap",
        "profile_summary": "Deterministic local scoring.",
        "source_url": "",
        "console_url": "",
        "docs_url": "",
    },
}


def next_calendar_month_reset(now: datetime | None = None) -> datetime:
    now = now or _now()
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)


def enrich_model(model_id: str, connected: bool, key_hint: str | None = None) -> dict[str, Any]:
    meta = dict(MODEL_PROFILES.get(model_id, {"display_name": model_id, "provider": "—"}))
    meta["id"] = model_id
    meta["connected"] = connected
    limit = meta.get("limit_units")
    has_limit = limit is not None
    meta["has_limit"] = has_limit
    meta["used_units"] = 0
    meta["remaining"] = limit if has_limit else None
    meta["pct_used"] = 0
    meta["show_reset"] = meta.get("reset_mode") not in {None, "none", ""}
    meta["needs_manual_reset"] = meta.get("reset_mode") == "manual_portal"
    meta["quota_paused"] = False

    mode = meta.get("reset_mode")
    now = _now()
    if mode == "auto_calendar":
        nxt = next_calendar_month_reset(now)
        delta = nxt - now
        hours = int(delta.total_seconds() // 3600)
        meta["next_reset_at"] = nxt.isoformat()
        meta["reset_in_human"] = f"{hours // 24}d {hours % 24}h" if hours >= 24 else f"{hours}h"
    elif mode == "auto_rolling":
        mins = int(meta.get("rolling_minutes") or 5)
        meta["next_reset_at"] = None
        meta["reset_in_human"] = f"every {mins} min"
    elif mode == "manual_portal":
        meta["next_reset_at"] = None
        meta["reset_in_human"] = meta.get("reset_label") or "Manual portal"
    else:
        meta["next_reset_at"] = None
        meta["reset_in_human"] = meta.get("reset_label") or "No reset"

    if meta.get("api_key_env"):
        if connected:
            meta["activation"] = {
                "state": "connected",
                "label": "Connected",
                "detail": f"{meta.get('display_name')} key is configured on the server.",
                "key_hint": key_hint,
            }
        else:
            meta["activation"] = {
                "state": "needs_activate",
                "label": "Needs key",
                "detail": f"Set {meta['api_key_env']} in Settings or .env.",
                "key_hint": meta["api_key_env"],
            }
    else:
        meta["activation"] = {
            "state": "connected" if connected else "skip",
            "label": "Ready" if connected else "Local",
            "detail": meta.get("profile_summary") or "",
            "key_hint": None,
        }
    return meta


def build_agent(
    agent_id: str,
    profile: dict[str, Any],
    *,
    status: str,
    model: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "id": agent_id,
        "name": profile["name"],
        "role": profile["role"],
        "kind": profile.get("kind", "bot"),
        "description": profile["description"],
        "source_name": profile.get("source_name"),
        "source_url": profile.get("source_url"),
        "docs_url": profile.get("docs_url"),
        "origin": profile.get("origin"),
        "profile_summary": profile.get("profile_summary"),
        "importance": profile.get("importance", 0),
        "importance_label": profile.get("importance_label"),
        "is_engine": bool(profile.get("is_engine")),
        "status": status,
        "modules": profile.get("modules") or [],
        "model_id": profile.get("model_id"),
        "model": model,
        "profile": {
            "kind": profile.get("kind", "bot"),
            "id": agent_id,
            "name": profile["name"],
            "source_name": profile.get("source_name"),
            "source_url": profile.get("source_url"),
            "docs_url": profile.get("docs_url"),
            "origin": profile.get("origin"),
            "summary": profile.get("profile_summary"),
            "is_engine": bool(profile.get("is_engine")),
            "importance_label": profile.get("importance_label"),
        },
        "activation": (model or {}).get("activation"),
    }
