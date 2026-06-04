[![release][release-badge]][release-url]
[![commits-since-latest][commits-badge]][commits-url]
![stars][stars-badge]
\
![hassfest][hassfest-badge]
![hacs valid][hacs-valid-badge]
![python][python-badge]

# HA IMAP Parcel for Home Assistant

Tracks parcel deliveries by scanning incoming emails via the [Email HA](https://github.com/PineappleEmperor/email-ha) integration. No courier API accounts required — delivery status is derived directly from the emails your retailers and couriers already send you.

---

## Features

| What | Details |
|---|---|
| **Real-time updates** | Listens for `email_ha_new_email` events and processes matching emails instantly |
| **Backfill on startup** | Queries the last N days of delivery emails on first run so historical orders appear immediately |
| **Deduplication** | Processed email UIDs are persisted — restarts never double-count emails |
| **Multi-order emails** | Handles Amazon emails that reference multiple order numbers in a single message |
| **Cross-source linking** | Merges retailer and courier emails (e.g. Tubby Tom's dispatch + Royal Mail tracking) when they share an order or tracking number |
| **Status precedence** | A "Delivered" status is never overwritten by an earlier-state email for the same parcel |
| **Custom sender rules** | Add your own sender → courier mappings via the options flow |
| **Auto-expiry** | Delivered parcels are removed from the database after 60 days |

---

## Prerequisites

- [Email HA](https://github.com/PineappleEmperor/email-ha) installed and configured with at least one IMAP account.

---

## Installation

### HACS (recommended)

1. In HACS go to **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/PineappleEmperor/ha-imap-parcel` with category **Integration**.
3. Install **IMAP Parcel** and restart Home Assistant.

### Manual

Copy `custom_components/ha_imap_parcel/` into your HA `config/custom_components/` directory and restart.

---

## Configuration

### Adding the integration

1. Go to **Settings → Devices & Services → Add Integration** and search for **IMAP Parcel**.
2. Select one or more Email HA accounts to monitor.
3. Set the backfill window (7–90 days, default 31).

### Options

Navigate to the integration and click **Configure** to:

| Option | Description |
|---|---|
| **Edit backfill window** | Change how many days back emails are scanned on startup |
| **Add custom sender rule** | Map an additional sender address to a courier name and confidence level |
| **Remove custom sender rule** | Delete a previously added rule |

---

## Built-in sender rules

The following senders are recognised automatically without any configuration:

| Sender | Courier | Statuses detected |
|---|---|---|
| `no-reply@royalmail.com` | Royal Mail | Ordered · Dispatched · Out for delivery · Delivered · Exception |
| `shipment-tracking@amazon.co.uk` | Amazon Logistics | Dispatched · Out for delivery · Delivered |
| `auto-confirm@amazon.co.uk` | Amazon | Ordered |
| `order-update@amazon.co.uk` | Amazon | Delivered |

---

## Sensors

Three sensors are created per configured integration entry.

### `sensor.imap_parcel_active_deliveries` (enabled by default)

State is the count of active (non-delivered) deliveries.

| Attribute | Description |
|---|---|
| `status_text` | Human-readable summary, e.g. "2 parcels today" or "in 3 days" |
| `number_of_active_deliveries` | Count of deliveries not yet delivered |
| `deliveries_arriving_today` | Count of deliveries with an ETA of today |
| `delivered_today` | Count of deliveries delivered today |
| `days_until_next_delivery` | Days until next ETA, or a text code if no ETA is known |
| `next_courier` | Courier for the soonest arriving delivery |
| `next_retailer` | Retailer for the soonest arriving delivery |
| `next_order_number` | Order number for the soonest arriving delivery |
| `next_tracking_number` | Tracking number for the soonest arriving delivery |
| `next_eta` | ETA date for the soonest arriving delivery |
| `next_status` | Status of the soonest arriving delivery |
| `active_deliveries` | Full list of active delivery objects |

`days_until_next_delivery` text codes:

| Value | Meaning |
|---|---|
| `No active deliveries.` | Nothing being tracked |
| `Active delivery, no ETA.` | Deliveries exist but none have a known ETA |

### `sensor.imap_parcel_recent_delivery` (disabled by default)

State is the status of the most recently updated delivery. Attributes mirror the full delivery record.

### `sensor.imap_parcel_raw_deliveries` (disabled by default)

State is the last-updated timestamp. The `deliveries` attribute contains the full raw delivery list — useful for debugging or building custom Lovelace cards.

---

## Contributing

Contributions welcome. Please open an issue or pull request on the [GitHub repository](https://github.com/PineappleEmperor/ha-imap-parcel).

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.

---

**Note:** This integration is unofficial and not affiliated with any courier or retailer.

<!-- Badges -->

[commits-badge]: https://img.shields.io/github/commits-since/PineappleEmperor/ha-imap-parcel/latest?style=flat-square
[hacs-valid-badge]: https://img.shields.io/github/actions/workflow/status/PineappleEmperor/ha-imap-parcel/hacs_validate.yml?style=flat-square&label=hacs%20valid
[hassfest-badge]: https://img.shields.io/github/actions/workflow/status/PineappleEmperor/ha-imap-parcel/hassfest_validate.yml?style=flat-square&label=hassfest
[python-badge]: https://img.shields.io/github/actions/workflow/status/PineappleEmperor/ha-imap-parcel/python_validate.yml?style=flat-square&label=python
[release-badge]: https://img.shields.io/github/v/release/PineappleEmperor/ha-imap-parcel?style=flat-square
[stars-badge]: https://img.shields.io/github/stars/PineappleEmperor/ha-imap-parcel?style=flat-square

<!-- References -->

[commits-url]: https://github.com/PineappleEmperor/ha-imap-parcel/commits/main/
[release-url]: https://github.com/PineappleEmperor/ha-imap-parcel/releases
