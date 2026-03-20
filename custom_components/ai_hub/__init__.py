"""AI Hub – Centralized API key management for Home Assistant."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

from .const import DOMAIN, KEY_TO_ENTITY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AI Hub from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry

    async def _sync(_event=None):
        await _write_keys(hass, entry)

    if hass.is_running:
        await _sync()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _sync)

    entry.async_on_unload(entry.add_update_listener(_on_options_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload AI Hub config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


async def _on_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Sync keys when options are updated."""
    await _write_keys(hass, entry)


async def _write_keys(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Write config entry keys to input_text entities."""
    data = {**entry.data, **entry.options}

    for conf_key, entity_id in KEY_TO_ENTITY.items():
        value = data.get(conf_key, "")
        if not value:
            continue

        # Try input_text.set_value first (entity exists via packages yaml)
        entity_state = hass.states.get(entity_id)
        if entity_state is not None:
            try:
                await hass.services.async_call(
                    "input_text", "set_value",
                    {"entity_id": entity_id, "value": value},
                    blocking=True,
                )
                continue
            except Exception as err:
                _LOGGER.debug("input_text.set_value failed for %s: %s", entity_id, err)

        # Fallback: set state directly (for users without packages yaml)
        friendly = entity_id.split(".")[1].replace("_", " ").title()
        hass.states.async_set(entity_id, value, {"friendly_name": friendly})
        _LOGGER.debug("AI Hub: set state %s directly", entity_id)

    _LOGGER.info("AI Hub: keys synced to input_text entities")
