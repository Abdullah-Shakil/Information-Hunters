"""Priority scoring for website and CRM leads.

Ideal lead (score 100): no website, email, mobile, incorporated within 18
months, and verified as actively trading.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ScoreInput:
    has_website: bool
    email: str | None = None
    mobile: str | None = None
    phone: str | None = None
    incorporation_date: date | None = None
    company_status: str = "active"
    actively_trading: bool | None = None
    as_of: date | None = None


@dataclass(frozen=True)
class ScoreResult:
    score: int
    reasons: list[str]
    qualified: bool
    band: str


def band_for(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"


def _present(value: str | None) -> bool:
    return bool(value and str(value).strip())


def _months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def score_lead(lead: ScoreInput) -> ScoreResult:
    status = (lead.company_status or "").strip().lower()
    if status and status != "active":
        return ScoreResult(0, ["Company is not active on the registry"], False, "D")
    if lead.actively_trading is False:
        return ScoreResult(0, ["Not verified as actively trading"], False, "D")
    if lead.actively_trading is None:
        return ScoreResult(0, ["Trading status unknown"], False, "D")

    score = 0
    reasons: list[str] = []

    if lead.has_website:
        reasons.append("Has a website — lower priority")
    else:
        score += 40
        reasons.append("No website")

    if _present(lead.email):
        score += 18
        reasons.append("Email on file")

    if _present(lead.mobile):
        score += 18
        reasons.append("Mobile number")
    elif _present(lead.phone):
        score += 6
        reasons.append("Landline only")

    as_of = lead.as_of or date.today()
    if lead.incorporation_date is not None:
        age = _months_between(lead.incorporation_date, as_of)
        if age <= 18:
            score += 16
            reasons.append("Incorporated within 18 months")
        elif age <= 36:
            score += 10
            reasons.append("Incorporated within 3 years")
        elif age <= 60:
            score += 4
            reasons.append("Incorporated within 5 years")
        else:
            reasons.append("Established company")

    score += 8
    reasons.append("Verified actively trading")
    score = max(0, min(100, score))
    return ScoreResult(score, reasons, True, band_for(score))
