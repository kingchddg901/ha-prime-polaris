"""
/* ============================================================
 * session_logger.py — Cook Session Tracker + CSV Writer
 * ============================================================
 *
 * Tracks a single cook session from manual start (switch on)
 * through manual stop (switch off) or auto-stop (grill goes
 * Off while switch is still on). Accumulates chamber temp
 * samples plus optional ambient/wind samples, computes basic
 * stats at the end, appends one row per cook to a flat CSV
 * at <config>/prime_polaris/sessions.csv.
 *
 * 90%+ of cooks are set-and-forget at one temperature, so the
 * schema is intentionally flat — no nested JSON, no event-level
 * detail. HA's recorder already has per-sample history if any
 * forensic question ever needs answering.
 *
 * Override resolution:
 *   - If a text override is a plain number string, treat as
 *     a fixed literal value for the whole cook.
 *   - Otherwise treat it as an entity_id (domain.id) and
 *     sample its state on each poll for averaging.
 *   - Empty override → that column is left blank in the CSV.
 * ============================================================
 */
"""

from __future__ import annotations

import csv
import logging
import re
import statistics
import uuid
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    FIELD_DEVICE_SWITCH,
    FIELD_FURNACE_TEMP_MEASURED,
    FIELD_FURNACE_TEMP_SETTING,
    FIELD_PROBE1_MEASURED,
    FIELD_PROBE1_SETTING,
    FIELD_PROBE2_MEASURED,
    FIELD_PROBE2_SETTING,
    FIELD_RUNNING_STATUS,
    FIELD_SMOKE_LEVEL,
    FIELD_SMOKE_MODE,
    RUNNING_STATUS_OFF,
)

_LOGGER = logging.getLogger(__name__)

CSV_COLUMNS = [
    "cook_id",
    "started_at",
    "ended_at",
    "duration_min",
    "protein",
    "weight_lb",
    "ambient_start",
    "ambient_avg",
    "wind_speed_avg",
    "mode",
    "smoke_level",
    "setpoint",
    "chamber_avg",
    "chamber_stdev",
    "chamber_peak",
    "chamber_min",
    "probe1_target",
    "probe1_initial",
    "probe1_final",
    "probe2_target",
    "probe2_initial",
    "probe2_final",
    "disturbance_count",
    "ended_normally",
    "notes",
]

# Disturbance / lid-open inference tunables.
# Calibrated for a 30s poll cadence. Values approximate — they will
# false-positive during smoke mode's natural sawtooth (we disable
# detection in smoke mode for that reason).
DISTURBANCE_DROP_RATE_PER_SAMPLE = 3.0    # °F drop in one 30s tick → suspect
DISTURBANCE_MIN_TOTAL_DROP       = 15.0   # °F total drop to confirm
DISTURBANCE_RECOVERY_NEAR        = 5.0    # within °F of original = recovered

EVENT_DISTURBANCE = "prime_polaris_disturbance"

# Matches "domain.entity_id" (e.g. "weather.home", "sensor.outdoor_temp")
_ENTITY_ID_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


