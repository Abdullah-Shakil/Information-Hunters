import httpx

from information_hunters.providers.companies_house import CompaniesHouseProvider
from information_hunters.providers.companies_house_public import parse_search_html
from information_hunters.providers.google_places import GooglePlacesVerifier, names_compatible
from information_hunters.providers.html_extract import extract_contacts
from information_hunters.providers.safety import UnsafeUrl, assert_public_http_url, usable_website
from information_hunters.providers.base import EnrichedCompany


HTML = """
<ul>
  <li>
    <h2><a href="/company/12345678">HARBOUR HEAT LTD</a></h2>
    <p>Active</p>
  </li>
  <li>
    <a href="/company/87654321">OLD CO LTD</a>
    <p>Dissolved on 1 January 2020</p>
  </li>
</ul>
"""


def test_public_search_parser_skips_dissolved():
    found = parse_search_html(HTML, "plumbers", "Manchester", 10)
    assert [item.company_number for item in found] == ["12345678"]
    assert found[0].name == "HARBOUR HEAT LTD"


def test_blocks_private_and_social_urls():
    for url in ("http://127.0.0.1/admin", "http://169.254.169.254/latest", "https://www.linkedin.com/in/someone", "file:///etc/passwd"):
        try:
            assert_public_http_url(url)
        except UnsafeUrl:
            continue
        raise AssertionError(url)
    assert usable_website("https://www.facebook.com/acme") is None
    assert usable_website("https://harbourheat.example") == "https://harbourheat.example"


def test_extracts_mailto_and_mobile():
    found = extract_contacts('<a href="mailto:enquiries@harbourheat.co.uk">Email</a> Call 07700 900123')
    assert found["email"] == "enquiries@harbourheat.co.uk"
    assert found["mobile"] == "07700 900123"


def test_names_compatible():
    assert names_compatible("Harbour Heat Ltd", "Harbour Heat Plumbing")
    assert not names_compatible("Harbour Heat Ltd", "Completely Different Electrics")


def test_companies_house_client_reads_advanced_search():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/advanced-search/companies":
            return httpx.Response(200, json={"items": [{"company_name": "HARBOUR HEAT LTD", "company_number": "12345678", "company_status": "active", "date_of_creation": "2024-05-01", "sic_codes": ["43220"], "registered_office_address": {"address_line_1": "1 Tariff Street", "locality": "Manchester", "postal_code": "M1 1AA"}}]})
        if request.url.path == "/company/12345678":
            return httpx.Response(200, json={"company_name": "HARBOUR HEAT LTD", "company_number": "12345678", "company_status": "active", "date_of_creation": "2024-05-01", "sic_codes": ["43220"], "registered_office_address": {"address_line_1": "1 Tariff Street", "locality": "Manchester", "postal_code": "M1 1AA"}})
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.company-information.service.gov.uk")
    provider = CompaniesHouseProvider("test-key", http=http)
    found = provider.discover("plumbers", "Manchester", 5)
    enriched = provider.enrich(found[0])
    assert enriched.company_number == "12345678"
    assert enriched.postcode == "M1 1AA"
    assert enriched.company_status == "active"


def test_places_keeps_operational_match_and_drops_lookalikes():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "places": [
                    {"displayName": {"text": "Unrelated Cafe"}, "businessStatus": "OPERATIONAL", "nationalPhoneNumber": "020 7946 0999"},
                    {"displayName": {"text": "Harbour Heat"}, "businessStatus": "OPERATIONAL", "nationalPhoneNumber": "07700 900222", "websiteUri": "https://www.facebook.com/harbourheat"},
                ]
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = GooglePlacesVerifier("places-key", http=http)
    result = verifier.verify(EnrichedCompany(company_number="1", name="Harbour Heat Ltd", category="plumbers", region="Manchester"))
    assert result.actively_trading is True
    assert result.evidence["mobile"] == "07700 900222"
    assert result.evidence["website"] is None
