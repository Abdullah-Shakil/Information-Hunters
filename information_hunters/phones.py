"""UK phone normalisation. Mobiles are 07 numbers, excluding 070 personal numbers."""

import re


def normalise_uk_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if digits.startswith("0044"):
        digits = digits[4:]
    elif digits.startswith("44"):
        digits = digits[2:]
    digits = digits.lstrip("0")
    if not digits:
        return None
    digits = "0" + digits
    if len(digits) not in {10, 11}:
        return None
    return digits


def is_mobile(digits: str | None) -> bool:
    if not digits:
        return False
    return len(digits) == 11 and digits.startswith("07") and not digits.startswith("070")


def format_uk(digits: str) -> str:
    if digits.startswith("07") and len(digits) == 11:
        return f"{digits[:5]} {digits[5:]}"
    if digits.startswith("02") and len(digits) == 11:
        return f"{digits[:3]} {digits[3:7]} {digits[7:]}"
    if len(digits) == 11:
        return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
    return digits


def split_phone(raw: str | None) -> tuple[str | None, str | None]:
    """Return (landline, mobile). A mobile is not also stored as a landline."""
    digits = normalise_uk_phone(raw)
    if not digits:
        return None, None
    pretty = format_uk(digits)
    if is_mobile(digits):
        return None, pretty
    return pretty, None
