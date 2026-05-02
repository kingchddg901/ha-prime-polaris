"""
/* ============================================================
 * text.py — Prime Polaris Text Entities
 * ============================================================
 *
 * User-editable text fields read by the cook-session tracker
 * when the session switch is flipped on:
 *
 *   - cook_notes:             free-form label for the cook
 *   - cook_ambient_override:  entity_id OR literal number for
 *                             ambient temp during this cook
 *   - cook_wind_override:     same shape, for wind speed
 *
 * All three are RestoreEntity so values persist across HA
 * restarts. The tracker clears them on session end.
 * ============================================================
 */
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DOMAIN, MANUFACTURER
from .coordinator import PrimePolarisCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PrimePolarisTextDescription(TextEntityDescription):
    """Description for a free-form text entity."""

    purpose: str = ""  # tracker key — "notes", "ambient_override", "wind_override"


TEXT_DESCRIPTIONS: tuple[PrimePolarisTextDescription, ...] = (
    PrimePolarisTextDescription(
        key="cook_notes",
        name="Cook Notes",
        icon="mdi:note-text-outline",
        native_max=255,
        purpose="notes",
    ),
    PrimePolarisTextDescription(
        key="cook_ambient_override",
        name="Cook Ambient Override",
        icon="mdi:thermometer",
        native_max=64,
        purpose="ambient_override",
    ),
    PrimePolarisTextDescription(
        key="cook_wind_override",
        name="Cook Wind Override",
        icon="mdi:weather-windy",
        native_max=64,
        purpose="wind_override",
    ),
    PrimePolarisTextDescription(
        key="cook_protein",
        name="Cook Protein",
        icon="mdi:food-steak",
        native_max=64,
        purpose="protein",
    ),
    PrimePolarisTextDescription(
        key="cook_weight_lb",
        name="Cook Weight (lb)",
        icon="mdi:scale",
        native_max=16,
        purpose="weight_lb",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up text entities from a config entry."""
    coordinator: PrimePolarisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PrimePolarisText(coordinator, entry, desc) for desc in TEXT_DESCRIPTIONS
    )


class PrimePolarisText(RestoreEntity, TextEntity):
    """Free-form user-editable text entity, restored across restarts.

    Registers itself with the coordinator's session_tracker on add
    so the tracker can read/clear it without guessing entity_ids.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PrimePolarisCoordinator,
        entry: ConfigEntry,
        description: PrimePolarisTextDescription,
    ) -> None:
        self._coordinator = coordinator
        self.entity_description = description
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_{description.key}"
        self._attr_native_value = ""

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_native_value = last_state.state
        # Register with tracker so it can read this entity by purpose.
        self._coordinator.session_tracker.register_text(
            self.entity_description.purpose, self
        )

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
