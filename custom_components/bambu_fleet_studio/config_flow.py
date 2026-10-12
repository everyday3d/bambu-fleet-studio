"""Config flow for Bambu Lab Fleet Studio standalone integration."""

from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

DOMAIN = "bambu_fleet_studio"


class BambuFleetStudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bambu Lab Fleet Studio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Bambu Lab Fleet Studio (Standalone LAN Engine)",
                data={},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle automatic setup import."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Bambu Lab Fleet Studio (Standalone LAN Engine)",
            data=import_data or {},
        )
