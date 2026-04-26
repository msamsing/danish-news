"""Sensor platform for Danish News."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DanishNewsDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Danish News sensor."""

    coordinator: DanishNewsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DanishNewsSensor(coordinator, entry)])


class DanishNewsSensor(CoordinatorEntity[DanishNewsDataUpdateCoordinator], SensorEntity):
    """Sensor exposing today's Danish news headlines."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:newspaper-variant-outline"
    _attr_name = "Nyheder"

    def __init__(
        self,
        coordinator: DanishNewsDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_headlines"

    @property
    def native_value(self) -> int:
        """Return total headline count."""

        return len(self.coordinator.data.get("articles", [])) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return article data for the Lovelace card."""

        data = self.coordinator.data or {}
        providers = data.get("providers", {})
        return {
            "integration": DOMAIN,
            "entry_id": self._entry.entry_id,
            "updated_at": data.get("updated_at", ""),
            "articles": data.get("articles", []),
            "providers": providers,
            "provider_counts": {
                provider: len(articles) for provider, articles in providers.items()
            },
            "provider_info": data.get("provider_info", {}),
            "errors": data.get("errors", {}),
        }
