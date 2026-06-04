"""Email parsers for ha_imap_parcel."""
from __future__ import annotations

import logging
from typing import Any

from .amazon import parse_amazon
from .base import ParsedDelivery
from .royalmail import parse_royalmail

_LOGGER = logging.getLogger(__name__)

_COURIER_PARSERS: dict[str, Any] = {
    "Amazon Logistics": parse_amazon,
    "Amazon": parse_amazon,
    "Royal Mail": parse_royalmail,
}


def parse_email(
    email_data: dict[str, Any], courier: str, status: str | None
) -> list[ParsedDelivery]:
    """Route email_data to the correct parser.

    Returns a list because one email can reference multiple orders/tracking numbers
    (e.g., Amazon multi-item shipments). Falls back to a single minimal entry on
    unknown couriers or parser failure.
    """
    parser = _COURIER_PARSERS.get(courier)
    if parser is None:
        _LOGGER.debug("No parser for courier '%s', using minimal data", courier)
        return [ParsedDelivery(status=status)]
    try:
        return parser(email_data, status)  # type: ignore[no-any-return]
    except (ValueError, AttributeError, KeyError, TypeError) as err:
        _LOGGER.warning(
            "Parser failed for courier '%s': %s: %s", courier, type(err).__name__, err
        )
        return [ParsedDelivery(status=status)]
