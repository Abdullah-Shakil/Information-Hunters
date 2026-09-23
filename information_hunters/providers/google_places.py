"""Google Places text search. Official API only — this does not scrape Google."""

import re

import httpx

from information_hunters.phones import split_phone
from information_hunters.providers.base import EnrichedCompany, ProviderAuthError, Verification
from information_hunters.providers.safety import usable_website

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.businessStatus",
        "places.formattedAddress",
        "places.googleMapsUri",
    ]
)


def _tokens(value: str) -> set[str]:
    cleaned = re.sub(r"\b(ltd|limited|llp|plc|co|company|the)\b", " ", value.lower())
    return {token for token in re.findall(r"[a-z0-9]+", cleaned) if len(token) > 1}


def names_compatible(company_name: str, place_name: str) -> bool:
    left = _tokens(company_name)
    right = _tokens(place_name)
    if not left or not right:
        return False
    if left <= right or right <= left:
        return True
    overlap = left & right
    return len(overlap) / max(len(left), 1) >= 0.5


class GooglePlacesVerifier:
    name = "google_places"

    def __init__(self, api_key: str, http: httpx.Client | None = None):
        if not api_key:
            raise ProviderAuthError("Google Places API key is not set")
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=20)

    def verify(self, company: EnrichedCompany) -> Verification:
        response = self.http.post(
            PLACES_URL,
            headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": FIELD_MASK},
            json={"textQuery": f"{company.name} {company.region}", "regionCode": "GB", "pageSize": 3},
        )
        if response.status_code in {401, 403}:
            raise ProviderAuthError("Google Places rejected the API key")
        if response.status_code >= 400:
            return Verification(False, f"Google Places returned {response.status_code}", "google_places")
        places = response.json().get("places") or []
        for place in places:
            place_name = ((place.get("displayName") or {}).get("text")) or ""
            if not names_compatible(company.name, place_name):
                continue
            status = place.get("businessStatus") or ""
            phone = place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber")
            website = usable_website(place.get("websiteUri"))
            trading = status == "OPERATIONAL"
            if trading:
                notes = f"Google Places lists {place_name} as operational."
            elif status:
                notes = f"Google Places lists {place_name} as {status}."
            else:
                notes = f"Google Places matched {place_name} without a business status."
                trading = False
            landline, mobile = split_phone(phone)
            return Verification(
                actively_trading=trading,
                notes=notes,
                source="google_places",
                evidence={
                    "place_name": place_name,
                    "business_status": status,
                    "phone": landline,
                    "mobile": mobile,
                    "website": website,
                    "maps_uri": place.get("googleMapsUri"),
                    "address": place.get("formattedAddress"),
                },
            )
        return Verification(False, "No matching Google place. Left out until a live trading signal exists.", "google_places")
