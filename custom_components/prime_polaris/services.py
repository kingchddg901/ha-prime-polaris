"""
/* ============================================================
 * services.py — Prime Polaris HA Services
 * ============================================================
 *
 * Registers integration-level services that the custom Lovelace
 * card uses to drive account flows without dragging the user
 * through Settings → Devices & Services.
 *
 * Services:
 *   request_otp(email)
 *     Send a 6-digit code to email.
 *
 *   verify_otp(email, otp, entry_id?)
 *     Exchange email + OTP for a fresh JWT, update the matching
 *     config entry, reload it.
 *
 *   clear_cook_inputs(entry_id?)
 *     Reset notes / protein / weight text entities.
 * ============================================================
 */
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    PrimePolarisApiClient,
    PrimePolarisAuthError,
    PrimePolarisConnectionError,
    PrimePolarisError,
)
from .const import (
    CONF_EMAIL,
    CONF_TOKEN,
    CONF_TOKEN_EXPIRY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_REQUEST_OTP       = "request_otp"
SERVICE_VERIFY_OTP        = "verify_otp"
SERVICE_CLEAR_COOK_INPUTS = "clear_cook_inputs"

REQUEST_OTP_SCHEMA = vol.Schema({
    vol.Required("email"): vol.All(str, vol.Length(min=3)),
})

VERIFY_OTP_SCHEMA = vol.Schema({
    vol.Required("email"):    vol.All(str, vol.Length(min=3)),
    vol.Required("otp"):      vol.All(str, vol.Length(min=4, max=10)),
    vol.Optional("entry_id"): str,
})

CLEAR_COOK_INPUTS_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
})


def _resolve_entry(hass: HomeAssistant, entry_id: str | None) -> ConfigEntry:
    """Pick the target config entry — explicit id, or the only one."""
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            raise HomeAssistantError(f"Config entry {entry_id} not found")
        if entry.domain != DOMAIN:
            raise HomeAssistantError("Entry is not a Prime Polaris entry")
        return entry
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError("No Prime Polaris config entries configured")
    if len(entries) > 1:
        raise HomeAssistantError(
            "Multiple Prime Polaris entries found — pass entry_id"
        )
    return entries[0]


def async_register_services(hass: HomeAssistant) -> None:
    """Register the integration-level services. Idempotent."""
    if hass.services.has_service(DOMAIN, SERVICE_REQUEST_OTP):
        return

    async def _request_otp(call: ServiceCall) -> None:
        email = call.data["email"].strip().lower()
        client = PrimePolarisApiClient(async_get_clientsession(hass))
        try:
            await client.request_otp(email)
        except PrimePolarisConnectionError as err:
            raise HomeAssistantError(
                f"Cannot reach Prime Polaris cloud: {err}"
            ) from err
        except PrimePolarisError as err:
            raise HomeAssistantError(f"OTP request failed: {err}") from err

    async def _verify_otp(call: ServiceCall) -> None:
        email = call.data["email"].strip().lower()
        otp   = call.data["otp"].strip()
        entry = _resolve_entry(hass, call.data.get("entry_id"))

        client = PrimePolarisApiClient(async_get_clientsession(hass))
        try:
            token, expiry = await client.login(email, otp)
        except PrimePolarisAuthError as err:
            raise HomeAssistantError(
                f"Invalid code or email: {err}"
            ) from err
        except PrimePolarisConnectionError as err:
            raise HomeAssistantError(
                f"Cannot reach Prime Polaris cloud: {err}"
            ) from err
        except PrimePolarisError as err:
            raise HomeAssistantError(f"Login failed: {err}") from err

        # Update entry with the new token. Reload so the coordinator
        # picks up the fresh JWT immediately.
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_TOKEN:        token,
                CONF_TOKEN_EXPIRY: expiry,
                CONF_EMAIL:        email,
            },
        )
        await hass.config_entries.async_reload(entry.entry_id)
        _LOGGER.info("Prime Polaris re-authenticated via service: %s", email)

    async def _clear_cook_inputs(call: ServiceCall) -> None:
        entry = _resolve_entry(hass, call.data.get("entry_id"))
        coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if coordinator is None:
            raise HomeAssistantError("Coordinator not available")

        tracker = getattr(coordinator, "session_tracker", None)
        if tracker is None:
            return

        for purpose in ("notes", "protein", "weight_lb"):
            ent = tracker._texts.get(purpose)
            if ent is not None:
                try:
                    await ent.async_set_value("")
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Could not clear %s: %s", purpose, err)

    hass.services.async_register(
        DOMAIN, SERVICE_REQUEST_OTP, _request_otp, schema=REQUEST_OTP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_VERIFY_OTP, _verify_otp, schema=VERIFY_OTP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_COOK_INPUTS, _clear_cook_inputs,
        schema=CLEAR_COOK_INPUTS_SCHEMA,
    )