class CookSessionTracker:
    """Tracks one cook session at a time for a single grill device.

    Thread model: HA event loop only. All file I/O is offloaded
    to the executor; no other locking required.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        csv_path: Path,
    ) -> None:
        self._hass = hass
        self._csv_path = csv_path

        # Text entities register themselves here by purpose key —
        # avoids guessing entity_ids that break on device rename.
        # Keys: "notes", "ambient_override", "wind_override".
        self._texts: dict[str, Any] = {}

        self._active = False
        self._session: dict[str, Any] | None = None
        self._prev_running_status: int | None = None

    def register_text(self, purpose: str, entity: Any) -> None:
        """Called by each text entity in async_added_to_hass."""
        self._texts[purpose] = entity

    def get_input(self, purpose: str) -> str:
        """Public read-only access to a text-input value (e.g., from
        the ETA sensor). Returns '' if entity isn't registered yet."""
        return self._read_text(purpose)

    # --- Public API ------------------------------------------

    @property
    def active(self) -> bool:
        return self._active

    def start(self, current_data: dict[str, Any] | None) -> None:
        """Begin a new cook session — called when the switch flips on."""
        if self._active:
            _LOGGER.debug("Cook session already active; ignoring start")
            return

        data = current_data or {}
        notes = self._read_text("notes")
        ambient_override = self._read_text("ambient_override")
        wind_override = self._read_text("wind_override")
        protein = self._read_text("protein").lower().strip()
        weight_raw = self._read_text("weight_lb")
        try:
            weight_lb: float | None = float(weight_raw) if weight_raw else None
        except ValueError:
            weight_lb = None

        smoke_mode = bool(data.get(FIELD_SMOKE_MODE))
        mode = "smoke" if smoke_mode else "temperature"

        ambient_start = self._read_override_value(ambient_override)

        self._session = {
            "cook_id": uuid.uuid4().hex[:12],
            "started_at": dt_util.utcnow().isoformat(),
            "ended_at": None,
            "ambient_override": ambient_override,
            "wind_override": wind_override,
            "ambient_start": ambient_start,
            "ambient_samples": [],
            "wind_samples": [],
            "mode": mode,
            "smoke_level": (
                int(data.get(FIELD_SMOKE_LEVEL, 0)) if smoke_mode else None
            ),
            "setpoint": int(data.get(FIELD_FURNACE_TEMP_SETTING, 0)) or None,
            "chamber_samples": [],
            "probe1_target": int(data.get(FIELD_PROBE1_SETTING, 0)) or None,
            "probe2_target": int(data.get(FIELD_PROBE2_SETTING, 0)) or None,
            "probe1_initial": (
                float(data.get(FIELD_PROBE1_MEASURED, 0))
                if data.get(FIELD_PROBE1_MEASURED) else None
            ),
            "probe2_initial": (
                float(data.get(FIELD_PROBE2_MEASURED, 0))
                if data.get(FIELD_PROBE2_MEASURED) else None
            ),
            "probe1_final": None,
            "probe2_final": None,
            "disturbance_count": 0,
            "notes": notes,
            "protein": protein,
            "weight_lb": weight_lb,
            "ended_normally": True,
            # Disturbance detection state machine — see _check_disturbance
            "_dist_state": "NORMAL",
            "_dist_drop_start_temp": None,
            "_dist_drop_start_time": None,
            "_dist_lowest_temp": None,
        }
        self._active = True
        _LOGGER.info(
            "Cook session started (cook_id=%s, mode=%s, setpoint=%s)",
            self._session["cook_id"], mode, self._session["setpoint"],
        )

    async def stop(self, ended_normally: bool = True) -> None:
        """Finalize the active session and append a row to CSV."""
        if not self._active or self._session is None:
            return

        sess = self._session
        sess["ended_at"] = dt_util.utcnow().isoformat()
        sess["ended_normally"] = ended_normally

        # Final probe readings (last sample we have, if any)
        # The observe() method tracks last_data implicitly via samples,
        # but probes are scalar at end-of-cook — captured below from
        # the most recent observation we stored.
        if "_last_probe1" in sess:
            sess["probe1_final"] = sess.pop("_last_probe1")
        if "_last_probe2" in sess:
            sess["probe2_final"] = sess.pop("_last_probe2")

        row = self._build_row(sess)

        # File I/O off the event loop
        await self._hass.async_add_executor_job(self._write_row, row)

        # Clear text entities so next cook starts fresh
        await self._clear_text_entities()

        _LOGGER.info(
            "Cook session ended (cook_id=%s, duration=%s min, ended_normally=%s)",
            sess["cook_id"], row["duration_min"], ended_normally,
        )
        self._active = False
        self._session = None

    def observe(self, data: dict[str, Any]) -> None:
        """Called from coordinator after each successful poll.

        Detects auto-stop (runningStatus 2 → 3 while session active)
        and accumulates samples while the session is active.
        """
        running_status = data.get(FIELD_RUNNING_STATUS)

        # Auto-stop: grill went Off while we were tracking
        if (
            self._active
            and self._prev_running_status is not None
            and self._prev_running_status != RUNNING_STATUS_OFF
            and running_status == RUNNING_STATUS_OFF
        ):
            _LOGGER.info("Cook session auto-stopping: grill powered off")
            # Schedule the async stop on the event loop
            self._hass.async_create_task(self.stop(ended_normally=True))

        if self._active and self._session is not None:
            chamber = data.get(FIELD_FURNACE_TEMP_MEASURED)
            if chamber is not None:
                try:
                    chamber_val = float(chamber)
                    self._session["chamber_samples"].append(chamber_val)
                    self._check_disturbance(chamber_val)
                except (TypeError, ValueError):
                    pass

            # Track latest probe readings for end-of-cook capture
            p1 = data.get(FIELD_PROBE1_MEASURED)
            p2 = data.get(FIELD_PROBE2_MEASURED)
            if p1 is not None:
                self._session["_last_probe1"] = float(p1)
            if p2 is not None:
                self._session["_last_probe2"] = float(p2)

            # Sample ambient/wind if overrides reference an entity
            ambient_val = self._read_override_value(self._session["ambient_override"])
            if ambient_val is not None:
                self._session["ambient_samples"].append(ambient_val)
            wind_val = self._read_override_value(self._session["wind_override"])
            if wind_val is not None:
                self._session["wind_samples"].append(wind_val)

        self._prev_running_status = running_status

    # --- Disturbance detection -------------------------------

    def _check_disturbance(self, chamber: float) -> None:
        """Run the lid-open / disturbance state machine for one sample.

        Skipped during smoke mode — the natural P-cycle sawtooth would
        false-positive constantly. Detected events fire HA event
        prime_polaris_disturbance and bump session disturbance_count.

        States:
          NORMAL   → DROPPING when one-sample drop ≥ DISTURBANCE_DROP_RATE_PER_SAMPLE
          DROPPING → CONFIRMED when total drop ≥ DISTURBANCE_MIN_TOTAL_DROP and rising
          DROPPING → NORMAL    if drop reverses without reaching min total (noise)
          CONFIRMED → NORMAL   when chamber recovers within DISTURBANCE_RECOVERY_NEAR
                                of the drop-start temp (count + fire event)
        """
        sess = self._session
        if sess is None or sess.get("mode") == "smoke":
            return

        samples = sess["chamber_samples"]
        if len(samples) < 2:
            return  # need at least one prior sample for delta

        prev = samples[-2]
        delta = chamber - prev
        state = sess["_dist_state"]

        if state == "NORMAL":
            if delta <= -DISTURBANCE_DROP_RATE_PER_SAMPLE:
                sess["_dist_state"] = "DROPPING"
                sess["_dist_drop_start_temp"] = prev
                sess["_dist_drop_start_time"] = dt_util.utcnow()
                sess["_dist_lowest_temp"] = chamber

        elif state == "DROPPING":
            lowest = sess["_dist_lowest_temp"]
            start_temp = sess["_dist_drop_start_temp"]
            if delta < 0:
                # Still falling — track lowest
                if lowest is None or chamber < lowest:
                    sess["_dist_lowest_temp"] = chamber
            else:
                # Stopped falling. Did we drop enough to confirm?
                total_drop = (start_temp or chamber) - (lowest or chamber)
                if total_drop >= DISTURBANCE_MIN_TOTAL_DROP:
                    sess["_dist_state"] = "CONFIRMED"
                else:
                    # Just noise — reset
                    sess["_dist_state"] = "NORMAL"
                    sess["_dist_drop_start_temp"] = None
                    sess["_dist_drop_start_time"] = None
                    sess["_dist_lowest_temp"] = None

        elif state == "CONFIRMED":
            start_temp = sess["_dist_drop_start_temp"]
            if start_temp is not None and chamber >= start_temp - DISTURBANCE_RECOVERY_NEAR:
                # Recovered. Finalize the event.
                start_time = sess["_dist_drop_start_time"]
                lowest = sess["_dist_lowest_temp"]
                recovery_seconds = (
                    (dt_util.utcnow() - start_time).total_seconds()
                    if start_time else None
                )
                peak_drop = (
                    start_temp - lowest if lowest is not None else None
                )
                sess["disturbance_count"] += 1

                self._hass.bus.async_fire(
                    EVENT_DISTURBANCE,
                    {
                        "cook_id": sess["cook_id"],
                        "detected_at": (
                            start_time.isoformat() if start_time else None
                        ),
                        "peak_drop": round(peak_drop, 1) if peak_drop else None,
                        "chamber_at_start": round(start_temp, 1),
                        "chamber_lowest": round(lowest, 1) if lowest else None,
                        "recovery_seconds": (
                            round(recovery_seconds, 1) if recovery_seconds else None
                        ),
                    },
                )
                _LOGGER.info(
                    "Cook disturbance detected: drop=%.1f°F, recovery=%.0fs",
                    peak_drop or 0, recovery_seconds or 0,
                )

                sess["_dist_state"] = "NORMAL"
                sess["_dist_drop_start_temp"] = None
                sess["_dist_drop_start_time"] = None
                sess["_dist_lowest_temp"] = None

    # --- Helpers ---------------------------------------------

    def _read_text(self, purpose: str) -> str:
        """Read the registered text entity's current value by purpose."""
        entity = self._texts.get(purpose)
        if entity is None:
            return ""
        val = getattr(entity, "native_value", None)
        return val if isinstance(val, str) else ""

    def _read_override_value(self, override: str) -> float | None:
        """Resolve an override string to a numeric value.

        Returns None if the override is empty, points at a missing
        entity, or its value isn't parseable as a number.

        Special-cases `weather.*` entities — HA weather entities expose
        temperature / wind_speed in their attributes, not in `state`
        (state is a forecast string like "cloudy" or "sunny").
        """
        if not override:
            return None

        if _ENTITY_ID_RE.match(override):
            state = self._hass.states.get(override)
            if state is None:
                return None
            # Weather entities → pull from attributes
            if override.startswith("weather."):
                attrs = state.attributes or {}
                # Wind override resolves wind_speed; everything else
                # gets temperature. Lossy but matches normal use.
                value = (
                    attrs.get("wind_speed")
                    if "wind" in override.lower() or override == self._wind_override_eid()
                    else attrs.get("temperature")
                )
                if value is not None:
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return None
            raw = state.state
        else:
            raw = override

        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _wind_override_eid(self) -> str:
        """Helper used in weather-entity dispatch above."""
        ent = self._texts.get("wind_override")
        return ent.entity_id if ent and hasattr(ent, "entity_id") else ""

    # Per-cook fields are wiped at session end. Setup-style fields
    # (ambient/wind sensor pointers) are treated as user defaults and
    # left alone — typing your outdoor sensor entity_id once should
    # apply to every future cook.
    _PER_COOK_PURPOSES = {"notes", "protein", "weight_lb"}

    async def _clear_text_entities(self) -> None:
        """Reset per-cook text entities. Defaults (ambient/wind) persist."""
        for purpose, entity in self._texts.items():
            if purpose not in self._PER_COOK_PURPOSES:
                continue
            try:
                await entity.async_set_value("")
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Could not clear %s: %s", purpose, err)

    def _build_row(self, sess: dict[str, Any]) -> dict[str, Any]:
        chamber = sess["chamber_samples"]
        ambient = sess["ambient_samples"]
        wind = sess["wind_samples"]

        started = dt_util.parse_datetime(sess["started_at"])
        ended = dt_util.parse_datetime(sess["ended_at"])
        duration_min = (
            round((ended - started).total_seconds() / 60.0, 1)
            if started and ended else None
        )

        return {
            "cook_id": sess["cook_id"],
            "started_at": sess["started_at"],
            "ended_at": sess["ended_at"],
            "duration_min": duration_min,
            "ambient_start": _fmt(sess.get("ambient_start")),
            "ambient_avg": _fmt(_mean(ambient)),
            "wind_speed_avg": _fmt(_mean(wind)),
            "mode": sess["mode"],
            "smoke_level": sess.get("smoke_level"),
            "setpoint": sess.get("setpoint"),
            "chamber_avg": _fmt(_mean(chamber), 1),
            "chamber_stdev": _fmt(_stdev(chamber), 2),
            "chamber_peak": _fmt(max(chamber) if chamber else None, 0),
            "chamber_min": _fmt(min(chamber) if chamber else None, 0),
            "probe1_target": sess.get("probe1_target"),
            "probe1_initial": _fmt(sess.get("probe1_initial"), 0),
            "probe1_final": _fmt(sess.get("probe1_final"), 0),
            "probe2_target": sess.get("probe2_target"),
            "probe2_initial": _fmt(sess.get("probe2_initial"), 0),
            "probe2_final": _fmt(sess.get("probe2_final"), 0),
            "disturbance_count": sess.get("disturbance_count", 0),
            "ended_normally": int(sess["ended_normally"]),
            "notes": sess["notes"],
            "protein": sess.get("protein") or "",
            "weight_lb": _fmt(sess.get("weight_lb"), 1),
        }

    def _write_row(self, row: dict[str, Any]) -> None:
        """Append one row, creating header if file is new. Blocking I/O."""
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self._csv_path.exists()
        with self._csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            if new_file:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})


# === Module helpers ==========================================


def _mean(xs: list[float]) -> float | None:
    return statistics.fmean(xs) if xs else None


def _stdev(xs: list[float]) -> float | None:
    return statistics.stdev(xs) if len(xs) >= 2 else None


def _fmt(val: float | None, digits: int = 2) -> str:
    """Format numeric for CSV — empty string if None."""
    if val is None:
        return ""
    return f"{val:.{digits}f}"
