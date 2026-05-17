"""Config flow for AI Hub."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_GROQ_KEY, CONF_ANTHROPIC_KEY, CONF_OPENAI_KEY,
    CONF_OPENROUTER_KEY, CONF_OPENROUTER_MODEL,
    CONF_OLLAMA_URL, CONF_OLLAMA_MODEL,
    DEFAULT_OPENROUTER_MODEL, DEFAULT_OLLAMA_URL, DEFAULT_OLLAMA_MODEL,
)


def _key_schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_GROQ_KEY,         default=defaults.get(CONF_GROQ_KEY, "")): str,
        vol.Optional(CONF_ANTHROPIC_KEY,    default=defaults.get(CONF_ANTHROPIC_KEY, "")): str,
        vol.Optional(CONF_OPENAI_KEY,       default=defaults.get(CONF_OPENAI_KEY, "")): str,
        vol.Optional(CONF_OPENROUTER_KEY,   default=defaults.get(CONF_OPENROUTER_KEY, "")): str,
        vol.Optional(CONF_OPENROUTER_MODEL, default=defaults.get(CONF_OPENROUTER_MODEL, DEFAULT_OPENROUTER_MODEL)): str,
        vol.Optional(CONF_OLLAMA_URL,       default=defaults.get(CONF_OLLAMA_URL, DEFAULT_OLLAMA_URL)): str,
        vol.Optional(CONF_OLLAMA_MODEL,     default=defaults.get(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL)): str,
    })


class AIHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for AI Hub."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            return self.async_create_entry(title="AI Hub", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_key_schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AIHubOptionsFlow(config_entry)


class AIHubOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for AI Hub."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        current = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_key_schema(current),
        )
