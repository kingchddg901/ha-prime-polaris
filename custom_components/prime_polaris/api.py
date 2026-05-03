"""
/* ============================================================
 * api.py — Prime Polaris REST API Client
 * ============================================================
 *
 * Thin async wrapper around the api.prime-polaris.com REST
 * API. Handles auth, token management, and all device calls.
 *
 * All methods raise PrimePolarisAuthError on auth failure,
 * PrimePolarisApiError on other API errors, and
 * PrimePolarisConnectionError on network failures.
 *
 * Auth flow:
 *   1. Call request_otp(email) → triggers email with 6-digit code
 *   2. Call login(email, otp) → returns JWT token + expiry
 *   3. Store token; pass as Bearer on all subsequent requests
 *   4. Token valid ~180 days; re-auth when expired
 *
 * Discovered via decompilation of GrillirG Control v1.1.3.
 * ============================================================
 */
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_BASE,
    CONF_TOKEN,
    EMAIL_TYPE_LOGIN,
    ENDPOINT_DEVICE_LIST,
    ENDPOINT_DEVICE_REALTIME,
    ENDPOINT_DEVICE_SPEC,
    ENDPOINT_DEVICE_STATUS,
    ENDPOINT_LOGIN,
    ENDPOINT_LOGOUT,
    ENDPOINT_PROGRAM_LIST,
    ENDPOINT_SEND_COMMAND,
    ENDPOINT_SEND_OTP,
    RESP_CODE_SUCCESS,
)

_LOGGER = logging.getLogger(__name__)

# === Exceptions ==============================================


class PrimePolarisError(Exception):
    """Base exception for all Prime Polaris errors."""


class PrimePolarisAuthError(PrimePolarisError):
    """Raised when authentication fails or token is invalid."""


class PrimePolarisConnectionError(PrimePolarisError):
    """Raised when the API cannot be reached."""


class PrimePolarisApiError(PrimePolarisError):
    """Raised when the API returns a non-success respCode."""

    def __init__(self, message: str, resp_code: int) -> None:
        super().__init__(message)
        self.resp_code = resp_code


# === Client ==================================================


class PrimePolarisApiClient:
    """Async REST client for the Prime Polaris grill backend.

    Usage:
        client = PrimePolarisApiClient(session)
        await client.request_otp("you@example.com")
        token, expiry = await client.login("you@example.com", "123456")
        client.set_token(token)
        devices = await client.get_device_list()
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialise with a shared aiohttp session.

        The session is owned by the caller (coordinator) and
        should not be closed here.
        """
        self._session = session
        self._token: str | None = None

    # --- Auth ------------------------------------------------

    def set_token(self, token: str) -> None:
        """Set the JWT token for authenticated requests."""
        self._token = token

    async def request_otp(self, email: str) -> None:
        """Request a 6-digit OTP be sent to the given email.

        Raises PrimePolarisApiError if the request fails.
        """
        await self._post(
            ENDPOINT_SEND_OTP,
            {"email": email, "emailType": EMAIL_TYPE_LOGIN},
            authenticated=False,
        )

    async def login(self, email: str, otp: str) -> tuple[str, int]:
        """Exchange email + OTP for a JWT token.

        Returns:
            (token, expiry_timestamp) where expiry_timestamp is
            a Unix timestamp integer from the JWT payload.

        Raises PrimePolarisAuthError on bad credentials.
        """
        data = await self._post(
            ENDPOINT_LOGIN,
            {"email": email, "verifyCode": otp, "emailType": EMAIL_TYPE_LOGIN},
            authenticated=False,
        )

        token = data.get("token")
        if not token:
            raise PrimePolarisAuthError("No token in login response")

        # Decode expiry from JWT payload (middle segment, base64)
        expiry = _decode_jwt_expiry(token)

        return token, expiry

    async def logout(self) -> None:
        """Invalidate the current session token."""
        try:
            await self._post(ENDPOINT_LOGOUT, None)
        except PrimePolarisError:
            pass  # Best effort — don't raise on logout failure
        finally:
            self._token = None

    # --- Device ----------------------------------------------

    async def get_device_list(self) -> list[dict[str, Any]]:
        """Return list of devices bound to the authenticated account."""
        data = await self._post(ENDPOINT_DEVICE_LIST, {})
        return data.get("list", [])

    async def get_device_realtime(self, device_id: str) -> dict[str, Any]:
        """Return current real-time state for the given device."""
        return await self._post(
            ENDPOINT_DEVICE_REALTIME, {"deviceId": device_id}
        )

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Return online/running status for the given device."""
        return await self._post(
            ENDPOINT_DEVICE_STATUS, {"deviceId": device_id}
        )

    async def get_device_spec(self, device_id: str) -> dict[str, Any]:
        """Return hardware specification for the given device."""
        return await self._post(
            ENDPOINT_DEVICE_SPEC, {"deviceId": device_id}
        )

    async def get_program_list(self, device_id: str) -> list[dict[str, Any]]:
        """Return available cook programs/recipes for the device."""
        data = await self._post(
            ENDPOINT_PROGRAM_LIST, {"deviceId": device_id}
        )
        return data.get("list", [])

    # --- Commands --------------------------------------------

    async def send_command(
        self, device_id: str, firmware_version: str, fields: dict
    ) -> None:
        """Send a control command to the device.

        The API expects a flat payload — deviceId and firmwareVersion
        alongside the command-specific fields directly. There is no
        requestData wrapper. Verified against live API 2026-05-02.

        Confirmed payload field names:
          Temperature:  furnace_temp_setting = <int>
          Smoke:        smoke_mode_and_smoke_level = [mode, level]
          Power off:    device_switch = 0  (power ON is server-blocked)
          Alarm:        alarm_switch = 0|1
          Winter mode:  winter_and_ref_temp = [0|1, refTemp]
          Probe temp:   setProbeTemp = [{"probeId": n, "temp_and_status": [temp, 1]}]
        """
        _LOGGER.debug(
            "Sending command to device %s: %s", device_id, fields
        )
        payload = {
            "deviceId": device_id,
            "firmwareVersion": firmware_version,
            **fields,
        }
        await self._post(ENDPOINT_SEND_COMMAND, payload)

    # --- Command helpers -------------------------------------

    async def set_device_switch(
        self, device_id: str, on: bool, firmware_version: str = ""
    ) -> None:
        """Turn the grill off. Power-on is blocked server-side."""
        await self.send_command(
            device_id, firmware_version, {"device_switch": 1 if on else 0}
        )

    async def set_temperature(
        self, device_id: str, temp: int, firmware_version: str = ""
    ) -> None:
        """Set the grill target temperature."""
        await self.send_command(
            device_id, firmware_version, {"furnace_temp_setting": temp}
        )

    async def set_smoke(
        self,
        device_id: str,
        smoke_mode: int,
        smoke_level: int,
        firmware_version: str = "",
    ) -> None:
        """Set smoke mode and level together.

        The API requires both values in a single call as an array.
        smoke_mode: 0=off, 1=on
        smoke_level: 0-10
        """
        await self.send_command(
            device_id,
            firmware_version,
            {"smoke_mode_and_smoke_level": [smoke_mode, smoke_level]},
        )

    async def set_probe_target(
        self,
        device_id: str,
        probe_id: int,
        target_temp: int,
        firmware_version: str = "",
    ) -> None:
        """Set a meat probe target alert temperature.

        probe_id: 1 or 2
        target_temp: temperature in current unit
        """
        await self.send_command(
            device_id,
            firmware_version,
            {
                "setProbeTemp": [
                    {"probeId": probe_id, "temp_and_status": [target_temp, 1]}
                ]
            },
        )

    async def set_alarm_switch(
        self, device_id: str, enabled: bool, firmware_version: str = ""
    ) -> None:
        """Enable or disable the temperature alarm."""
        await self.send_command(
            device_id, firmware_version, {"alarm_switch": 1 if enabled else 0}
        )

    async def set_winter_mode(
        self,
        device_id: str,
        enabled: bool,
        ref_temp: int = 0,
        firmware_version: str = "",
    ) -> None:
        """Enable or disable winter mode (cold weather compensation).

        Requires ref_temp (current furnace temp) alongside the toggle.
        """
        await self.send_command(
            device_id,
            firmware_version,
            {"winter_and_ref_temp": [1 if enabled else 0, ref_temp]},
        )

    # --- HTTP internals --------------------------------------

    def _headers(self, authenticated: bool) -> dict[str, str]:
        """Build request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if authenticated:
            if not self._token:
                raise PrimePolarisAuthError("No token set — must login first")
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _post(
        self,
        endpoint: str,
        body: dict[str, Any] | None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """POST to the API and return the response data dict.

        Handles:
          - Network errors → PrimePolarisConnectionError
          - HTTP errors → PrimePolarisConnectionError
          - API error codes → PrimePolarisAuthError or PrimePolarisApiError
          - Success → returns data field contents
        """
        url = f"{API_BASE}{endpoint}"
        headers = self._headers(authenticated)

        try:
            async with self._session.post(
                url,
                json=body or {},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()

        except aiohttp.ClientResponseError as err:
            raise PrimePolarisConnectionError(
                f"HTTP {err.status} from {endpoint}"
            ) from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise PrimePolarisConnectionError(
                f"Connection failed to {endpoint}: {err}"
            ) from err

        resp_code = payload.get("respCode")
        resp_msg = payload.get("respMessage", "Unknown error")

        if resp_code != RESP_CODE_SUCCESS:
            # Auth errors use negative codes in the -1xxxx range.
            # -10108 is "session displaced by login elsewhere" — same
            # remediation as a normal expired token (must reauth), but
            # the cloud distinguishes the cause. Confirmed in the wild
            # 2026-05-02 when a parallel session bumped this account.
            if resp_code in (-10001, -10002, -10003, -10007, -10108):
                raise PrimePolarisAuthError(
                    f"Auth error {resp_code}: {resp_msg}"
                )
            raise PrimePolarisApiError(resp_msg, resp_code)

        return payload.get("data") or {}


# === Helpers =================================================


def _decode_jwt_expiry(token: str) -> int:
    """Extract the exp claim from a JWT without verifying signature.

    Returns Unix timestamp integer, or current time + 180 days
    if decoding fails.
    """
    import base64
    import json

    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Not a valid JWT")

        # Add padding required by base64
        payload_b64 = parts[1] + "=="
        payload_json = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_json)
        return int(payload["exp"])

    except Exception:  # noqa: BLE001
        _LOGGER.warning("Could not decode JWT expiry; using 180-day default")
        return int(time.time()) + (180 * 24 * 3600)
