"""
/* ============================================================
 * frontend.py — Bundled Lovelace Card Registration
 * ============================================================
 *
 * The integration ships its own Lovelace card. On setup we:
 *   1. Serve the bundled JS file as a static asset under
 *      /prime_polaris_card/ha-prime-polaris-card.js
 *   2. Register that URL as a Lovelace resource so HA's frontend
 *      loads it on every dashboard automatically — no manual
 *      "add resource" step required by the user.
 *
 * Idempotent: re-registering across reloads is fine. The resource
 * URL carries a ?v= query param matching the card version so the
 * browser picks up updates after an integration upgrade without
 * stale-cache headaches.
 * ============================================================
 */
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "ha-prime-polaris-card.js"
CARD_URL_PATH = f"/{DOMAIN}_card/{CARD_FILENAME}"
CARD_VERSION  = "0.4.2"  # bump alongside src/constants.js → CARD_VERSION


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled card JS and add it to Lovelace resources.

    Safe to call repeatedly across reloads; static-path registration
    is idempotent at the HA layer, and we de-dupe the Lovelace
    resource by URL prefix.
    """
    card_path = Path(__file__).parent / "www" / CARD_FILENAME
    if not card_path.exists():
        _LOGGER.warning(
            "Bundled card JS not found at %s — skipping registration", card_path,
        )
        return

    # Serve the file as a static asset
    try:
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path=CARD_URL_PATH,
                path=str(card_path),
                cache_headers=False,
            )
        ])
    except Exception as err:  # noqa: BLE001
        # Already-registered raises on some HA versions; not fatal.
        _LOGGER.debug("Static path registration: %s", err)

    # Register as a Lovelace resource so users don't have to
    await _async_register_lovelace_resource(hass)


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Add (or update) the card as a Lovelace resource.

    Skips silently in YAML-mode dashboards (resources are config-driven
    there; users add the URL themselves).
    """
    full_url = f"{CARD_URL_PATH}?v={CARD_VERSION}"

    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        _LOGGER.debug("Lovelace not loaded yet; skipping resource registration")
        return

    resources = getattr(lovelace, "resources", None)
    if resources is None:
        _LOGGER.debug("Lovelace resources unavailable (YAML mode?); skipping")
        return

    # Trigger lazy load on first use
    if not getattr(resources, "loaded", True):
        try:
            await resources.async_load()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not load resources collection: %s", err)
            return

    # Already registered? Update version if outdated; else create.
    items = resources.async_items() if callable(getattr(resources, "async_items", None)) else []
    existing = next(
        (i for i in items if isinstance(i, dict)
         and i.get("url", "").split("?", 1)[0] == CARD_URL_PATH),
        None,
    )

    if existing is not None:
        if existing.get("url") != full_url:
            try:
                await resources.async_update_item(
                    existing["id"], {"url": full_url, "res_type": "module"},
                )
                _LOGGER.info("Updated Lovelace card resource → v%s", CARD_VERSION)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Could not update Lovelace resource: %s", err)
        return

    try:
        await resources.async_create_item(
            {"url": full_url, "res_type": "module"},
        )
        _LOGGER.info("Registered Lovelace card resource at %s", full_url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not create Lovelace resource: %s", err)
