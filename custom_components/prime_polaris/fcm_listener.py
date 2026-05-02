"""
/* ============================================================
 * fcm_listener.py — Persistent FCM (Push) Listener
 * ============================================================
 *
 * Optional, opt-in component that connects to Google's Mobile
 * Connection Server (MCS) using the OEM Firebase credentials
 * recovered from the GrillirG APK, then receives the same
 * push notifications the official mobile app receives.
 *
 * Works in two modes (decided by the user, not by code):
 *   - Dual-account (recommended): HA uses a secondary prime-
 *     polaris account with the device shared to it. Phone keeps
 *     OEM pushes since the primary account is untouched.
 *   - Single-account: HA registers under the primary account.
 *     Phone stops receiving pushes until the user reopens the
 *     official app (which re-registers the phone's token).
 *
 * Either way the integration code is identical — only the JWT
 * differs, and the JWT is per-entry.
 *
 * Each captured push:
 *   - Updates coordinator.last_alarm so sensor.grill_last_alarm
 *     reflects FCM-driven alarms (alongside polled alarmEvent).
 *   - Fires HA event prime_polaris_fcm_alarm for automations.
 *
 * Dedupe: pushes for the same notification.title within
 * OPT_FCM_DEDUP_SECONDS are suppressed (avoids spam during
 * sustained alarm conditions where the server fires every
 * 25–30s).
 *
 * Persistence: FCM device credentials (FID + registration
 * blob) are stored via HA's Store helper keyed by entry_id so
 * we don't re-register on every restart.
 * ============================================================
 */
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    API_BASE,
    CONF_TOKEN,
    DEFAULT_FCM_DEDUP_SECONDS,
    DOMAIN,
    ENDPOINT_REGISTER_FCM_TOKEN,
    EVENT_FCM_ALARM,
    FCM_API_KEY,
    FCM_APP_ID,
    FCM_BUNDLE_ID,
    FCM_PROJECT_ID,
    FCM_SENDER_ID,
    OPT_FCM_DEDUP_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


def _store_key(entry_id: str) -> str:
    return f"{DOMAIN}_fcm_{entry_id}"


class PrimePolarisFcmListener:
    """Persistent FCM listener bound to a single config entry.

    Lifecycle:
      async_start  → load saved credentials, register with FCM
                     (re-using saved creds if any), POST token to
                     prime-polaris, then connect to MCS.
      async_stop   → disconnect from MCS, leave creds on disk
                     so next start is fast.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: Any,  # PrimePolarisCoordinator (avoiding circular import)
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._store: Store = Store(hass, STORAGE_VERSION, _store_key(entry.entry_id))

        # Lazy-loaded — the firebase_messaging package is heavy and we
        # only want to import when FCM is actually enabled.
        self._client: Any | None = None
        self._fcm_token: str | None = None

        # Dedupe state: title → last-fired epoch
        self._last_fired: dict[str, float] = {}

    async def async_start(self) -> None:
        try:
            from firebase_messaging import FcmPushClient, FcmPushClientConfig
            from firebase_messaging.fcmpushclient import FcmRegisterConfig
        except ImportError as err:
            _LOGGER.error(
                "firebase-messaging package is not installed: %s", err,
            )
            return

        creds = await self._store.async_load()

        fcm_config = FcmRegisterConfig(
            project_id=FCM_PROJECT_ID,
            app_id=FCM_APP_ID,
            api_key=FCM_API_KEY,
            messaging_sender_id=FCM_SENDER_ID,
            bundle_id=FCM_BUNDLE_ID,
        )
        client_config = FcmPushClientConfig(send_selective_acknowledgements=True)

        self._client = FcmPushClient(
            callback=self._on_notification,
            fcm_config=fcm_config,
            credentials=creds,
            credentials_updated_callback=self._on_credentials_updated,
            config=client_config,
        )

        try:
            self._fcm_token = await self._client.checkin_or_register()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("FCM check-in/register failed: %s", err)
            return

        _LOGGER.info("FCM token acquired for entry %s", self._entry.entry_id)

        # Register the FCM token with prime-polaris so pushes route to us
        ok = await self._register_with_polaris(self._fcm_token)
        if not ok:
            _LOGGER.warning(
                "Could not register FCM token with prime-polaris — pushes "
                "will not be addressed to this device"
            )

        try:
            await self._client.start()
            _LOGGER.info("FCM listener connected to MCS")
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("FCM MCS start failed: %s", err)

    async def async_stop(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.stop()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("FCM stop raised (likely already disconnected): %s", err)
        self._client = None

    # --- Push handling ---------------------------------------

    def _on_notification(
        self, notification: dict | None, persistent_id: str, obj: Any
    ) -> None:
        """Called by firebase-messaging on each incoming push.

        Runs on the event loop (the lib hands the callback off
        without offloading), so we keep work small and synchronous.
        """
        if not isinstance(notification, dict):
            return

        notif = notification.get("notification") or {}
        data = notification.get("data") or {}
        title = notif.get("title") or "Alarm"
        body = notif.get("body") or ""

        # Dedupe: suppress same-title pushes within the dedupe window
        dedup_window = int(
            self._entry.options.get(
                OPT_FCM_DEDUP_SECONDS, DEFAULT_FCM_DEDUP_SECONDS
            )
        )
        now = time.time()
        last = self._last_fired.get(title, 0.0)
        if now - last < dedup_window:
            _LOGGER.debug(
                "FCM dedupe: suppressing repeat '%s' (%.1fs since last)",
                title, now - last,
            )
            return
        self._last_fired[title] = now

        # data.params is itself a JSON-encoded string — parse defensively
        params: dict[str, Any] = {}
        raw_params = data.get("params")
        if isinstance(raw_params, str):
            try:
                params = json.loads(raw_params)
            except json.JSONDecodeError:
                params = {"raw": raw_params}
        elif isinstance(raw_params, dict):
            params = raw_params

        captured_at = dt_util.utcnow().isoformat()

        # Update coordinator's last_alarm so sensor.grill_last_alarm
        # reflects this. Same shape as polled alarmEvent path.
        self._coordinator.last_alarm = {
            "events": [{"title": title, "body": body, "params": params}],
            "count": 1,
            "captured_at": captured_at,
            "source": "fcm",
        }
        # Touch entities so the sensor reflects immediately
        try:
            self._coordinator.async_update_listeners()
        except Exception:  # noqa: BLE001
            pass

        # Fire HA event — automations subscribe here
        self._hass.bus.async_fire(
            EVENT_FCM_ALARM,
            {
                "device_id": self._coordinator.device_id,
                "title": title,
                "body": body,
                "params": params,
                "fcm_message_id": notification.get("fcmMessageId"),
                "received_at": captured_at,
            },
        )

        _LOGGER.info("FCM push received: %s — %s", title, body)

    def _on_credentials_updated(self, creds: Any) -> None:
        """Persist updated FCM credentials (FID, registration blob)."""
        # The lib calls this synchronously; schedule the save on the loop
        if hasattr(creds, "model_dump"):
            data = creds.model_dump()
        elif isinstance(creds, dict):
            data = creds
        else:
            data = {"raw": str(creds)}

        async def _save() -> None:
            await self._store.async_save(data)

        self._hass.async_create_task(_save())

    # --- prime-polaris token registration --------------------

    async def _register_with_polaris(self, fcm_token: str) -> bool:
        """POST the FCM token to /api/auth/registerFcmToken."""
        session = async_get_clientsession(self._hass)
        url = f"{API_BASE}{ENDPOINT_REGISTER_FCM_TOKEN}"
        headers = {
            "Authorization": f"Bearer {self._entry.data.get(CONF_TOKEN, '')}",
            "Content-Type": "application/json",
        }
        body = {"fcmToken": fcm_token, "deviceType": "android"}
        try:
            async with session.post(
                url, json=body, headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                payload = await resp.json(content_type=None)
        except (aiohttp.ClientError, json.JSONDecodeError) as err:
            _LOGGER.error("registerFcmToken request failed: %s", err)
            return False

        if payload.get("respCode") == 10000:
            _LOGGER.info(
                "FCM token registered with prime-polaris (account=%s)",
                self._entry.data.get("email", "?"),
            )
            return True

        _LOGGER.error(
            "registerFcmToken rejected: %s (%s)",
            payload.get("respMessage"), payload.get("respCode"),
        )
        return False
