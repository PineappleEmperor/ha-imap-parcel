"""Persistent storage for delivery orders."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class DeliveryStore:
    """Persist delivery records to .storage/imap_parcel.deliveries_<entry_id>."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}"
        )
        self._deliveries: dict[str, dict[str, Any]] = {}
        # UIDs of emails already ingested in a previous run — skip on backfill.
        self._processed_uids: set[str] = set()

    async def async_load(self) -> None:
        """Load deliveries and processed-UID set from storage on startup."""
        data = await self._store.async_load()
        self._deliveries = (data or {}).get("deliveries", {})
        self._processed_uids = set((data or {}).get("processed_uids", []))
        _LOGGER.debug(
            "Loaded %d deliveries, %d known UIDs from storage",
            len(self._deliveries),
            len(self._processed_uids),
        )

    def is_uid_known(self, uid: str) -> bool:
        """Return True if this email UID was already processed in a previous run."""
        return uid in self._processed_uids

    def get_all(self) -> list[dict[str, Any]]:
        """Return all deliveries as a list."""
        return list(self._deliveries.values())

    def get(self, delivery_id: str) -> dict[str, Any] | None:
        """Return a single delivery by ID, or None."""
        return self._deliveries.get(delivery_id)

    def find_by_order_number(self, order_number: str) -> str | None:
        """Return delivery_id of first delivery matching this order number, or None."""
        for did, d in self._deliveries.items():
            if d.get("order_number") == order_number:
                return did
        return None

    def find_by_tracking_number(self, tracking_number: str) -> str | None:
        """Return delivery_id of first delivery matching this tracking number, or None."""
        for did, d in self._deliveries.items():
            if d.get("tracking_number") == tracking_number:
                return did
        return None

    async def async_upsert(self, delivery_id: str, data: dict[str, Any]) -> None:
        """Insert or update a delivery and persist."""
        self._deliveries[delivery_id] = data
        await self._store.async_save(
            {"deliveries": self._deliveries, "processed_uids": list(self._processed_uids)}
        )

    async def async_mark_uid(self, uid: str) -> None:
        """Record that an email UID has been fully handled (upserted or intentionally skipped)."""
        self._processed_uids.add(uid)
        await self._store.async_save(
            {"deliveries": self._deliveries, "processed_uids": list(self._processed_uids)}
        )

    async def async_expire(self, max_age_days: int = 60) -> int:
        """Remove Delivered parcels older than max_age_days. Returns count removed."""
        cutoff = datetime.now(UTC).timestamp() - (max_age_days * 86400)
        to_remove = [
            k
            for k, v in self._deliveries.items()
            if v.get("status") == "Delivered"
            and float(v.get("last_updated_ts", 0)) < cutoff
        ]
        for k in to_remove:
            del self._deliveries[k]
        if to_remove:
            await self._store.async_save(
                {"deliveries": self._deliveries, "processed_uids": list(self._processed_uids)}
            )
        return len(to_remove)
