"""Polite HTML fallback for Companies House public search.

Prefer the official API. This exists for fields the API would have returned
when no key is configured and demo mode is off.
"""

import re
import time
from datetime import date
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from information_hunters.categories import category_by_id
from information_hunters.providers.base import DiscoveredCompany, EnrichedCompany, ProviderError

SEARCH = "https://find-and-update.company-information.service.gov.uk/search/companies?q={query}"
COMPANY_HREF = re.compile(r"^/company/([A-Za-z0-9]{6,10})$")
CREATED = re.compile(r"(\d{1,2}\s+\w+\s+\d{4})")


class PublicSearchProvider:
    name = "companies_house_public"

    def __init__(self, http: httpx.Client | None = None, delay_seconds: float = 2.0):
        self.http = http or httpx.Client(
            timeout=30,
            headers={"User-Agent": "InformationHunters/0.1 (public registry research; rate limited)"},
            follow_redirects=True,
        )
        self.delay_seconds = delay_seconds
        self._last = 0.0

    def discover(self, category: str, region: str, limit: int, incorporated_after=None) -> list[DiscoveredCompany]:
        meta = category_by_id(category)
        label = meta["label"] if meta else category
        self._wait()
        url = SEARCH.format(query=quote_plus(f"{label} {region}"))
        response = self.http.get(url)
        if response.status_code >= 400:
            raise ProviderError(f"Companies House public search returned {response.status_code}")
        return parse_search_html(response.text, category, region, limit, incorporated_after)

    def enrich(self, company: DiscoveredCompany) -> EnrichedCompany:
        meta = category_by_id(company.category) or {}
        raw = company.raw
        created = raw.get("incorporation_date")
        return EnrichedCompany(
            company_number=company.company_number,
            name=company.name,
            category=company.category,
            region=company.region,
            address=raw.get("address") or "",
            sic_codes=[meta["sic"]] if meta else [],
            sic_labels=[meta.get("sic_label", "")] if meta else [],
            incorporation_date=date.fromisoformat(created) if created else None,
            company_status=raw.get("company_status") or "active",
            sources=[{"provider": "companies_house_public", "reference": f"/company/{company.company_number}"}],
        )

    def _wait(self) -> None:
        delay = self.delay_seconds - (time.monotonic() - self._last)
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()


def parse_search_html(html: str, category: str, region: str, limit: int, incorporated_after=None) -> list[DiscoveredCompany]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[DiscoveredCompany] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        href = (link.get("href") or "").split("?")[0]
        match = COMPANY_HREF.match(href)
        if not match:
            continue
        number = match.group(1).upper()
        if number in seen:
            continue
        name = link.get_text(" ", strip=True)
        if not name or name.lower() in {"view company", "company"}:
            continue
        blob = ""
        parent = link.find_parent(["li", "article", "div"])
        if parent is not None:
            blob = parent.get_text(" ", strip=True)
        if "dissolved" in blob.lower():
            continue
        seen.add(number)
        found.append(
            DiscoveredCompany(
                company_number=number,
                name=name,
                category=category,
                region=region,
                source="companies_house_public",
                raw={"company_status": "active", "snippet": blob[:500]},
            )
        )
        if len(found) >= limit:
            break
    return found
