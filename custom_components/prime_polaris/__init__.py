"""
/* ============================================================
 * __init__.py — Prime Polaris Integration Entry Point
 * ============================================================
 *
 * Handles integration setup, platform forwarding, and teardown.
 * Creates one coordinator per config entry (one per grill) and
 * stores it in hass.data for platform entities to access.
 *
 * Platforms loaded: climate, sensor, switch, number
 * ============================================================
 */
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PrimePolarisApiClient
from .const import CONF_TOKEN, DOMAIN, OPT_FCM_ENABLED
from .coordinator import PrimePolarisCoordinator
from .fcm_listener import PrimePolarisFcmListener
from .frontend import async_register_card
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)

# Platforms this integration provides entities for
PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.TEXT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Prime Polaris from a config entry.

    Called by HA when the integration is loaded. Creates the
    API client, injects the stored token, creates the coordinator,
    performs an initial data fetch, and forwards setup to each
    platform.
    """
    # Register integration-wide services (idempotent — safe across
    # multiple entries). The Lovelace card calls these for re-auth
    # and per-cook resets without dragging users through Settings.
    async_register_services(hass)

    # Register the bundled Lovelace card. Serves the JS as a static
    # asset and adds it to Lovelace resources automatically — users
    # don't need to manually add a custom: resource.
    await async_register_card(hass)

    session = async_get_clientsession(hass)
    client = PrimePolarisApiClient(session)
    client.set_token(entry.data[CONF_TOKEN])

    coordinator = PrimePolarisCoordinator(hass, client, entry)

    # Perform initial fetch — raises ConfigEntryNotReady if it fails
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in hass.data keyed by domain + entry ID
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward setup to each platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Optional FCM listener — opt-in via options flow
    if entry.options.get(OPT_FCM_ENABLED):
        listener = PrimePolarisFcmListener(hass, entry, coordinator)
        coordinator.fcm_listener = listener
        await listener.async_start()

    # Reload entry when options change so FCM state follows the toggle
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the entry when options change (e.g. FCM toggled)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Called by HA when the integration is removed or reloaded.
    Unloads all platform entities, stops the FCM listener if
    it was running, and cleans up coordinator state.
    """
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    # Stop FCM listener first so it doesn't dispatch to a dying coordinator
    if coordinator is not None:
        listener = getattr(coordinator, "fcm_listener", None)
        if listener is not None:
            await listener.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
