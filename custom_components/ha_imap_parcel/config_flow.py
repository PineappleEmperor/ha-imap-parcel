"""Config flow for HA IMAP Parcel."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_BACKFILL_DAYS,
    CONF_EMAIL_HA_ENTRY_IDS,
    CONF_RULE_CONFIDENCE,
    CONF_RULE_COURIER,
    CONF_RULE_SENDER,
    CONF_SENDER_RULES,
    CONFIDENCE_HIGH,
    CONFIDENCE_OPTIONS,
    DEFAULT_BACKFILL_DAYS,
    DOMAIN,
    EMAIL_HA_CONF_EMAIL,
    EMAIL_HA_DOMAIN,
    MAX_BACKFILL_DAYS,
    MIN_BACKFILL_DAYS,
)

_ACTION_SAVE = "save"
_ACTION_ADD_RULE = "add_rule"
_ACTION_REMOVE_RULE = "remove_rule"
_ACTION_EDIT_BACKFILL = "edit_backfill"


def _email_ha_options(hass: HomeAssistant) -> dict[str, str]:
    """Return {entry_id: email_address} for all configured email_ha entries."""
    return {
        entry.entry_id: entry.data.get(EMAIL_HA_CONF_EMAIL, entry.title)
        for entry in hass.config_entries.async_entries(EMAIL_HA_DOMAIN)
    }


class ImapParcelTrackingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for IMAP Parcel."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ImapParcelTrackingOptionsFlow:
        """Return the options flow handler."""
        return ImapParcelTrackingOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select one or more email_ha entries and set backfill days."""
        email_ha_opts = _email_ha_options(self.hass)
        if not email_ha_opts:
            return self.async_abort(reason="no_email_ha_entries")

        errors: dict[str, str] = {}

        if user_input is not None:
            entry_ids: list[str] = user_input.get(CONF_EMAIL_HA_ENTRY_IDS, [])
            if not entry_ids:
                errors[CONF_EMAIL_HA_ENTRY_IDS] = "no_entries_selected"
            else:
                return self.async_create_entry(
                    title="IMAP Parcel",
                    data={
                        CONF_EMAIL_HA_ENTRY_IDS: entry_ids,
                        CONF_BACKFILL_DAYS: user_input.get(
                            CONF_BACKFILL_DAYS, DEFAULT_BACKFILL_DAYS
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL_HA_ENTRY_IDS): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=k, label=v)
                            for k, v in email_ha_opts.items()
                        ],
                        multiple=True,
                    )
                ),
                vol.Optional(
                    CONF_BACKFILL_DAYS, default=DEFAULT_BACKFILL_DAYS
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_BACKFILL_DAYS, max=MAX_BACKFILL_DAYS),
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class ImapParcelTrackingOptionsFlow(OptionsFlow):
    """Options flow: manage custom sender rules and backfill window."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._pending_rules: list[dict[str, str]] = list(
            config_entry.options.get(CONF_SENDER_RULES, [])
        )
        self._pending_backfill: int = config_entry.options.get(
            CONF_BACKFILL_DAYS,
            config_entry.data.get(CONF_BACKFILL_DAYS, DEFAULT_BACKFILL_DAYS),
        )

    def _save(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title="",
            data={
                CONF_SENDER_RULES: self._pending_rules,
                CONF_BACKFILL_DAYS: self._pending_backfill,
            },
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show current config and action menu."""
        if user_input is not None:
            action = user_input.get("action", _ACTION_SAVE)
            if action == _ACTION_ADD_RULE:
                return await self.async_step_add_rule()
            if action == _ACTION_REMOVE_RULE and self._pending_rules:
                return await self.async_step_remove_rule()
            if action == _ACTION_EDIT_BACKFILL:
                return await self.async_step_edit_backfill()
            return self._save()

        rules_desc = (
            "\n".join(
                f"• {r[CONF_RULE_SENDER]} → {r[CONF_RULE_COURIER]} ({r[CONF_RULE_CONFIDENCE]})"
                for r in self._pending_rules
            )
            or "None (using built-in rules only)"
        )

        actions: dict[str, str] = {
            _ACTION_SAVE: "Save and close",
            _ACTION_EDIT_BACKFILL: f"Edit backfill window (currently {self._pending_backfill} days)",
            _ACTION_ADD_RULE: "Add custom sender rule",
        }
        if self._pending_rules:
            actions[_ACTION_REMOVE_RULE] = "Remove a custom sender rule"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required("action", default=_ACTION_SAVE): vol.In(actions)}
            ),
            description_placeholders={
                "custom_rules": rules_desc,
                "backfill_days": str(self._pending_backfill),
            },
        )

    async def async_step_add_rule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a custom sender address → courier mapping."""
        errors: dict[str, str] = {}

        if user_input is not None:
            sender = user_input[CONF_RULE_SENDER].strip().lower()
            if not sender:
                errors[CONF_RULE_SENDER] = "empty_sender"
            elif "@" not in sender:
                errors[CONF_RULE_SENDER] = "invalid_email"
            else:
                # Replace existing rule for same sender
                self._pending_rules = [
                    r for r in self._pending_rules if r.get(CONF_RULE_SENDER) != sender
                ]
                self._pending_rules.append(
                    {
                        CONF_RULE_SENDER: sender,
                        CONF_RULE_COURIER: user_input[CONF_RULE_COURIER].strip(),
                        CONF_RULE_CONFIDENCE: user_input[CONF_RULE_CONFIDENCE],
                    }
                )
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_rule",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_RULE_SENDER): str,
                    vol.Required(CONF_RULE_COURIER): str,
                    vol.Required(CONF_RULE_CONFIDENCE, default=CONFIDENCE_HIGH): vol.In(
                        CONFIDENCE_OPTIONS
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_rule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a custom sender rule."""
        if not self._pending_rules:
            return await self.async_step_init()

        if user_input is not None:
            idx = int(user_input["rule_index"])
            self._pending_rules.pop(idx)
            return await self.async_step_init()

        rule_options = {
            str(i): f"{r[CONF_RULE_SENDER]} → {r[CONF_RULE_COURIER]}"
            for i, r in enumerate(self._pending_rules)
        }
        return self.async_show_form(
            step_id="remove_rule",
            data_schema=vol.Schema(
                {vol.Required("rule_index"): vol.In(rule_options)}
            ),
        )

    async def async_step_edit_backfill(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the backfill window."""
        if user_input is not None:
            self._pending_backfill = int(user_input[CONF_BACKFILL_DAYS])
            return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_backfill",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BACKFILL_DAYS, default=self._pending_backfill): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_BACKFILL_DAYS, max=MAX_BACKFILL_DAYS),
                    )
                }
            ),
        )
