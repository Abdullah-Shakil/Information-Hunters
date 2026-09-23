"""Pull a visible email and UK phone number from a public HTML page."""

import re

from bs4 import BeautifulSoup

from information_hunters.phones import split_phone

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+44\s?(?:\(0\)\s?)?|0)(?:\d[\s\-()]?){9,12}")
JUNK_EMAIL = ("sentry", "wixpress", "godaddy", "schema.org", "example@example", ".png", ".jpg", ".webp", ".svg", "wix.com")


def _ok_email(value: str) -> bool:
    email = value.strip().strip(".").lower()
    if "@" not in email or email.startswith("@"):
        return False
    return not any(token in email for token in JUNK_EMAIL)


def extract_contacts(html: str) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    emails: list[str] = []
    for link in soup.select("a[href]"):
        href = link.get("href") or ""
        if href.lower().startswith("mailto:"):
            emails.append(href.split(":", 1)[1].split("?")[0])
    text = soup.get_text(" ", strip=True)
    emails.extend(EMAIL_RE.findall(text))
    email = next((item.strip() for item in emails if _ok_email(item)), None)

    landline = None
    mobile = None
    for match in PHONE_RE.findall(text):
        found_landline, found_mobile = split_phone(match)
        if found_mobile and mobile is None:
            mobile = found_mobile
        elif found_landline and landline is None:
            landline = found_landline
        if mobile and landline:
            break
    return {"email": email, "phone": landline, "mobile": mobile}
