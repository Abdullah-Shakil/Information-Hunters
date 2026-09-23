"""Pick providers for a hunt from the job row and server secrets."""

from sqlalchemy.orm import Session

from information_hunters.config import get_settings
from information_hunters.models import Job
from information_hunters.providers.demo import DemoDiscovery, DemoEnricher, DemoVerifier
from information_hunters.secrets import resolve_secret


def build_providers(session: Session, job: Job):
    settings = get_settings()
    ch_key = resolve_secret(session, "COMPANIES_HOUSE_API_KEY")
    places_key = resolve_secret(session, "GOOGLE_PLACES_API_KEY")
    discovery_name = job.discovery_provider or "auto"
    verify_name = job.verification_provider or "auto"

    if discovery_name == "auto":
        if ch_key:
            discovery_name = "companies_house"
        elif settings.demo_mode:
            discovery_name = "demo"
        else:
            discovery_name = "companies_house_public"

    if discovery_name == "demo":
        return DemoDiscovery(), DemoEnricher(), DemoVerifier()

    if discovery_name == "companies_house":
        from information_hunters.providers.companies_house import CompaniesHouseProvider

        provider = CompaniesHouseProvider(ch_key)
        verifier = _verifier(verify_name, places_key, settings.demo_mode)
        return provider, provider, verifier

    if discovery_name == "companies_house_public":
        from information_hunters.providers.companies_house_public import PublicSearchProvider

        provider = PublicSearchProvider()
        verifier = _verifier(verify_name, places_key, settings.demo_mode)
        return provider, provider, verifier

    raise RuntimeError(f"Unknown discovery provider: {discovery_name}")


def _verifier(name: str, places_key: str, demo_mode: bool):
    if name == "auto":
        if places_key:
            name = "google_places"
        elif demo_mode:
            name = "demo"
        else:
            name = "registry"
    if name == "demo":
        return DemoVerifier()
    if name == "google_places":
        from information_hunters.providers.google_places import GooglePlacesVerifier

        return GooglePlacesVerifier(places_key)
    if name == "registry":
        from information_hunters.providers.registry import RegistryVerifier

        return RegistryVerifier()
    raise RuntimeError(f"Unknown verification provider: {name}")
