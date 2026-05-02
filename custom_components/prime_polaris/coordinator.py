"""
/* ============================================================
 * coordinator.py — Prime Polaris Data Update Coordinator
 * ============================================================
 *
 * DataUpdateCoordinator subclass that polls the Prime Polaris
 * API every POLL_INTERVAL seconds and distributes state to all
 * platform entities via the standard HA coordinator pattern.
 *
 * Each coordinator instance manages exactly one grill device.
 * Multiple grills (if ever supported) would each get their own
 * coordinator instance.
 *
 * Token expiry handling:
 *   - JWT expires after ~180 days
 *   - On auth failure during poll, fires a persistent HA
 *     notification prompting the user to re-authenticate via
 *     the integration's config flow (Options flow re-auth)
 *   - Does not attempt silent re-auth since OTP requires
 *     human interaction
 * ============================================================
 */
"""

from __future__ import annotations

import json
import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import (
    PrimePolarisApiClient,
    PrimePolarisApiError,
    PrimePolarisAuthError,
    PrimePolarisConnectionError,
    PrimePolarisError,
)
from .const import (
    CONF_DEVICE_ID,
    CONF_FIRMWARE_VERSION,
    CONF_TOKEN,
    CONF_TOKEN_EXPIRY,
    DOMAIN,
    EVENT_ALARM,
    FIELD_ALARM_EVENT,
    POLL_FAILURE_TOLERANCE,
    POLL_INTERVAL,
    TOKEN_EXPIRY_BUFFER_SECONDS,
)
from .cook_predictor import CookPredictor
from .session_logger import CookSessionTracker

_LOGGER = logging.getLogger(__name__)

# Repairs issue id for the "token nearing expiry" warning. Tied
# to the config entry so multiple grills don't share an issue.
def _token_expiry_issue_id(entry_id: str) -> str:
    return f"token_near_expiry_{entry_id}"


class PrimePolarisCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for a single Prime Polaris grill device.

    Polls queryDeviceRealTimeData on the configured interval and
    makes the result available to all platform entities via
    coordinator.data.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: PrimePolarisApiClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialise the coordinator.

        Args:
            hass:   HA instance.
            client: Authenticated API client.
            entry:  Config entry for this integration instance.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.client = client
        self.entry = entry
        self.device_id: str = entry.data[CONF_DEVICE_ID]
        self.firmware_version: str = entry.data.get(CONF_FIRMWARE_VERSION, "")
        self._reauth_notified = False

        # Alarm event tracking.
        # alarmEvent in the realtime payload is transient — the cloud
        # does not retain history. We diff each poll, fire HA events
        # for new entries, and keep a snapshot for the "last alarm"
        # sensor so users can still see what happened after it cleared.
        # Entry shape is unknown until first capture; treat opaquely.
        self._last_alarm_sigs: list[str] = []
        self.last_alarm: dict[str, Any] | None = None

        # Tolerate a single failed poll before flipping entities to
        # unavailable. The cloud occasionally returns 5xx for one tick
        # and recovers on the next — without this, every blip blanks
        # the dashboard.
        self._consecutive_failures = 0

        # Cook-session tracker — manual start/stop via switch.cook_session,
        # auto-stop fallback when the grill goes off mid-session. CSV
        # at <config>/prime_polaris/sessions.csv. Text entities register
        # themselves with the tracker on setup (avoids brittle entity_id
        # guessing if the device gets renamed in HA).
        csv_path = Path(hass.config.path("prime_polaris")) / "sessions.csv"
        self.session_tracker = CookSessionTracker(
            hass=hass,
            csv_path=csv_path,
        )

        # Live predictor — Newton's-law fit + stall detection. Runs
        # whenever a probe is plugged in, regardless of whether a
        # cook session is being recorded. Reset by the disturbance
        # path so a lid open doesn't poison the fit. Loads Tier 2
        # priors (per-protein, weight-scaled) from the same CSV so
        # historical cooks improve early-cook ETAs.
        self.predictor = CookPredictor(csv_path=csv_path)

    # --- DataUpdateCoordinator interface ---------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest state from the API.

        Called automatically by the coordinator on the poll
        interval. Returns the full realtime data dict on success.

        Raises UpdateFailed on any error so HA marks entities
        as unavailable rather than showing stale data.
        """
        # Check token expiry before attempting the poll
        self._check_token_expiry()

        try:
            data = await self.client.get_device_realtime(self.device_id)
            _LOGGER.debug("Poll result for %s: %s", self.device_id, data)

            # Clear any existing reauth notification if poll succeeds
            if self._reauth_notified:
                self._reauth_notified = False

            self._consecutive_failures = 0
            self._process_alarm_events(data.get(FIELD_ALARM_EVENT))
            self.session_tracker.observe(data)

            # Feed the predictor (Newton's-law fit + stall detect).
            # Override resolution: if the user has typed a trusted entity
            # into the chamber/probe override text inputs (Setup tab),
            # use that source instead of the OEM reading. Predictor's
            # Newton's-law math is only as good as its inputs — overrides
            # let users feed it ThermoMaven / instant-read truth temps.
            chamber_oem = data.get("furnaceTempMeasured")
            probe_1_oem = data.get("probeP1Measured")
            probe_2_oem = data.get("probeP2Measured")

            chamber = self._resolve_override("chamber_override", chamber_oem)
            probe_1 = self._resolve_override("probe_1_override", probe_1_oem)
            probe_2 = self._resolve_override("probe_2_override", probe_2_oem)

            if chamber is not None:
                try:
                    self.predictor.observe(
                        ts=dt_util.utcnow(),
                        chamber=float(chamber),
                        probe_1=probe_1,
                        probe_2=probe_2,
                    )
                except (TypeError, ValueError):
                    pass

            return data

        except PrimePolarisAuthError as err:
            # Token rejected — no point retrying, raise immediately
            self._notify_reauth_required()
            self._consecutive_failures = 0
            raise UpdateFailed(f"Authentication failed: {err}") from err

        except (PrimePolarisConnectionError, PrimePolarisError) as err:
            self._consecutive_failures += 1
            # Cloud APIs blip — tolerate up to POLL_FAILURE_TOLERANCE
            # consecutive failures before flipping entities to
            # unavailable. Each suppressed failure still logs so real
            # outages aren't silent.
            if (
                self._consecutive_failures <= POLL_FAILURE_TOLERANCE
                and self.data is not None
            ):
                _LOGGER.warning(
                    "Prime Polaris poll failed (%d/%d, transient): %s",
                    self._consecutive_failures, POLL_FAILURE_TOLERANCE, err,
                )
                return self.data
            kind = (
                "Connection error"
                if isinstance(err, PrimePolarisConnectionError)
                else "API error"
            )
            raise UpdateFailed(f"{kind}: {err}") from err

    # --- Commands --------------------------------------------

    async def async_send_command(self, fields: dict) -> None:
        """Send a command to the grill and immediately refresh state.

        Args:
            fields: Flat dict of command-specific fields to merge into
                    the API payload alongside deviceId/firmwareVersion.
                    See api.py send_command docstring for field names.

        Raises:
            HomeAssistantError: Wrapped, user-readable error if the
                command fails. Auth failures also trigger the reauth
                notification path (same behavior as poll-side auth fail).
        """
        try:
            await self.client.send_command(
                self.device_id, self.firmware_version, fields
            )
        except PrimePolarisAuthError as err:
            self._notify_reauth_required()
            raise HomeAssistantError(
                f"Prime Polaris authentication failed — re-authentication "
                f"required. ({err})"
            ) from err
        except PrimePolarisConnectionError as err:
            raise HomeAssistantError(
                f"Cannot reach Prime Polaris cloud — check your internet "
                f"connection. ({err})"
            ) from err
        except PrimePolarisApiError as err:
            raise HomeAssistantError(
                f"Prime Polaris rejected the command: {err}"
            ) from err
        except PrimePolarisError as err:
            raise HomeAssistantError(
                f"Prime Polaris command failed: {err}"
            ) from err

        await self.async_request_refresh()

    # --- Alarm events ----------------------------------------

    def _process_alarm_events(self, raw_events: Any) -> None:
        """Diff the alarmEvent list and fire HA events for new entries.

        The cloud reports active alarms via alarmEvent in the realtime
        payload; once the underlying condition clears the entries are
        removed. This method maintains a signature of the last-seen
        list and fires {DOMAIN}_alarm on the bus for each newly added
        entry, plus updates self.last_alarm for the sensor.

        Entry shape is unknown until observed in the wild — handled
        opaquely. When a real event finally lands we'll see it in the
        log and can surface specific fields.
        """
        events = raw_events if isinstance(raw_events, list) else (
            [raw_events] if raw_events else []
        )

        try:
            current_sigs = [
                json.dumps(e, sort_keys=True, default=str) for e in events
            ]
        except (TypeError, ValueError):
            # Fall back to repr if anything is non-serialisable
            current_sigs = [repr(e) for e in events]

        prev_sigs = self._last_alarm_sigs
        new_entries = [
            entry for entry, sig in zip(events, current_sigs)
            if sig not in prev_sigs
        ]

        for entry in new_entries:
            _LOGGER.warning(
                "Prime Polaris alarm event captured (device %s): %s",
                self.device_id, entry,
            )
            self.hass.bus.async_fire(
                EVENT_ALARM,
                {
                    "device_id": self.device_id,
                    "event": entry,
                    "captured_at": dt_util.utcnow().isoformat(),
                },
            )

        self._last_alarm_sigs = current_sigs

        if events:
            self.last_alarm = {
                "events": events,
                "count": len(events),
                "captured_at": dt_util.utcnow().isoformat(),
            }
        # When events go back to empty we keep last_alarm so the
        # sensor still shows the most recent alarm we observed.

    # --- Override sources ------------------------------------

    def _resolve_override(self, purpose: str, fallback) -> float | None:
        """Read an override text input by purpose, resolve to a value.

        - Empty / missing → returns `fallback` (the OEM reading)
        - "domain.entity_id" → reads hass.states[that].state, parses as float
        - "weather.X" → pulls from attributes.temperature
        - Plain numeric string → parsed as literal value
        - Anything that can't be resolved → returns fallback (don't break
          the predictor on a typo)
        """
        tracker = getattr(self, "session_tracker", None)
        if tracker is None:
            return fallback
        raw = tracker.get_input(purpose) if hasattr(tracker, "get_input") else ""
        if not raw:
            return fallback

        raw = raw.strip()

        # entity_id form
        if "." in raw and " " not in raw:
            state = self.hass.states.get(raw)
            if state is None:
                return fallback
            # weather.* entities expose temperature in attributes
            if raw.startswith("weather.") and state.attributes:
                t = state.attributes.get("temperature")
                if t is not None:
                    try:
                        return float(t)
                    except (TypeError, ValueError):
                        return fallback
            try:
                return float(state.state)
            except (TypeError, ValueError):
                return fallback

        # Literal numeric value
        try:
            return float(raw)
        except (TypeError, ValueError):
            return fallback

    # --- Token management ------------------------------------

    def _check_token_expiry(self) -> None:
        """Surface a Repairs issue if the token is approaching expiry.

        Modern HA pattern: instead of a logger warning that nobody
        sees, raise a Repairs issue with the email + remaining days.
        The issue auto-clears once reauth refreshes the token.
        """
        expiry = self.entry.data.get(CONF_TOKEN_EXPIRY, 0)
        remaining = expiry - time.time()
        issue_id = _token_expiry_issue_id(self.entry.entry_id)

        if 0 < remaining < TOKEN_EXPIRY_BUFFER_SECONDS:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="token_near_expiry",
                translation_placeholders={
                    "email": self.entry.data.get("email", ""),
                    "days": str(max(int(remaining // 86400), 0)),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _notify_reauth_required(self) -> None:
        """Trigger HA's reauth flow on the config entry.

        Modern pattern: entry.async_start_reauth() puts a
        "Reconfigure" button on the integration tile and runs the
        reauth flow already defined in config_flow.py — no manual
        persistent notification needed.
        """
        if self._reauth_notified:
            return

        self._reauth_notified = True
        self.entry.async_start_reauth(self.hass)
        _LOGGER.error(
            "Prime Polaris authentication failed — re-auth required. "
            "Entities will be unavailable until reconfigured."
        )
