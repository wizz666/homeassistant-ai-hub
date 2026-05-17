"""AI Hub – Centralized API key management for Home Assistant."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_keys(hass: HomeAssistant) -> dict:
    """Return AI Hub keys from the config entry.

    Other integrations can call this to retrieve keys without
    reading from input_text or any other frontend-visible entity::

        from homeassistant.loader import async_get_integration
        if hass.data.get("ai_hub"):
            from custom_components.ai_hub import get_keys
            keys = get_keys(hass)
    """
    for entry in hass.config_entries.async_entries(DOMAIN):
        return {**entry.data, **entry.options}
    return {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AI Hub from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry
    entry.async_on_unload(entry.add_update_listener(_on_options_update))
    configured = sum(1 for v in {**entry.data, **entry.options}.values() if v)
    _LOGGER.info("AI Hub: ready with %d configured provider(s)", configured)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload AI Hub config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


async def _on_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — keys are re-read live from the config entry."""
    _LOGGER.debug("AI Hub: options updated")
