"""The Danish News integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CARD_FILENAME, CARD_URL_PATH, DOMAIN
from .coordinator import DanishNewsDataUpdateCoordinator
from .websocket import async_register_websocket

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Danish News from a config entry."""

    coordinator = DanishNewsDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await async_register_card_path(hass)
    async_register_websocket(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_register_card_path(hass: HomeAssistant) -> None:
    """Expose the Lovelace card bundled with the integration."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("card_path_registered"):
        return

    card_path = Path(__file__).parent / "www" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(card_path), True)]
    )
    domain_data["card_path_registered"] = True
