"""Fill phone, email, and website from Places evidence, a public page, or Apify."""

from sqlalchemy.orm import Session

from information_hunters.models import Job
from information_hunters.phones import split_phone
from information_hunters.providers.apify import ApifyEnricher
from information_hunters.providers.base import EnrichedCompany, Verification
from information_hunters.providers.fetchers import build_fetcher
from information_hunters.providers.html_extract import extract_contacts
from information_hunters.providers.safety import usable_website
from information_hunters.secrets import resolve_secret


def apply_verification_contacts(company: EnrichedCompany, verification: Verification) -> None:
    evidence = verification.evidence or {}
    if evidence.get("mobile") and not company.mobile:
        company.mobile = evidence["mobile"]
    if evidence.get("phone") and not company.phone:
        company.phone = evidence["phone"]
    website = usable_website(evidence.get("website"))
    if website:
        company.website = website
        company.has_website = True
    elif evidence.get("website") and not usable_website(evidence.get("website")):
        company.has_website = False
        company.website = None
    if evidence.get("address") and not company.address:
        company.address = evidence["address"]
    if evidence:
        company.sources.append({"provider": verification.source, "reference": evidence.get("maps_uri") or evidence.get("business_status") or ""})


def pull_extra_contacts(session: Session, job: Job, company: EnrichedCompany) -> None:
    secrets = {name: resolve_secret(session, name) for name in ("SCRAPINGBEE_API_KEY", "APIFY_TOKEN", "APIFY_ACTOR_ID")}
    if company.website and job.contact_fetcher != "none":
        fetcher = build_fetcher(job.contact_fetcher or "auto", secrets)
        if fetcher is not None:
            try:
                html = fetcher.fetch(company.website)
            except Exception as exc:
                company.sources.append({"provider": fetcher.name, "reference": f"fetch failed: {exc}"[:300]})
            else:
                found = extract_contacts(html)
                if found.get("email") and not company.email:
                    company.email = found["email"]
                if found.get("mobile") and not company.mobile:
                    company.mobile = found["mobile"]
                if found.get("phone") and not company.phone:
                    company.phone = found["phone"]
                company.sources.append({"provider": fetcher.name, "reference": company.website})

    if secrets.get("APIFY_TOKEN") and secrets.get("APIFY_ACTOR_ID"):
        try:
            extra = ApifyEnricher(secrets["APIFY_TOKEN"], secrets["APIFY_ACTOR_ID"]).enrich(company)
        except Exception as exc:
            company.sources.append({"provider": "apify", "reference": f"actor failed: {exc}"[:300]})
            return
        email = extra.get("email")
        if isinstance(email, list):
            email = email[0] if email else None
        if email and not company.email:
            company.email = str(email)
        landline, mobile = split_phone(extra.get("mobile") or extra.get("phone"))
        if extra.get("mobile"):
            _, mobile = split_phone(str(extra["mobile"]))
        if mobile and not company.mobile:
            company.mobile = mobile
        if landline and not company.phone:
            company.phone = landline
        website = usable_website(extra.get("website") if isinstance(extra.get("website"), str) else None)
        if website and not company.website:
            company.website = website
            company.has_website = True
        company.sources.append({"provider": "apify", "reference": secrets["APIFY_ACTOR_ID"]})
