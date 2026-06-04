"""Constants for HA IMAP Parcel."""
from __future__ import annotations

from typing import TypedDict


class SenderRule(TypedDict):
    """Shape of one entry in BUILTIN_SENDER_RULES and user-defined sender rules."""

    courier: str
    confidence: str
    subject_patterns: dict[str, str]


DOMAIN = "ha_imap_parcel"
PLATFORMS = ["sensor"]

# email_ha integration
EMAIL_HA_DOMAIN = "email_ha"
EMAIL_HA_EVENT_NEW_EMAIL = "email_ha_new_email"
EMAIL_HA_SERVICE_QUERY = "query_emails"
EMAIL_HA_CONF_EMAIL = "email"

# Config / options keys
CONF_EMAIL_HA_ENTRY_IDS = "email_ha_entry_ids"
CONF_BACKFILL_DAYS = "backfill_days"
CONF_SENDER_RULES = "sender_rules"
CONF_RULE_SENDER = "sender"
CONF_RULE_COURIER = "courier"
CONF_RULE_CONFIDENCE = "confidence"

# Defaults
DEFAULT_BACKFILL_DAYS = 31
MIN_BACKFILL_DAYS = 7
MAX_BACKFILL_DAYS = 90

# Delivery statuses
STATUS_EXCEPTION = "Exception"
STATUS_OUT_FOR_DELIVERY = "Out for delivery"
STATUS_DISPATCHED = "Dispatched"
STATUS_ORDERED = "Ordered"
STATUS_DELIVERED = "Delivered"

# Lower rank means closer to delivery. A status only replaces another if it has a lower rank.
STATUS_RANK: dict[str, int] = {
    STATUS_DELIVERED: 0,
    STATUS_EXCEPTION: 1,
    STATUS_OUT_FOR_DELIVERY: 2,
    STATUS_DISPATCHED: 3,
    STATUS_ORDERED: 4,
}

ACTIVE_STATUSES: frozenset[str] = frozenset(
    {STATUS_ORDERED, STATUS_DISPATCHED, STATUS_OUT_FOR_DELIVERY, STATUS_EXCEPTION}
)

# Confidence levels
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

CONFIDENCE_OPTIONS: dict[str, str] = {
    CONFIDENCE_HIGH: "High (known delivery sender)",
    CONFIDENCE_MEDIUM: "Medium (likely delivery sender)",
    CONFIDENCE_LOW: "Low (uncertain)",
}

# Storage
STORAGE_KEY = f"{DOMAIN}.deliveries"
STORAGE_VERSION = 1

# Human-readable codes for negative days_until_next_delivery values (mirrors parcel-ha)
DAYS_RETURN_CODES: dict[int, str] = {
    -1: "No active deliveries.",
    -2: "Active delivery, no ETA.",
    -3: "Error",
}

# Built-in sender rules: exact sender address → courier/confidence/subject→status mapping.
# Subject patterns use substring matching (case-sensitive, as per real email subjects).
BUILTIN_SENDER_RULES: dict[str, SenderRule] = {
    "no-reply@royalmail.com": {
        "courier": "Royal Mail",
        "confidence": CONFIDENCE_HIGH,
        "subject_patterns": {
            "has been delivered": STATUS_DELIVERED,
            "is due to be delivered today": STATUS_OUT_FOR_DELIVERY,
            "is on its way": STATUS_DISPATCHED,
            "has encountered an issue": STATUS_EXCEPTION,
        },
    },
    "shipment-tracking@amazon.co.uk": {
        "courier": "Amazon Logistics",
        "confidence": CONFIDENCE_HIGH,
        "subject_patterns": {
            "Delivered:": STATUS_DELIVERED,
            "Out for delivery:": STATUS_OUT_FOR_DELIVERY,
            "Dispatched:": STATUS_DISPATCHED,
        },
    },
    "auto-confirm@amazon.co.uk": {
        "courier": "Amazon",
        "confidence": CONFIDENCE_HIGH,
        "subject_patterns": {
            "Ordered:": STATUS_ORDERED,
        },
    },
    "order-update@amazon.co.uk": {
        "courier": "Amazon",
        "confidence": CONFIDENCE_HIGH,
        "subject_patterns": {
            "Delivered:": STATUS_DELIVERED,
        },
    },
}
