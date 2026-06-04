"""Amazon UK delivery email parser."""
from __future__ import annotations

import datetime
import re
from typing import Any

from bs4 import BeautifulSoup

from .base import ParsedDelivery

_ORDER_RE = re.compile(r"(?P<order>[0-9]{3}-[0-9]{7}-[0-9]{7})")
_MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_amazon(email_data: dict[str, Any], status: str | None) -> list[ParsedDelivery]:
    """Parse an Amazon UK delivery email.

    Returns one ParsedDelivery per distinct order number found.
    Amazon often packs multiple order numbers into a single email
    (e.g., split shipments), and dispatch emails can carry multiple
    tracking numbers for the same order.
    """
    subject: str = email_data.get("subject", "")
    body_text: str = email_data.get("body_text", "")
    body_html: str = email_data.get("body_html", "")

    search_text = body_html or body_text

    # Deduplicated list preserving first-seen order
    order_numbers = list(
        dict.fromkeys(_ORDER_RE.findall(search_text) + _ORDER_RE.findall(subject))
    )

    # Extract retailer from HTML ("Sold by: Retailer" & "Dispatched by Retailer")
    retailer: str | None = None
    if body_html:
        soup = BeautifulSoup(body_html, "html.parser")
        flat = soup.get_text(separator=" ", strip=True)
        m = re.search(
            r"(?:Sold by|Dispatched by)[:\s]+([A-Za-z0-9\s&'\-\.]+?)(?:\s{2,}|\||$)",
            flat,
        )
        if m:
            retailer = m.group(1).strip()

    eta = _extract_eta(subject)

    if not order_numbers:
        # No order number found — create one anonymous entry so the email isn't lost
        return [ParsedDelivery(retailer=retailer or "Amazon UK", eta=eta, status=status)]

    return [
        ParsedDelivery(
            order_number=order_number,
            retailer=retailer or "Amazon UK",
            eta=eta,
            status=status,
        )
        for order_number in order_numbers
    ]


def _extract_eta(subject: str) -> datetime.date | None:
    """Try to extract a delivery date from an Amazon subject line."""
    today = datetime.date.today()

    if "today" in subject.lower():
        return today

    m = re.search(
        r"(?:arriving|by|on)\s+(?:\w+\s+)?(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?",
        subject,
        re.IGNORECASE,
    )
    if m:
        try:
            day = int(m.group(1))
            month = _MONTHS.get(m.group(2)[:3].lower())
            year = int(m.group(3)) if m.group(3) else today.year
            if month:
                candidate = datetime.date(year, month, day)
                if (today - candidate).days > 7:
                    candidate = datetime.date(year + 1, month, day)
                return candidate
        except (ValueError, TypeError):
            pass

    return None
