"""Config flow for Danish News."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_MAX_ARTICLES,
    CONF_PROVIDERS,
    CONF_REFRESH_MINUTES,
    DEFAULT_MAX_ARTICLES,
    DEFAULT_PROVIDERS,
    DEFAULT_REFRESH_MINUTES,
    DOMAIN,
    PROVIDER_NAMES,
)


class DanishNewsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Danish News config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create the integration."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_PROVIDERS):
                errors["base"] = "no_providers"
            else:
                return self.async_create_entry(title="Danske nyheder", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=options_schema(user_input),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""

        return DanishNewsOptionsFlow(config_entry)


class DanishNewsOptionsFlow(config_entries.OptionsFlow):
    """Handle Danish News options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""

        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""

        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_PROVIDERS):
                errors["base"] = "no_providers"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema(
                user_input or self._config_entry.options or self._config_entry.data
            ),
            errors=errors,
        )


def options_schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Return the shared config/options schema."""

    values = values or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_PROVIDERS,
                default=values.get(CONF_PROVIDERS, DEFAULT_PROVIDERS),
            ): cv.multi_select(PROVIDER_NAMES),
            vol.Optional(
                CONF_MAX_ARTICLES,
                default=values.get(CONF_MAX_ARTICLES, DEFAULT_MAX_ARTICLES),
            ): vol.All(vol.Coerce(int), vol.Range(min=3, max=20)),
            vol.Optional(
                CONF_REFRESH_MINUTES,
                default=values.get(CONF_REFRESH_MINUTES, DEFAULT_REFRESH_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
        }
    )
