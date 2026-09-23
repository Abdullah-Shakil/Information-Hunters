from dataclasses import dataclass, field
from datetime import date


@dataclass
class DiscoveredCompany:
    company_number: str
    name: str
    category: str
    region: str
    source: str
    raw: dict = field(default_factory=dict)


@dataclass
class EnrichedCompany:
    company_number: str
    name: str
    category: str
    region: str
    address: str = ""
    postcode: str = ""
    sic_codes: list[str] = field(default_factory=list)
    sic_labels: list[str] = field(default_factory=list)
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    website: str | None = None
    has_website: bool = False
    incorporation_date: date | None = None
    company_status: str = "active"
    synthetic: bool = False
    sources: list[dict] = field(default_factory=list)


@dataclass
class Verification:
    actively_trading: bool | None
    notes: str
    source: str
    evidence: dict = field(default_factory=dict)


class ProviderError(RuntimeError):
    pass


class ProviderAuthError(ProviderError):
    pass
