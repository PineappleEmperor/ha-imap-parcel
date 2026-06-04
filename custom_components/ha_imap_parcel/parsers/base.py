"""Base types for delivery email parsers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class ParsedDelivery:
    """Structured output from a delivery email parser."""

    order_number: str | None = None
    tracking_number: str | None = None
    retailer: str | None = None
    eta: date | None = None
    status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
