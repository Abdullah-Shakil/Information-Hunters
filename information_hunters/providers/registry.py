from information_hunters.providers.base import EnrichedCompany, Verification


class RegistryVerifier:
    """Companies House company_status only. Used when Google Places is not configured."""

    name = "registry"

    def verify(self, company: EnrichedCompany) -> Verification:
        active = (company.company_status or "").lower() == "active"
        if active:
            notes = "Registry status is active. Google Places was not used, so a live shopfront was not checked."
        else:
            notes = f"Registry status is {company.company_status or 'unknown'}."
        return Verification(actively_trading=active, notes=notes, source="registry")
