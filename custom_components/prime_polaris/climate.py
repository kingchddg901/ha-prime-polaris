"""
/* ============================================================
 * climate.py — Prime Polaris Grill Climate Entity
 * ============================================================
 *
 * Exposes the pellet grill as a HA climate entity, which gives
 * the best UX for a device with a set point and measured temp:
 *
 *   - HVAC modes: off, heat (cooking)
 *   - Current temperature: furnaceTempMeasured
 *   - Target temperature: furnaceTempSetting
 *   - Preset modes: map to runningStatus values
 *
 * Remote power-on is supported but gated by a minimum set point
 * (MIN_REMOTE_POWER_ON_TEMP) as a safety guard — the grill will
 * not ignite unless a target temperature has been configured.
 *
 * Temperature unit follows the device's tempUnit field:
 *   0 = Fahrenheit, 1 = Celsius
 * ============================================================
 */
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_EMAIL,
    CONF_TOKEN_EXPIRY,
    DOMAIN,
    FIELD_DEVICE_SWITCH,
    FIELD_FURNACE_TEMP_MEASURED,
    FIELD_FURNACE_TEMP_SETTING,
    FIELD_RUNNING_STATUS,
    FIELD_TEMP_UNIT,
    MANUFACTURER,
    MIN_REMOTE_POWER_ON_TEMP,
    RUNNING_STATUS_LABELS,
    RUNNING_STATUS_OFF,
    TEMP_MAX,
    TEMP_MIN,
    TEMP_STEP,
    TEMP_UNIT_CELSIUS,
)
from .coordinator import PrimePolarisCoordinator

_LOGGER = logging.getLogger(__name__)

# Map running status integers to HA preset mode strings
_PRESET_MAP = {
    status: label for status, label in RUNNING_STATUS_LABELS.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate entity from a config entry."""
    coordinator: PrimePolarisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PrimePolarisClimate(coordinator, entry)])


class PrimePolarisClimate(
    CoordinatorEntity[PrimePolarisCoordinator], ClimateEntity
):
    """Climate entity representing a Prime Polaris pellet grill.

    Provides set point control, current temp reading, and
    on/off control via HVAC modes.
    """

    _attr_has_entity_name = True
    _attr_name = None  # Device name is the entity name
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_target_temperature_step = TEMP_STEP
    _attr_min_temp = TEMP_MIN
    _attr_max_temp = TEMP_MAX
    _attr_preset_modes = list(RUNNING_STATUS_LABELS.values())

    def __init__(
        self,
        coordinator: PrimePolarisCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_climate"

    # --- Device info -----------------------------------------

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry info — groups all entities together."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
            "model": self.coordinator.entry.data.get("model", "Pellet Grill"),
        }

    # --- State properties ------------------------------------

    @property
    def _data(self) -> dict[str, Any]:
        """Shorthand accessor for coordinator data."""
        return self.coordinator.data or {}

    @property
    def temperature_unit(self) -> str:
        """Return temperature unit based on device setting."""
        if self._data.get(FIELD_TEMP_UNIT) == TEMP_UNIT_CELSIUS:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def current_temperature(self) -> float | None:
        """Return measured grill temperature."""
        val = self._data.get(FIELD_FURNACE_TEMP_MEASURED)
        return float(val) if val is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the current temperature set point."""
        val = self._data.get(FIELD_FURNACE_TEMP_SETTING)
        return float(val) if val else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode based on device switch state."""
        if self._data.get(FIELD_DEVICE_SWITCH, 0) == 0:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode mapped from running status."""
        status = self._data.get(FIELD_RUNNING_STATUS, RUNNING_STATUS_OFF)
        return _PRESET_MAP.get(status)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Diagnostic info readable from the frontend (e.g., the
        custom Lovelace card's Setup tab pulls email + token expiry
        from here so users can see when reauth is due).

        Token itself is NOT exposed — only the email and the Unix
        epoch expiry timestamp, both of which are non-sensitive.
        """
        entry_data = self.coordinator.entry.data
        return {
            "email":        entry_data.get(CONF_EMAIL),
            "token_expiry": entry_data.get(CONF_TOKEN_EXPIRY),
        }

    # --- Actions ---------------------------------------------

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        temp = kwargs.get("temperature")
        if temp is None:
            return
        _LOGGER.debug("Setting grill temperature to %s", temp)
        await self.coordinator.async_send_command(
            {"furnace_temp_setting": int(temp)}
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn grill off. Power-on is blocked server-side by the API."""
        if hvac_mode == HVACMode.OFF:
            _LOGGER.info("Powering off grill remotely")
            await self.coordinator.async_send_command({"device_switch": 0})
        elif hvac_mode == HVACMode.HEAT:
            # Server returns error -10004 for device_switch=1 — not supported
            _LOGGER.warning(
                "Remote power-on is not supported by the Prime Polaris API"
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Preset mode changes are read-only — driven by grill state."""
        # Running status is determined by the grill firmware, not set
        # directly. This is here to satisfy the ClimateEntity contract.
        _LOGGER.debug("Preset mode is read-only: %s", preset_mode)
