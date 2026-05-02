"""
/* ============================================================
 * switch.py — Prime Polaris Switch Entities
 * ============================================================
 *
 * Provides toggle switches for binary grill settings:
 *
 *   - smoke_mode:  Enable/disable extra smoke (smokeMode field)
 *   - winter_mode: Enable cold-weather compensation (winter field)
 *   - alarm:       Enable/disable temp alarm (alarmSwitch field)
 *
 * Confirmed API field names (verified 2026-05-02):
 *   alarm_switch            = 0|1
 *   winter_and_ref_temp     = [0|1, refTemp]
 *   smoke_mode_and_smoke_level = [mode, level]
 * ============================================================
 */
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    DOMAIN,
    FIELD_ALARM_SWITCH,
    FIELD_SMOKE_LEVEL,
    FIELD_SMOKE_MODE,
    FIELD_WINTER_MODE,
    MANUFACTURER,
    OPT_FCM_ENABLED,
)
from .coordinator import PrimePolarisCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PrimePolarsSwitchDescription(SwitchEntityDescription):
    """Extended description with state field name."""

    state_field: str = ""


SWITCH_DESCRIPTIONS: tuple[PrimePolarsSwitchDescription, ...] = (
    PrimePolarsSwitchDescription(
        key="smoke_mode",
        name="Smoke Mode",
        icon="mdi:smoke",
        state_field=FIELD_SMOKE_MODE,
    ),
    PrimePolarsSwitchDescription(
        key="winter_mode",
        name="Winter Mode",
        icon="mdi:snowflake",
        state_field=FIELD_WINTER_MODE,
    ),
    PrimePolarsSwitchDescription(
        key="alarm",
        name="Temperature Alarm",
        icon="mdi:bell-ring",
        state_field=FIELD_ALARM_SWITCH,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    coordinator: PrimePolarisCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [
        PrimePolarisSwitch(coordinator, entry, desc)
        for desc in SWITCH_DESCRIPTIONS
    ]
    entities.append(PrimePolarisCookSessionSwitch(coordinator, entry))
    entities.append(PrimePolarisFcmEnableSwitch(hass, entry))
    async_add_entities(entities)


class PrimePolarisFcmEnableSwitch(SwitchEntity):
    """Dashboard-visible toggle for the FCM push listener.

    Reads/writes entry.options[OPT_FCM_ENABLED] directly so it
    stays in sync with the options-flow form. Flipping triggers
    the existing entry update listener, which reloads the entry
    and starts/stops the FCM listener accordingly.
    """

    _attr_has_entity_name = True
    _attr_name = "Push Alerts"
    _attr_icon = "mdi:bell-ring-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_fcm_enabled"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
        }

    @property
    def is_on(self) -> bool:
        return bool(self._entry.options.get(OPT_FCM_ENABLED, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._update_option(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._update_option(False)

    async def _update_option(self, value: bool) -> None:
        new_options = {**self._entry.options, OPT_FCM_ENABLED: value}
        # Triggers _async_options_updated → entry reload → new entity
        # instance picks up the new value automatically.
        self._hass.config_entries.async_update_entry(
            self._entry, options=new_options
        )


class PrimePolarisCookSessionSwitch(
    CoordinatorEntity[PrimePolarisCoordinator], SwitchEntity
):
    """Manual on/off for cook-session recording.

    On-flip → snapshot current state + override text entities,
    begin accumulating samples in the tracker.

    Off-flip → finalize and append a row to sessions.csv.

    Auto-off: the coordinator's tracker also flips this off when
    the grill goes from Cooking to Off while the session is active.
    """

    _attr_has_entity_name = True
    _attr_name = "Cook Session"
    _attr_icon = "mdi:record-circle-outline"

    def __init__(
        self,
        coordinator: PrimePolarisCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_cook_session"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
        }

    @property
    def is_on(self) -> bool:
        tracker = getattr(self.coordinator, "session_tracker", None)
        return bool(tracker and tracker.active)

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Reload Tier-2 priors so this cook gets the latest CSV state
        self.coordinator.predictor.reload_priors()
        tracker = self.coordinator.session_tracker
        tracker.start(self.coordinator.data)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        tracker = self.coordinator.session_tracker
        await tracker.stop(ended_normally=True)
        self.async_write_ha_state()


class PrimePolarisSwitch(
    CoordinatorEntity[PrimePolarisCoordinator], SwitchEntity
):
    """A toggle switch for a binary grill setting."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PrimePolarisCoordinator,
        entry: ConfigEntry,
        description: PrimePolarsSwitchDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
        }

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}

    @property
    def is_on(self) -> bool:
        """Return True when the setting is active."""
        desc = self.entity_description
        return bool(self._data.get(desc.state_field, 0))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable this setting."""
        await self.coordinator.async_send_command(self._build_fields(1))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable this setting."""
        await self.coordinator.async_send_command(self._build_fields(0))

    def _build_fields(self, value: int) -> dict:
        """Build the flat command fields for this switch.

        Each switch type has a different API field structure:
          - smoke_mode: must send mode AND level together as array
          - winter_mode: must send toggle AND refTemp together as array
          - alarm: simple int field
        """
        desc = self.entity_description

        if desc.key == "smoke_mode":
            # Smoke mode and level must always be sent together
            level = int(self._data.get(FIELD_SMOKE_LEVEL, 0))
            return {"smoke_mode_and_smoke_level": [value, level]}

        if desc.key == "winter_mode":
            # Winter mode requires current refTemp alongside toggle
            ref_temp = int(self._data.get("refTemp", 0))
            return {"winter_and_ref_temp": [value, ref_temp]}

        if desc.key == "alarm":
            return {"alarm_switch": value}

        _LOGGER.warning("Unknown switch key: %s", desc.key)
        return {}
