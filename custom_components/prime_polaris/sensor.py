"""
/* ============================================================
 * sensor.py — Prime Polaris Sensor Entities
 * ============================================================
 *
 * Provides the following sensors per grill device:
 *
 *   - probe_1_temperature: Meat probe 1 measured temp
 *   - probe_2_temperature: Meat probe 2 measured temp
 *   - running_status:      Human-readable grill state string
 *   - probe_1_target:      Meat probe 1 target (alert) temp
 *   - probe_2_target:      Meat probe 2 target (alert) temp
 *
 * Probe sensors show as unavailable when the probe is not
 * plugged in (probeP1Status = 0).
 * ============================================================
 */
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    DOMAIN,
    FIELD_DEVICE_SWITCH,
    FIELD_FURNACE_TEMP_MEASURED,
    FIELD_PROBE1_MEASURED,
    FIELD_PROBE1_SETTING,
    FIELD_PROBE1_STATUS,
    FIELD_PROBE2_MEASURED,
    FIELD_PROBE2_SETTING,
    FIELD_PROBE2_STATUS,
    FIELD_RUNNING_STATUS,
    FIELD_SMOKE_LEVEL,
    FIELD_SMOKE_MODE,
    FIELD_TEMP_UNIT,
    MANUFACTURER,
    RUNNING_STATUS_LABELS,
    RUNNING_STATUS_OFF,
    TEMP_UNIT_CELSIUS,
)
from .coordinator import PrimePolarisCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PrimePolarisensorDescription(SensorEntityDescription):
    """Extended description with probe status field for availability."""

    probe_status_field: str | None = None
    value_field: str = ""


# Sensor definitions — one entry per sensor entity
SENSOR_DESCRIPTIONS: tuple[PrimePolarisensorDescription, ...] = (
    PrimePolarisensorDescription(
        key="probe_1_temperature",
        name="Probe 1 Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_field=FIELD_PROBE1_MEASURED,
        probe_status_field=FIELD_PROBE1_STATUS,
    ),
    PrimePolarisensorDescription(
        key="probe_2_temperature",
        name="Probe 2 Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_field=FIELD_PROBE2_MEASURED,
        probe_status_field=FIELD_PROBE2_STATUS,
    ),
    PrimePolarisensorDescription(
        key="running_status",
        name="Running Status",
        value_field=FIELD_RUNNING_STATUS,
        probe_status_field=None,
    ),
    PrimePolarisensorDescription(
        key="last_alarm",
        name="Last Alarm",
        icon="mdi:alert-circle-outline",
        value_field="",  # synthetic — sourced from coordinator.last_alarm
        probe_status_field=None,
    ),
    PrimePolarisensorDescription(
        key="chamber_temperature",
        name="Chamber Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_field=FIELD_FURNACE_TEMP_MEASURED,
        probe_status_field=None,
    ),
    PrimePolarisensorDescription(
        key="active_mode",
        name="Active Mode",
        icon="mdi:state-machine",
        value_field="",  # synthetic — derived from deviceSwitch + smokeMode
        probe_status_field=None,
    ),
    PrimePolarisensorDescription(
        key="active_smoke_level",
        name="Active Smoke Level",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:smoke",
        value_field="",  # synthetic — smokeLevel only while smokeMode==1
        probe_status_field=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: PrimePolarisCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        PrimePolarisSensor(coordinator, entry, desc)
        for desc in SENSOR_DESCRIPTIONS
    ]
    entities.append(PrimePolarisProbeEtaSensor(coordinator, entry, probe_id=1))
    entities.append(PrimePolarisProbeEtaSensor(coordinator, entry, probe_id=2))
    async_add_entities(entities)


class PrimePolarisProbeEtaSensor(
    CoordinatorEntity[PrimePolarisCoordinator], SensorEntity
):
    """Live time-to-target estimate for a probe.

    State: estimated minutes until probe reaches its set target,
    based on a rolling Newton's-law fit. Unavailable when the
    probe isn't plugged in, the target isn't set, or the fit
    can't be computed yet (need ≥5 samples).

    Attributes:
      in_stall:     bool, True when probe is in the typical
                    stall window (140-175°F) with low rolling
                    stdev — collagen rendering, not a fit failure.
      stall_stdev:  rolling stdev (°F) over the stall window.
      k:            fitted Newton's-law coefficient (1/s); useful
                    for diagnostics or future per-protein priors.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "min"

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
        self._attr_unique_id = f"{self._device_id}_probe_{probe_id}_eta"
        self._attr_name = f"Probe {probe_id} ETA"
        self._setting_field = (
            FIELD_PROBE1_SETTING if probe_id == 1 else FIELD_PROBE2_SETTING
        )
        self._measured_field = (
            FIELD_PROBE1_MEASURED if probe_id == 1 else FIELD_PROBE2_MEASURED
        )

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
        if not super().available:
            return False
        # Need probe plugged in (measured > 0) AND a target set
        return (
            self._data.get(self._measured_field, 0) > 0
            and self._data.get(self._setting_field, 0) > 0
        )

    def _resolve_prior(self) -> tuple[float | None, str | None]:
        """Look up the Tier-2 prior for this cook (gated by sample
        thresholds). Returns (k_prior, source_label) or (None, None)."""
        tracker = self.coordinator.session_tracker
        protein = tracker.get_input("protein")
        weight_raw = tracker.get_input("weight_lb")
        try:
            weight_lb = float(weight_raw) if weight_raw else None
        except ValueError:
            weight_lb = None
        return self.coordinator.predictor.get_prior(protein, weight_lb)

    @property
    def native_value(self) -> float | None:
        target = self._data.get(self._setting_field, 0)
        if not target:
            return None
        predictor = self.coordinator.predictor.probes.get(self._probe_id)
        if predictor is None:
            return None
        prior, _ = self._resolve_prior()
        eta_seconds = predictor.eta_seconds(float(target), prior=prior)
        if eta_seconds is None:
            return None
        return round(eta_seconds / 60.0, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        predictor = self.coordinator.predictor.probes.get(self._probe_id)
        if predictor is None:
            return None
        in_stall, sigma = predictor.stall()
        prior, source = self._resolve_prior()
        k = predictor.fit_k(prior=prior)
        return {
            "in_stall": in_stall,
            "stall_stdev": round(sigma, 3) if sigma is not None else None,
            "k": round(k, 6) if k is not None else None,
            "samples": predictor.sample_count,
            "prior_source": source,
        }


class PrimePolarisSensor(
    CoordinatorEntity[PrimePolarisCoordinator], SensorEntity
):
    """A single sensor entity for a Prime Polaris grill."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PrimePolarisCoordinator,
        entry: ConfigEntry,
        description: PrimePolarisensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._device_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    # --- Device info -----------------------------------------

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
        }

    # --- State -----------------------------------------------

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return temp unit for temperature sensors, None for status."""
        desc = self.entity_description
        if desc.device_class == SensorDeviceClass.TEMPERATURE:
            if self._data.get(FIELD_TEMP_UNIT) == TEMP_UNIT_CELSIUS:
                return UnitOfTemperature.CELSIUS
            return UnitOfTemperature.FAHRENHEIT
        return None

    @property
    def available(self) -> bool:
        """Mark probe sensors unavailable when no reading is present.

        probeP_Status is 0 when no target is set even if the probe is
        plugged in. Use measured temp > 0 as the reliable indicator.

        active_smoke_level is unavailable whenever smoke mode is off,
        so long-term statistics show clean gaps between smoke runs.
        """
        if not super().available:
            return False

        desc = self.entity_description

        if desc.key == "active_smoke_level":
            return bool(self._data.get(FIELD_SMOKE_MODE))

        if desc.probe_status_field:
            # Map status field to corresponding measured field
            measured_field = desc.probe_status_field.replace("Status", "Measured")
            return self._data.get(measured_field, 0) > 0

        return True

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        desc = self.entity_description

        # Active mode: off / smoke / temperature, derived from flags
        if desc.key == "active_mode":
            if not self._data.get(FIELD_DEVICE_SWITCH):
                return "off"
            return "smoke" if self._data.get(FIELD_SMOKE_MODE) else "temperature"

        # Smoke level only when smoke mode is engaged (else unavailable)
        if desc.key == "active_smoke_level":
            if not self._data.get(FIELD_SMOKE_MODE):
                return None
            level = self._data.get(FIELD_SMOKE_LEVEL)
            return float(level) if level is not None else None

        # Synthetic sensor sourced from coordinator state, not realtime data
        if desc.key == "last_alarm":
            last = self.coordinator.last_alarm
            if not last:
                return None
            evt = (last.get("events") or [None])[0]
            if isinstance(evt, dict):
                # FCM pushes use {title, body, params}; polled alarmEvent
                # entries (when finally captured in the wild) may use
                # different keys. Try in order of likelihood.
                for key in ("title", "type", "name", "code", "event", "message"):
                    if key in evt:
                        return str(evt[key])[:255]
                return str(evt)[:255]
            return str(evt)[:255] if evt is not None else None

        raw = self._data.get(desc.value_field)

        if raw is None:
            return None

        # Running status: convert int to human-readable string
        if desc.key == "running_status":
            return RUNNING_STATUS_LABELS.get(raw, f"Unknown ({raw})")

        return float(raw) if raw else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose flat, readable attributes on the last_alarm sensor.

        UI-friendly version — flattens the coordinator's nested
        last_alarm dict so the device page shows clean key/value
        pairs instead of `events: [{...nested...}]`.
        """
        if self.entity_description.key == "last_alarm":
            last = self.coordinator.last_alarm
            if not last:
                return None
            evt = (last.get("events") or [None])[0]
            attrs: dict[str, Any] = {
                "captured_at": last.get("captured_at"),
                "source": last.get("source"),
            }
            if isinstance(evt, dict):
                attrs["title"] = evt.get("title")
                attrs["body"] = evt.get("body")
            elif evt is not None:
                attrs["raw"] = str(evt)
            return attrs
        return None
