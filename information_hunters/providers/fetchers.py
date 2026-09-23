"""Page fetchers. Each one returns HTML for a public URL and nothing else."""

import httpx

from information_hunters.providers.base import ProviderError
from information_hunters.providers.safety import assert_public_http_url

USER_AGENT = "InformationHunters/0.1 (public-page research)"


class DirectFetcher:
    name = "direct"

    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})

    def fetch(self, url: str) -> str:
        assert_public_http_url(url)
        response = self.http.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "text/html")
        if "html" not in content_type and "text" not in content_type:
            raise ProviderError("Page was not HTML")
        return response.text[:1_000_000]


class ScrapingBeeFetcher:
    name = "scrapingbee"

    def __init__(self, api_key: str, http: httpx.Client | None = None):
        if not api_key:
            raise ProviderError("ScrapingBee API key is not set")
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=40)

    def fetch(self, url: str) -> str:
        assert_public_http_url(url)
        response = self.http.get(
            "https://app.scrapingbee.com/api/v1/",
            params={"api_key": self.api_key, "url": url, "render_js": "false"},
        )
        response.raise_for_status()
        return response.text[:1_000_000]


class BrightDataFetcher:
    name = "brightdata"

    def __init__(self, api_token: str, zone: str, http: httpx.Client | None = None):
        if not api_token or not zone:
            raise ProviderError("Bright Data token and zone are required")
        self.api_token = api_token
        self.zone = zone
        self.http = http or httpx.Client(timeout=40)

    def fetch(self, url: str) -> str:
        assert_public_http_url(url)
        response = self.http.post(
            "https://api.brightdata.com/request",
            headers={"Authorization": f"Bearer {self.api_token}"},
            json={"zone": self.zone, "url": url, "format": "raw"},
        )
        response.raise_for_status()
        return response.text[:1_000_000]


class PlaywrightFetcher:
    """Headless Chromium for public pages. This does not bypass logins."""

    name = "playwright"

    def fetch(self, url: str) -> str:
        assert_public_http_url(url)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ProviderError("Playwright is not installed. Use pip install -e '.[browser]' and playwright install chromium.") from exc
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(locale="en-GB", viewport={"width": 1280, "height": 800})
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                return page.content()[:1_000_000]
            finally:
                browser.close()


def build_fetcher(name: str, secrets: dict):
    if name in {"", "none"}:
        return None
    if name == "auto":
        if secrets.get("SCRAPINGBEE_API_KEY"):
            name = "scrapingbee"
        elif secrets.get("BRIGHTDATA_API_TOKEN") and secrets.get("BRIGHTDATA_ZONE"):
            name = "brightdata"
        else:
            name = "direct"
    if name == "direct":
        return DirectFetcher()
    if name == "scrapingbee":
        return ScrapingBeeFetcher(secrets.get("SCRAPINGBEE_API_KEY", ""))
    if name == "brightdata":
        return BrightDataFetcher(secrets.get("BRIGHTDATA_API_TOKEN", ""), secrets.get("BRIGHTDATA_ZONE", ""))
    if name == "playwright":
        return PlaywrightFetcher()
    raise ProviderError(f"Unknown contact fetcher: {name}")
