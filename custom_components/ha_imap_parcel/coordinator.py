"""Coordinator for HA IMAP Parcel."""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .classifier import EmailClassifier
from .const import (
    BUILTIN_SENDER_RULES,
    CONF_BACKFILL_DAYS,
    CONF_EMAIL_HA_ENTRY_IDS,
    CONF_RULE_SENDER,
    CONF_SENDER_RULES,
    DEFAULT_BACKFILL_DAYS,
    DOMAIN,
    EMAIL_HA_CONF_EMAIL,
    EMAIL_HA_DOMAIN,
    EMAIL_HA_EVENT_NEW_EMAIL,
    EMAIL_HA_SERVICE_QUERY,
    STATUS_RANK,
)
from .parsers import parse_email
from .store import DeliveryStore

_LOGGER = logging.getLogger(__name__)


def _delivery_id(order_number: str | None, tracking_number: str | None, uid: str) -> str:
    """Generate a stable 16-char delivery ID from the best available identifier."""
    key = order_number or tracking_number or uid
    return hashlib.sha1(key.encode()).hexdigest()[:16]  # noqa: S324


def _resolve_delivery_id(
    store: DeliveryStore,
    order_number: str | None,
    tracking_number: str | None,
    uid: str,
) -> str:
    """Find existing delivery by order/tracking number cross-reference or create a new ID."""
    if order_number:
        existing = store.find_by_order_number(order_number)
        if existing:
            return existing
    if tracking_number:
        existing = store.find_by_tracking_number(tracking_number)
        if existing:
            return existing
    return _delivery_id(order_number, tracking_number, uid)


class ParcelTrackingCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Manages delivery DB."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry = entry
        self._store = DeliveryStore(hass, entry.entry_id)
        self._classifier = self._build_classifier()
        self._email_ha_entry_ids: list[str] = list(entry.data.get(CONF_EMAIL_HA_ENTRY_IDS, []))
        self._backfill_days: int = entry.options.get(
            CONF_BACKFILL_DAYS,
            entry.data.get(CONF_BACKFILL_DAYS, DEFAULT_BACKFILL_DAYS),
        )
        # email_address (str) → email_ha config entry_id (str)
        self._email_entry_map: dict[str, str] = {}
        self._unsub: list[Any] = []

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(hours=1),
        )

    def _build_classifier(self) -> EmailClassifier:
        extra: list[dict[str, Any]] = self._entry.options.get(CONF_SENDER_RULES, [])
        return EmailClassifier(extra_rules=extra)


    async def _async_setup(self) -> None:
        """One-time init: load store, resolve email addresses, backfill, subscribe."""
        _LOGGER.info("Setting up HA IMAP Parcel coordinator")
        await self._store.async_load()
        self._resolve_email_addresses()
        if not self._email_entry_map:
            _LOGGER.warning("No email_ha entries resolved — backfill and event tracking will be skipped")
        await self._async_backfill()
        self._subscribe_events()
        _LOGGER.info(
            "Setup complete: %d deliveries in store, watching %d email account(s)",
            len(self._store.get_all()),
            len(self._email_entry_map),
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Hourly: expire old delivered parcels and return current list."""
        removed = await self._store.async_expire(max_age_days=60)
        if removed:
            _LOGGER.debug("Expired %d old deliveries", removed)
        return self._store.get_all()


    def _resolve_email_addresses(self) -> None:
        """Build email_address → email_ha entry_id map from configured entries."""
        self._email_entry_map = {}
        for entry_id in self._email_ha_entry_ids:
            ha_entry = self.hass.config_entries.async_get_entry(entry_id)
            if ha_entry is None:
                _LOGGER.warning("email_ha entry %s not found — skipping", entry_id)
                continue
            email_addr: str = ha_entry.data.get(EMAIL_HA_CONF_EMAIL, "")
            if email_addr:
                self._email_entry_map[email_addr] = entry_id
                _LOGGER.debug("Tracking email address: %s (entry %s)", email_addr, entry_id)

    def _subscribe_events(self) -> None:
        """Subscribe to email_ha_new_email events for configured accounts."""

        @callback
        def _on_new_email(event: Event) -> None:  # type: ignore[type-arg]
            email_address: str = event.data.get("email_address", "")
            if email_address not in self._email_entry_map:
                return
            self.hass.async_create_task(
                self._async_process_email_event(event.data),
                name=f"{DOMAIN}:process_email",
            )

        self._unsub.append(
            self.hass.bus.async_listen(EMAIL_HA_EVENT_NEW_EMAIL, _on_new_email)
        )

    def unsubscribe(self) -> None:
        """Cancel all event subscriptions (called on entry unload)."""
        for unsub in self._unsub:
            unsub()
        self._unsub = []


    async def _async_backfill(self) -> None:
        """Query email_ha for delivery emails from the last N days, one sender at a time."""
        since = (datetime.now(UTC) - timedelta(days=self._backfill_days)).strftime("%d-%b-%Y")

        known_senders = list(BUILTIN_SENDER_RULES.keys())
        for rule in self._entry.options.get(CONF_SENDER_RULES, []):
            sender = rule.get(CONF_RULE_SENDER, "").strip()
            if sender:
                known_senders.append(sender)

        _LOGGER.info(
            "Backfilling from %s across %d entry(s), %d known sender(s)",
            since,
            len(self._email_ha_entry_ids),
            len(known_senders),
        )
        for entry_id in self._email_ha_entry_ids:
            for sender in known_senders:
                await self._async_query_and_process(
                    entry_id=entry_id,
                    criteria=f"SINCE {since} FROM {sender}",
                    max_results=50,
                )

        all_deliveries = self._store.get_all()
        _LOGGER.info("Backfill complete: %d deliveries in store", len(all_deliveries))
        self.async_set_updated_data(all_deliveries)

    async def _async_query_and_process(
        self, entry_id: str, criteria: str, max_results: int = 50
    ) -> None:
        """Call email_imap.query_emails and process each result."""
        try:
            result = await self.hass.services.async_call(
                EMAIL_HA_DOMAIN,
                EMAIL_HA_SERVICE_QUERY,
                {
                    "config_entry_id": entry_id,
                    "search_criteria": criteria,
                    "max_results": max_results,
                    "include_full_body": True,
                },
                blocking=True,
                return_response=True,
            )
            emails: list[dict[str, Any]] = cast(
                list[dict[str, Any]], (result or {}).get("emails", [])
            )
            _LOGGER.info(
                "Query '%s' via entry %s → %d emails", criteria, entry_id, len(emails)
            )
            for email_data in emails:
                await self._async_process_email(email_data, entry_id)
        except (HomeAssistantError, vol.Invalid) as err:
            _LOGGER.warning(
                "email_imap query failed (entry %s, '%s'): %s: %s",
                entry_id,
                criteria,
                type(err).__name__,
                err,
            )


    async def _async_process_email_event(self, event_data: Mapping[str, Any]) -> None:
        """Handle email_ha_new_email: classify from preview, fetch full body if matched."""
        email_address: str = str(event_data.get("email_address", ""))
        entry_id = self._email_entry_map.get(email_address)
        if entry_id is None:
            return

        sender: str = str(event_data.get("sender_email", ""))
        subject: str = str(event_data.get("subject", ""))
        courier = self._classifier.classify(sender, subject)[0]
        if courier is None:
            return  # Not a delivery email — ignore

        uid: str = str(event_data.get("uid", ""))
        await self._async_query_and_process(
            entry_id=entry_id,
            criteria=f"UID {uid}",
            max_results=1,
        )


    async def _async_process_email(
        self, email_data: dict[str, Any], entry_id: str
    ) -> None:
        """Classify, parse, and upsert a single email into the delivery store."""
        sender: str = email_data.get("sender_email", "")
        subject: str = email_data.get("subject", "")
        uid: str = str(email_data.get("uid", ""))

        courier, status, confidence = self._classifier.classify(sender, subject)
        if courier is None:
            _LOGGER.debug("No rule matched sender=%s subject=%s — skipping", sender, subject)
            return

        _LOGGER.debug("Classified email uid=%s as courier=%s status=%s confidence=%s", uid, courier, status, confidence)
        if self._store.is_uid_known(uid):
            _LOGGER.debug("Skipping already-processed UID %s", uid)
            return

        # One email may reference multiple order/tracking numbers (e.g., Amazon split shipments).
        parsed_list = parse_email(email_data, courier, status)
        updated = False

        for parsed in parsed_list:
            delivery_id = _resolve_delivery_id(self._store, parsed.order_number, parsed.tracking_number, uid)
            existing = self._store.get(delivery_id)
            new_status = parsed.status or status or "Unknown"

            if existing:
                existing_rank = STATUS_RANK.get(existing["status"], 99)
                new_rank = STATUS_RANK.get(new_status, 99)
                if new_rank > existing_rank:
                    # This email represents an earlier state than what's stored.
                    # Mark UID processed so we never revisit it, but skip the upsert.
                    _LOGGER.debug(
                        "Email superseded for delivery %s: stored=%s, email=%s — skipping",
                        delivery_id,
                        existing["status"],
                        new_status,
                    )
                    continue
                new_status = existing["status"] if new_rank == existing_rank else new_status

            now_ts = datetime.now(UTC).timestamp()
            now_iso = datetime.now(UTC).isoformat()

            delivery: dict[str, Any] = {
                "id": delivery_id,
                "retailer": parsed.retailer or courier,
                "courier": courier,
                "order_number": parsed.order_number or (existing or {}).get("order_number"),
                "tracking_number": parsed.tracking_number or (existing or {}).get("tracking_number"),
                "status": new_status,
                "eta": parsed.eta.isoformat() if parsed.eta else (existing or {}).get("eta"),
                "first_seen": (existing or {}).get("first_seen", now_iso),
                "last_updated": now_iso,
                "last_updated_ts": now_ts,
                "source_entry_id": entry_id,
                "confidence": confidence,
            }

            await self._store.async_upsert(delivery_id, delivery)
            updated = True
            _LOGGER.debug(
                "Upserted delivery %s: %s (%s) → %s",
                delivery_id,
                courier,
                parsed.order_number or parsed.tracking_number or uid,
                new_status,
            )

        # Mark the email UID as handled regardless of whether any delivery was upserted.
        await self._store.async_mark_uid(uid)
        if updated:
            self.async_set_updated_data(self._store.get_all())
