"""Optional Apify actor call. The actor id comes from configuration, not from this repo."""

import httpx

from information_hunters.providers.base import EnrichedCompany, ProviderError


class ApifyEnricher:
    name = "apify"

    def __init__(self, token: str, actor_id: str, http: httpx.Client | None = None):
        if not token or not actor_id:
            raise ProviderError("Apify token and actor id are required")
        self.token = token
        self.actor_id = actor_id
        self.http = http or httpx.Client(timeout=90)

    def enrich(self, company: EnrichedCompany) -> dict:
        response = self.http.post(
            f"https://api.apify.com/v2/acts/{self.actor_id}/run-sync-get-dataset-items",
            params={"token": self.token},
            json={"companyName": company.name, "location": company.region, "companyNumber": company.company_number},
        )
        if response.status_code in {401, 403}:
            raise ProviderError("Apify rejected the token")
        response.raise_for_status()
        items = response.json()
        if isinstance(items, dict):
            items = items.get("items") or []
        if not items:
            return {}
        first = items[0] if isinstance(items, list) else {}
        return {
            "email": first.get("email") or first.get("emails"),
            "phone": first.get("phone") or first.get("landline"),
            "mobile": first.get("mobile") or first.get("mobilePhone"),
            "website": first.get("website") or first.get("websiteUrl"),
        }
