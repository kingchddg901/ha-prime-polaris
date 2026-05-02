"""
/* ============================================================
 * config_flow.py — Prime Polaris Config & Reauth Flow
 * ============================================================
 *
 * Implements the HA config flow for initial setup and
 * re-authentication. The flow is two-step because the API
 * uses email OTP login:
 *
 *   Step 1 (user): Enter email address → triggers OTP email
 *   Step 2 (otp):  Enter 6-digit code → exchanges for JWT
 *
 * On success, stores token, expiry, user ID, and device info
 * in the config entry. If multiple devices exist on the account
 * a device selector step is shown.
 *
 * Reauth flow reuses the same two steps and updates the
 * existing config entry's token fields in place.
 * ============================================================
 */
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    PrimePolarisApiClient,
    PrimePolarisAuthError,
    PrimePolarisConnectionError,
    PrimePolarisError,
)
from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_EMAIL,
    CONF_FIRMWARE_VERSION,
    CONF_TOKEN,
    CONF_TOKEN_EXPIRY,
    CONF_USER_ID,
    DEFAULT_FCM_DEDUP_SECONDS,
    DOMAIN,
    NAME,
    OPT_FCM_DEDUP_SECONDS,
    OPT_FCM_ENABLED,
)

_LOGGER = logging.getLogger(__name__)

# === Schemas =================================================

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
    }
)

STEP_OTP_SCHEMA = vol.Schema(
    {
        vol.Required("otp"): str,
    }
)


def _device_selector_schema(devices: list[dict]) -> vol.Schema:
    """Build a schema with a device selector populated from the API."""
    options = {d["id"]: d.get("deviceName", d["id"]) for d in devices}
    return vol.Schema(
        {
            vol.Required(CONF_DEVICE_ID): vol.In(options),
        }
    )


# === Flow ====================================================


class PrimePolarisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Prime Polaris Pellet Grill integration.

    Handles initial setup and re-authentication. The flow stores
    the email address temporarily between steps so the OTP step
    knows which account to authenticate.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._email: str = ""
        self._token: str = ""
        self._token_expiry: int = 0
        self._user_id: str = ""
        self._devices: list[dict] = []
        self._client: PrimePolarisApiClient | None = None

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return PrimePolarisOptionsFlow(entry)

    # --- Step 1: Email entry ---------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — collect email and send OTP."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL].strip().lower()
            self._client = PrimePolarisApiClient(
                async_get_clientsession(self.hass)
            )

            try:
                await self._client.request_otp(self._email)
            except PrimePolarisConnectionError:
                errors["base"] = "cannot_connect"
            except PrimePolarisError:
                errors["base"] = "unknown"
            else:
                return await self.async_step_otp()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={"name": NAME},
        )

    # --- Step 2: OTP entry -----------------------------------

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle OTP entry — exchange code for JWT token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            otp = user_input["otp"].strip()

            try:
                self._token, self._token_expiry = await self._client.login(
                    self._email, otp
                )
                self._client.set_token(self._token)
                devices = await self._client.get_device_list()

            except PrimePolarisAuthError:
                errors["base"] = "invalid_auth"
            except PrimePolarisConnectionError:
                errors["base"] = "cannot_connect"
            except PrimePolarisError:
                errors["base"] = "unknown"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                elif len(devices) == 1:
                    # Only one device — skip selector
                    return self._create_entry(devices[0])
                else:
                    self._devices = devices
                    return await self.async_step_device()

        return self.async_show_form(
            step_id="otp",
            data_schema=STEP_OTP_SCHEMA,
            errors=errors,
            description_placeholders={"email": self._email},
        )

    # --- Step 3: Device selector (multi-device accounts) -----

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device selection for accounts with multiple grills."""
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            device = next(d for d in self._devices if d["id"] == device_id)
            return self._create_entry(device)

        return self.async_show_form(
            step_id="device",
            data_schema=_device_selector_schema(self._devices),
        )

    # --- Reauth flow -----------------------------------------

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication when token has expired."""
        # Pre-populate email from existing config entry
        existing = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id", "")
        )
        if existing:
            self._email = existing.data.get(CONF_EMAIL, "")

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth and send new OTP."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input.get(CONF_EMAIL, self._email).strip().lower()
            self._client = PrimePolarisApiClient(
                async_get_clientsession(self.hass)
            )

            try:
                await self._client.request_otp(self._email)
            except PrimePolarisConnectionError:
                errors["base"] = "cannot_connect"
            except PrimePolarisError:
                errors["base"] = "unknown"
            else:
                return await self.async_step_reauth_otp()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_EMAIL, default=self._email): str}),
            errors=errors,
        )

    async def async_step_reauth_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle OTP entry during reauth."""
        errors: dict[str, str] = {}

        if user_input is not None:
            otp = user_input["otp"].strip()

            try:
                self._token, self._token_expiry = await self._client.login(
                    self._email, otp
                )
            except PrimePolarisAuthError:
                errors["base"] = "invalid_auth"
            except PrimePolarisConnectionError:
                errors["base"] = "cannot_connect"
            except PrimePolarisError:
                errors["base"] = "unknown"
            else:
                # Update the existing entry with new token
                entry_id = self.context.get("entry_id", "")
                existing = self.hass.config_entries.async_get_entry(entry_id)
                if existing:
                    self.hass.config_entries.async_update_entry(
                        existing,
                        data={
                            **existing.data,
                            CONF_TOKEN: self._token,
                            CONF_TOKEN_EXPIRY: self._token_expiry,
                            CONF_EMAIL: self._email,
                        },
                    )
                    await self.hass.config_entries.async_reload(entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_otp",
            data_schema=STEP_OTP_SCHEMA,
            errors=errors,
            description_placeholders={"email": self._email},
        )

    # --- Helpers ---------------------------------------------

    def _create_entry(self, device: dict) -> ConfigFlowResult:
        """Create the config entry with device and auth data."""
        return self.async_create_entry(
            title=device.get("deviceName", NAME),
            data={
                CONF_EMAIL: self._email,
                CONF_TOKEN: self._token,
                CONF_TOKEN_EXPIRY: self._token_expiry,
                CONF_DEVICE_ID: device["id"],
                CONF_DEVICE_NAME: device.get("deviceName", NAME),
                CONF_FIRMWARE_VERSION: device.get("firmwareVersion", ""),
            },
        )


# === Options flow ============================================


class PrimePolarisOptionsFlow(OptionsFlow):
    """Per-entry options.

    Currently exposes:
      - fcm_enabled: opt-in to FCM push listening. WARNING: this
        registers an FCM token under the entry's account, which
        replaces any existing token (e.g. the user's phone). For
        the recommended dual-account setup, only enable this on
        the SECONDARY config entry; leave it off on the primary.
      - fcm_dedup_seconds: window during which repeat pushes for
        the same alarm category are suppressed.
    """

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_enabled = self._entry.options.get(OPT_FCM_ENABLED, False)
        current_dedup = self._entry.options.get(
            OPT_FCM_DEDUP_SECONDS, DEFAULT_FCM_DEDUP_SECONDS
        )

        schema = vol.Schema({
            vol.Required(OPT_FCM_ENABLED, default=current_enabled): bool,
            vol.Required(
                OPT_FCM_DEDUP_SECONDS, default=current_dedup
            ): vol.All(int, vol.Range(min=10, max=3600)),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
