"""Synthetic catalogue so the product runs with no paid keys.

Numbers are in the Ofcom drama ranges. Domains use the reserved .example TLD.
"""

from __future__ import annotations

from datetime import date

from information_hunters.categories import category_by_id, region_by_id
from information_hunters.phones import format_uk
from information_hunters.providers.base import DiscoveredCompany, EnrichedCompany, Verification

STEMS: dict[str, list[tuple[str, str]]] = {
    "plumbers": [("Harbour Heat", "harbourheat"), ("Northpipe", "northpipe"), ("Moss Valve", "mossvalve"), ("Calder Flow", "calderflow"), ("Quay Plumbing", "quayplumbing"), ("Bricklane Heating", "bricklaneheat")],
    "electricians": [("Lumen House", "lumenhouse"), ("Grid Sparrow", "gridsparrow"), ("Volt House", "volthouse"), ("Arc Lime", "arclime"), ("Parish Electrical", "parishelectrical"), ("Beacon Circuit", "beaconcircuit")],
    "painters": [("Limewash Studio", "limewash"), ("Ochre Pine", "ochrepine"), ("Fieldcoat", "fieldcoat"), ("Gable Brush", "gablebrush"), ("Soffit Painting", "soffitpainting"), ("Atelier White", "atelierwhite")],
    "gardeners": [("Hearth Hedge", "hearthhedge"), ("Southlawn", "southlawn"), ("Orchard Grounds", "orchardgrounds"), ("Moss Path", "mosspath"), ("Terrace Thyme", "terracethyme"), ("Green Course", "greencourse")],
    "solicitors": [("Hale Rowan", "halerowan"), ("Northbridge Legal", "northbridgelegal"), ("Quill Court", "quillcourt"), ("Marsh Lane Solicitors", "marshlane"), ("Whitlow Law", "whitlowlaw"), ("Paper Pier", "paperpier")],
    "roofers": [("Ridge Rain", "ridgerain"), ("Slatehouse", "slatehouse"), ("Eaves Co", "eavesco"), ("High Gable Roofing", "highgable"), ("Pinnacle Slate", "pinnacleslate"), ("Loom Roofing", "loomroofing")],
    "cleaners": [("Clearstore", "clearstore"), ("Bright Threshold", "brightthreshold"), ("Linen Key", "linenkey"), ("Morning Rooms", "morningrooms"), ("Glass Porch", "glassporch"), ("Civic Clean", "civicclean")],
    "hairdressers": [("Comb Copper", "combcopper"), ("Low Lounge", "lowlounge"), ("Shear House", "shearhouse"), ("Basin Wool", "basinwool"), ("Friday Chair", "fridaychair"), ("Atelier North", "ateliern")],
}

# website, email, mobile, landline, months_ago, trading, company_status
TRAITS = [
    (False, True, True, False, 8, True, "active"),
    (False, False, True, False, 4, True, "active"),
    (False, True, False, True, 14, True, "active"),
    (False, False, False, True, 30, True, "active"),
    (True, True, True, False, 6, True, "active"),
    (True, False, False, True, 90, True, "active"),
    (False, True, True, False, 3, False, "active"),
    (False, False, True, False, 10, True, "dissolved"),
]


def _shift_months(today: date, months: int) -> date:
    month = today.month - months
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    day = min(today.day, 28)
    return date(year, month, day)


def _landline(dial: str, n: int) -> str:
    if dial == "020":
        return f"020 7946 {n % 1000:04d}"
    if dial == "029":
        return f"029 2018 {n % 1000:04d}"
    return f"{dial} 496 {n % 1000:04d}"


def build_record(category: str, region: str, index: int, today: date | None = None) -> dict | None:
    stems = STEMS.get(category)
    region_meta = region_by_id(region)
    category_meta = category_by_id(category)
    if not stems or region_meta is None or category_meta is None:
        return None
    if index >= len(TRAITS):
        return None
    today = today or date.today()
    stem, slug = stems[index % len(stems)]
    website, email, mobile, landline, months, trading, status = TRAITS[index]
    number = f"DEMO-{category[:3].upper()}-{region[:3].upper()}-{index + 1:02d}"
    seq = (index + 1) * 17
    mobile_no = format_uk(f"07700900{seq % 1000:03d}") if mobile else None
    phone = _landline(region_meta["dial"], seq) if landline and not mobile else None
    if mobile and not landline:
        phone = None
    site = f"https://{slug}.example" if website else None
    mail = f"enquiries@{slug}.example" if email and website else (f"enquiries.{slug}@example.com" if email else None)
    incorporated = _shift_months(today, months)
    return {
        "company_number": number,
        "name": f"{stem} Ltd",
        "category": category,
        "region": region,
        "address": f"{10 + index} Tariff Street, {region}",
        "postcode": "",
        "sic_codes": [category_meta["sic"]],
        "sic_labels": [category_meta["sic_label"]],
        "phone": phone,
        "mobile": mobile_no,
        "email": mail,
        "website": site,
        "has_website": bool(website),
        "incorporation_date": incorporated.isoformat(),
        "company_status": status,
        "actively_trading": trading and status == "active",
        "synthetic": True,
    }


class DemoDiscovery:
    name = "demo"

    def discover(self, category: str, region: str, limit: int, incorporated_after: date | None = None) -> list[DiscoveredCompany]:
        found: list[DiscoveredCompany] = []
        for index in range(min(limit, len(TRAITS))):
            record = build_record(category, region, index)
            if record is None:
                continue
            if incorporated_after and date.fromisoformat(record["incorporation_date"]) < incorporated_after:
                continue
            found.append(
                DiscoveredCompany(
                    company_number=record["company_number"],
                    name=record["name"],
                    category=category,
                    region=region,
                    source="demo",
                    raw=record,
                )
            )
        return found


class DemoEnricher:
    name = "demo"

    def enrich(self, company: DiscoveredCompany) -> EnrichedCompany:
        raw = company.raw
        return EnrichedCompany(
            company_number=company.company_number,
            name=raw.get("name", company.name),
            category=company.category,
            region=company.region,
            address=raw.get("address", ""),
            postcode=raw.get("postcode", ""),
            sic_codes=list(raw.get("sic_codes") or []),
            sic_labels=list(raw.get("sic_labels") or []),
            phone=raw.get("phone"),
            mobile=raw.get("mobile"),
            email=raw.get("email"),
            website=raw.get("website"),
            has_website=bool(raw.get("has_website")),
            incorporation_date=date.fromisoformat(raw["incorporation_date"]) if raw.get("incorporation_date") else None,
            company_status=raw.get("company_status", "active"),
            synthetic=True,
            sources=[{"provider": "demo", "reference": "synthetic-catalogue"}],
        )


class DemoVerifier:
    name = "demo"

    def verify(self, company: EnrichedCompany) -> Verification:
        trading = bool(company.sources) or True
        # Trading flag is stored on the discovery raw record and copied via a side channel
        # on the enriched company through company_status plus the synthetic source note.
        return Verification(
            actively_trading=None,
            notes="pending",
            source="demo",
        )


def demo_trading(company: DiscoveredCompany) -> bool:
    return bool(company.raw.get("actively_trading"))
