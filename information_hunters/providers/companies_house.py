"""Official Companies House public data API."""

import httpx

from information_hunters.categories import category_by_id
from information_hunters.config import get_settings
from information_hunters.providers.base import DiscoveredCompany, EnrichedCompany, ProviderAuthError, ProviderError
from information_hunters.providers.rate_limit import RateLimiter

BASE = "https://api.company-information.service.gov.uk"


class CompaniesHouseProvider:
    name = "companies_house"

    def __init__(self, api_key: str, http: httpx.Client | None = None):
        if not api_key:
            raise ProviderAuthError("Companies House API key is not set")
        self.http = http or httpx.Client(
            base_url=BASE,
            auth=(api_key, ""),
            timeout=30,
            headers={"User-Agent": "InformationHunters/0.1"},
        )
        self.limiter = RateLimiter(get_settings().companies_house_rps)

    def discover(self, category: str, region: str, limit: int, incorporated_after=None) -> list[DiscoveredCompany]:
        meta = category_by_id(category)
        if meta is None:
            raise ProviderError(f"Unknown category {category}")
        params = {
            "sic_codes": meta["sic"],
            "location": region,
            "company_status": "active",
            "size": str(min(limit, 100)),
        }
        if incorporated_after is not None:
            params["incorporated_from"] = incorporated_after.isoformat()
        payload = self._get("/advanced-search/companies", params)
        found = []
        for item in payload.get("items") or []:
            number = str(item.get("company_number") or "").strip()
            name = str(item.get("company_name") or "").strip()
            if not number or not name:
                continue
            found.append(
                DiscoveredCompany(
                    company_number=number,
                    name=name,
                    category=category,
                    region=region,
                    source="companies_house",
                    raw=item,
                )
            )
            if len(found) >= limit:
                break
        return found

    def enrich(self, company: DiscoveredCompany) -> EnrichedCompany:
        try:
            profile = self._get(f"/company/{company.company_number}")
        except ProviderError:
            profile = company.raw
        address = profile.get("registered_office_address") or company.raw.get("registered_office_address") or {}
        meta = category_by_id(company.category) or {}
        sic_codes = [str(code) for code in (profile.get("sic_codes") or company.raw.get("sic_codes") or [])]
        created = profile.get("date_of_creation") or company.raw.get("date_of_creation")
        from datetime import date

        incorporated = date.fromisoformat(created) if created else None
        locality = address.get("locality") or company.region
        parts = [address.get("premises"), address.get("address_line_1"), address.get("address_line_2"), locality, address.get("postal_code")]
        return EnrichedCompany(
            company_number=company.company_number,
            name=profile.get("company_name") or company.name,
            category=company.category,
            region=locality or company.region,
            address=", ".join(part for part in parts if part),
            postcode=address.get("postal_code") or "",
            sic_codes=sic_codes,
            sic_labels=[meta.get("sic_label", "")] if meta else [],
            incorporation_date=incorporated,
            company_status=str(profile.get("company_status") or company.raw.get("company_status") or "active"),
            sources=[{"provider": "companies_house", "reference": f"/company/{company.company_number}"}],
        )

    def _get(self, path: str, params: dict | None = None) -> dict:
        self.limiter.wait()
        response = self.http.get(path, params=params)
        if response.status_code == 401:
            raise ProviderAuthError("Companies House rejected the API key")
        if response.status_code == 404:
            raise ProviderError(f"Companies House had no record for {path}")
        if response.status_code >= 400:
            raise ProviderError(f"Companies House returned {response.status_code}")
        return response.json()
