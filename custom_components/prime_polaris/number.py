"""
/* ============================================================
 * number.py — Prime Polaris Number Entities
 * ============================================================
 *
 * Provides numeric slider controls for grill settings:
 *
 *   - smoke_level:    Smoke intensity level (0–10)
 *   - probe_1_target: Meat probe 1 alert temperature
 *   - probe_2_target: Meat probe 2 alert temperature
 *
 * Probe target numbers are only available when the probe is
 * physically plugged in (probeP1/2Status = 1).
 *
 * Confirmed API field (verified 2026-05-02):
 *   setProbeTemp = [{"probeId": 1|2, "temp_and_status": [temp, 1]}]
 * ============================================================
 */
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CMD_SMOKE_SET,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    DEFAULT_FCM_DEDUP_SECONDS,
    DOMAIN,
    FIELD_FURNACE_TEMP_SETTING,
    FIELD_PROBE1_MEASURED,
    FIELD_PROBE1_STATUS,
    FIELD_PROBE1_SETTING,
    FIELD_PROBE2_MEASURED,
    FIELD_PROBE2_STATUS,
    FIELD_PROBE2_SETTING,
    FIELD_SMOKE_LEVEL,
    FIELD_SMOKE_MODE,
    FIELD_TEMP_UNIT,
    MANUFACTURER,
    OPT_FCM_DEDUP_SECONDS,
    SMOKE_LEVEL_MAX,
    SMOKE_LEVEL_MIN,
    SMOKE_LEVEL_STEP,
    TEMP_MAX,
    TEMP_MIN,
    TEMP_STEP,
    TEMP_UNIT_CELSIUS,
)
from .coordinator import PrimePolarisCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    coordinator: PrimePolarisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        PrimePolarisTemperatureNumber(coordinator, entry),
        PrimePolarisSmokeLevelNumber(coordinator, entry),
        PrimePolarisProbeTargetNumber(coordinator, entry, probe_id=1),
        PrimePolarisProbeTargetNumber(coordinator, entry, probe_id=2),
        PrimePolarisFcmDedupNumber(hass, entry),
    ])


class PrimePolarisFcmDedupNumber(NumberEntity):
    """Dashboard-visible slider for the FCM dedupe window (seconds).

    Reads/writes entry.options[OPT_FCM_DEDUP_SECONDS] directly so
    it stays in sync with the options-flow form.
    """

    _attr_has_entity_name = True
    _attr_name = "Push Alert Dedupe"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 10
    _attr_native_max_value = 3600
    _attr_native_step = 10
    _attr_native_unit_of_measurement = "s"
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_fcm_dedup_seconds"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
        }

    @property
    def native_value(self) -> float:
        return float(
            self._entry.options.get(
                OPT_FCM_DEDUP_SECONDS, DEFAULT_FCM_DEDUP_SECONDS
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        new_options = {**self._entry.options, OPT_FCM_DEDUP_SECONDS: int(value)}
        self._hass.config_entries.async_update_entry(
            self._entry, options=new_options
        )


class PrimePolarisTemperatureNumber(
    CoordinatorEntity[PrimePolarisCoordinator], NumberEntity
):
    """Type-in temperature setpoint (1°F precision).

    Sibling to the climate entity's slider — exposes the same
    furnace_temp_setting via NumberMode.BOX so users can type
    a precise value rather than dragging the climate dial.
    """

    _attr_has_entity_name = True
    _attr_name = "Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = TEMP_MIN
    _attr_native_max_value = TEMP_MAX
    _attr_native_step = TEMP_STEP

    def __init__(
        self,
        coordinator: PrimePolarisCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_temperature"

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
    def native_unit_of_measurement(self) -> str:
        if self._data.get(FIELD_TEMP_UNIT) == TEMP_UNIT_CELSIUS:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def native_value(self) -> float | None:
        val = self._data.get(FIELD_FURNACE_TEMP_SETTING)
        return float(val) if val else None

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.debug("Setting grill temperature to %s", value)
        await self.coordinator.async_send_command(
            {"furnace_temp_setting": int(value)}
        )


class PrimePolarisSmokeLevelNumber(
    CoordinatorEntity[PrimePolarisCoordinator], NumberEntity
):
    """Smoke intensity level slider (0–10).

    Smoke mode and level must always be sent together — we carry
    the current smokeMode value so adjusting level doesn't toggle mode.
    """

    _attr_has_entity_name = True
    _attr_name = "Smoke Level"
    _attr_icon = "mdi:smoke"
    _attr_native_min_value = SMOKE_LEVEL_MIN
    _attr_native_max_value = SMOKE_LEVEL_MAX
    _attr_native_step = SMOKE_LEVEL_STEP
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: PrimePolarisCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_smoke_level"

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
    def native_value(self) -> float:
        return float(self._data.get(FIELD_SMOKE_LEVEL, 0))

    async def async_set_native_value(self, value: float) -> None:
        """Set smoke level, preserving current smoke mode."""
        current_mode = int(self._data.get(FIELD_SMOKE_MODE, 0))
        _LOGGER.debug("Setting smoke level to %s (mode=%s)", value, current_mode)
        await self.coordinator.async_send_command(
            {"smoke_mode_and_smoke_level": [current_mode, int(value)]}
        )


class PrimePolarisProbeTargetNumber(
    CoordinatorEntity[PrimePolarisCoordinator], NumberEntity
):
    """Meat probe target alert temperature.

    When the grill temp reaches this value the grill beeps.
    Only available when the probe is physically plugged in.
    """

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: PrimePolarisCoordinator,
        entry: ConfigEntry,
        probe_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._probe_id = probe_id
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_probe_{probe_id}_target"
        self._attr_name = f"Probe {probe_id} Target"
        self._attr_icon = "mdi:thermometer-probe"
        self._status_field = FIELD_PROBE1_STATUS if probe_id == 1 else FIELD_PROBE2_STATUS
        self._setting_field = FIELD_PROBE1_SETTING if probe_id == 1 else FIELD_PROBE2_SETTING
        self._measured_field = FIELD_PROBE1_MEASURED if probe_id == 1 else FIELD_PROBE2_MEASURED

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
    def available(self) -> bool:
        """Available when probe is reporting a temperature reading.

        probeP_Status is 0 when no target is set, even if the probe
        is physically plugged in. Use measured temp > 0 instead as
        the reliable plug-in indicator.
        """
        if not super().available:
            return False
        return self._data.get(self._measured_field, 0) > 0

    @property
    def native_unit_of_measurement(self) -> str:
        if self._data.get(FIELD_TEMP_UNIT) == TEMP_UNIT_CELSIUS:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def native_min_value(self) -> float:
        """Min of 0 allows displaying unset state cleanly."""
        return 0.0

    @property
    def native_max_value(self) -> float:
        return float(TEMP_MAX)

    @property
    def native_value(self) -> float:
        """Return probe target temp, or 0 if not yet set."""
        return float(self._data.get(self._setting_field, 0))

    async def async_set_native_value(self, value: float) -> None:
        """Set the probe alert temperature."""
        _LOGGER.debug("Setting probe %s target to %s", self._probe_id, value)
        await self.coordinator.async_send_command({
            "setProbeTemp": [
                {
                    "probeId": self._probe_id,
                    "temp_and_status": [int(value), 1],
                }
            ]
        })
