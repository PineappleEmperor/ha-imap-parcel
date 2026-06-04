"""Royal Mail delivery email parser."""
from __future__ import annotations

import datetime
import re
from typing import Any

from bs4 import BeautifulSoup

from .base import ParsedDelivery

# RM tracking: AB123456789GB, AB12345678GB, or 13-digit barcode
_TRACKING_RE = re.compile(
    r"\b([A-Z]{2}[0-9]{8,9}[A-Z]{2}|[A-Z]{2}[0-9]{9}GB|[0-9]{13})\b"
)
_FULL_MONTHS: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def parse_royalmail(email_data: dict[str, Any], status: str | None) -> list[ParsedDelivery]:
    """Parse a Royal Mail delivery email.

    RM sends one tracking number per email, so always returns a single-element list.
    """
    subject: str = email_data.get("subject", "")
    body_text: str = email_data.get("body_text", "")
    body_html: str = email_data.get("body_html", "")

    flat_body = body_text
    if body_html and not flat_body:
        soup = BeautifulSoup(body_html, "html.parser")
        flat_body = soup.get_text(separator=" ", strip=True)

    tracking_number: str | None = None
    for text in (flat_body, subject):
        m = _TRACKING_RE.search(text)
        if m:
            tracking_number = m.group(1)
            break

    retailer = _extract_retailer(subject)
    eta = _extract_eta(subject, flat_body)

    return [
        ParsedDelivery(
            tracking_number=tracking_number,
            retailer=retailer,
            eta=eta,
            status=status,
        )
    ]


def _extract_retailer(subject: str) -> str | None:
    """Extract retailer from RM subject patterns like 'Your parcel from <Retailer> is...'"""
    m = re.search(
        r"(?:Royal Mail )?parcel from ([\w\(\)\s\&\-\.]+?) (?:is|has)",
        subject,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _extract_eta(subject: str, body: str) -> datetime.date | None:
    """Try to extract delivery date from subject or body text."""
    today = datetime.date.today()

    if "today" in subject.lower():
        return today

    pattern = re.compile(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August"
        r"|September|October|November|December)(?:\s+(\d{4}))?",
        re.IGNORECASE,
    )
    for text in (subject, body):
        m = pattern.search(text)
        if m:
            try:
                day = int(m.group(1))
                month = _FULL_MONTHS[m.group(2).lower()]
                year = int(m.group(3)) if m.group(3) else today.year
                return datetime.date(year, month, day)
            except (ValueError, KeyError):
                pass

    return None
