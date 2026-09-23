from datetime import date

from information_hunters.scoring import ScoreInput, score_lead


AS_OF = date(2026, 9, 23)


def _score(**kwargs):
    payload = dict(company_status="active", actively_trading=True, as_of=AS_OF)
    payload.update(kwargs)
    return score_lead(ScoreInput(**payload))


def test_ideal_lead_scores_100():
    result = _score(
        has_website=False,
        email="enquiries@harbourheat.example",
        mobile="07700 900123",
        incorporation_date=date(2025, 3, 23),
    )
    assert result.score == 100
    assert result.band == "A"
    assert result.qualified is True
    assert "No website" in result.reasons
    assert "Mobile number" in result.reasons


def test_website_lowers_an_otherwise_strong_lead():
    result = _score(
        has_website=True,
        email="enquiries@harbourheat.example",
        mobile="07700 900123",
        incorporation_date=date(2025, 3, 23),
    )
    assert result.score == 60
    assert result.band == "B"
    assert "Has a website — lower priority" in result.reasons


def test_mobile_does_not_stack_with_landline_points():
    both = _score(has_website=False, mobile="07700 900123", phone="0161 496 0123", incorporation_date=date(2024, 1, 1))
    mobile_only = _score(has_website=False, mobile="07700 900123", incorporation_date=date(2024, 1, 1))
    assert both.score == mobile_only.score


def test_older_incorporation_scores_less_than_eighteen_months():
    recent = _score(has_website=False, incorporation_date=date(2025, 3, 23))
    older = _score(has_website=False, incorporation_date=date(2025, 2, 1))
    assert recent.score - older.score == 6
    assert "Incorporated within 3 years" in older.reasons


def test_dissolved_and_unverified_companies_are_not_qualified():
    dissolved = _score(has_website=False, company_status="dissolved", email="a@example.com", mobile="07700 900111")
    closed = _score(has_website=False, actively_trading=False)
    unknown = _score(has_website=False, actively_trading=None)
    assert dissolved.score == 0 and dissolved.qualified is False
    assert closed.qualified is False
    assert unknown.qualified is False


def test_missing_contact_still_ranks_a_new_company_without_a_site():
    result = _score(has_website=False, incorporation_date=date(2026, 1, 2))
    assert result.score == 64
    assert result.band == "B"
