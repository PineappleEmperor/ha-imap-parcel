"""Sensors for IMAP Parcel."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ACTIVE_STATUSES, DAYS_RETURN_CODES, DOMAIN, STATUS_DELIVERED
from .coordinator import ParcelTrackingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: ParcelTrackingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ActiveDeliveriesSensor(coordinator),
            RecentDeliverySensor(coordinator),
            RawDeliveriesSensor(coordinator),
        ],
        update_before_add=True,
    )


def _make_device_info(coordinator: ParcelTrackingCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="IMAP Parcel",
        manufacturer="IMAP Parcel",
        model="Email-based tracking",
        entry_type=DeviceEntryType.SERVICE,
    )


class ActiveDeliveriesSensor(  # type: ignore[misc]
    CoordinatorEntity[ParcelTrackingCoordinator], SensorEntity
):
    """State = count of active (non-delivered) deliveries.

    Mirrors parcel-ha's ActiveShipment, adapted for email-derived data.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "parcels"
    _attr_icon = "mdi:package"

    def __init__(self, coordinator: ParcelTrackingCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Active Deliveries"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_active_deliveries"
        self._attr_device_info = _make_device_info(coordinator)
        self._attr_native_value = None
        self._attr_extra_state_attributes: dict[str, Any] = {}  # type: ignore[assignment]

    def _handle_coordinator_update(self) -> None:
        deliveries: list[dict[str, Any]] = self.coordinator.data or []
        today = date.today()

        active = [d for d in deliveries if d.get("status") in ACTIVE_STATUSES]
        delivered_today = [
            d
            for d in deliveries
            if d.get("status") == STATUS_DELIVERED and d.get("eta") == today.isoformat()
        ]

        # Traceable = active + valid ETA on or after today
        traceable: list[tuple[date, dict[str, Any]]] = []
        for d in active:
            eta_str = d.get("eta")
            if eta_str:
                try:
                    eta_date = date.fromisoformat(str(eta_str))
                    if eta_date >= today:
                        traceable.append((eta_date, d))
                except ValueError:
                    pass
        traceable.sort(key=lambda x: x[0])

        if traceable:
            next_eta, next_delivery = traceable[0]
            days_until: int = (next_eta - today).days
        else:
            next_delivery = None
            days_until = -2 if active else -1

        # Icon mirrors parcel-ha numeric pattern
        if days_until < 0:
            icon_map = {-1: "mdi:shopping", -2: "mdi:help-circle"}
            self._attr_icon = icon_map.get(days_until, "mdi:close-circle")
        elif days_until == 0:
            self._attr_icon = "mdi:package"
        elif days_until > 9:
            self._attr_icon = "mdi:numeric-9-plus-circle"
        else:
            self._attr_icon = f"mdi:numeric-{days_until}-circle"

        arriving_today = sum(1 for eta, _ in traceable if eta == today)

        if arriving_today > 0:
            n = arriving_today
            verbose = f"{'1 parcel' if n == 1 else f'{n} parcels'} today"
        elif days_until > 0:
            verbose = f"in {'1 day' if days_until == 1 else f'{days_until} days'}"
        elif days_until == -2:
            n = len(active)
            verbose = f"{n} active {'parcel' if n == 1 else 'parcels'}, no ETA"
        else:
            verbose = "No active deliveries"

        days_display: int | str = (
            DAYS_RETURN_CODES.get(days_until, str(days_until)) if days_until < 0 else days_until
        )

        self._attr_native_value = len(active)
        self._attr_extra_state_attributes = {
            "status_text": verbose,
            "number_of_active_deliveries": len(active),
            "deliveries_arriving_today": arriving_today,
            "delivered_today": len(delivered_today),
            "days_until_next_delivery": days_display,
            "next_courier": (next_delivery or {}).get("courier"),
            "next_retailer": (next_delivery or {}).get("retailer"),
            "next_order_number": (next_delivery or {}).get("order_number"),
            "next_tracking_number": (next_delivery or {}).get("tracking_number"),
            "next_eta": (next_delivery or {}).get("eta"),
            "next_status": (next_delivery or {}).get("status"),
            "active_deliveries": [
                {
                    "id": d.get("id"),
                    "retailer": d.get("retailer"),
                    "courier": d.get("courier"),
                    "status": d.get("status"),
                    "eta": d.get("eta"),
                    "order_number": d.get("order_number"),
                    "tracking_number": d.get("tracking_number"),
                    "confidence": d.get("confidence"),
                }
                for d in active
            ],
        }
        self.async_write_ha_state()


class RecentDeliverySensor(  # type: ignore[misc]
    CoordinatorEntity[ParcelTrackingCoordinator], SensorEntity
):
    """State = status of the most recently updated delivery. Disabled by default."""

    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:package-variant"

    def __init__(self, coordinator: ParcelTrackingCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Recent Delivery"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_recent_delivery"
        self._attr_device_info = _make_device_info(coordinator)
        self._attr_native_value = None
        self._attr_extra_state_attributes: dict[str, Any] = {}  # type: ignore[assignment]

    def _handle_coordinator_update(self) -> None:
        deliveries: list[dict[str, Any]] = self.coordinator.data or []
        if not deliveries:
            self._attr_native_value = "No deliveries"
            self._attr_extra_state_attributes = {}
        else:
            recent = max(deliveries, key=lambda d: float(d.get("last_updated_ts") or 0))
            self._attr_native_value = str(recent.get("status", "Unknown"))
            self._attr_extra_state_attributes = {
                k: v for k, v in recent.items() if k not in ("id", "last_updated_ts")
            }
        self.async_write_ha_state()


class RawDeliveriesSensor(  # type: ignore[misc]
    CoordinatorEntity[ParcelTrackingCoordinator], SensorEntity
):
    """Full delivery list for debugging. Disabled by default."""

    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:package-down"

    def __init__(self, coordinator: ParcelTrackingCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Raw Deliveries"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_raw_deliveries"
        self._attr_device_info = _make_device_info(coordinator)
        self._attr_native_value = None
        self._attr_extra_state_attributes: dict[str, Any] = {}  # type: ignore[assignment]

    def _handle_coordinator_update(self) -> None:
        deliveries: list[dict[str, Any]] = self.coordinator.data or []
        self._attr_native_value = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        self._attr_extra_state_attributes = {
            "deliveries": deliveries,
            "count": len(deliveries),
        }
        self.async_write_ha_state()
