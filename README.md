# AI Hub for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/wizz666/homeassistant-ai-hub.svg)](https://github.com/wizz666/homeassistant-ai-hub/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support_this_project-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/wizz666)

**AI Hub** is a centralized API key manager for Home Assistant. Enter your AI service keys once — AI Hub stores them securely and makes them available to all AI-powered integrations automatically.

## Features

- **One place for all your AI keys** — Groq, Anthropic, OpenAI, OpenRouter, Ollama
- **Secure storage** — Keys stored in HA config entries, not in YAML files
- **Auto-sync** — Keys are automatically synced to `input_text` helper entities used by other integrations
- **Config flow UI** — Set up and update keys through the Home Assistant interface
- **Migration-friendly** — Detects and imports existing keys from `input_text` entities

## Supported AI Providers

| Provider | Free Tier | Notes |
|---|---|---|
| [Groq](https://console.groq.com) | ✅ Yes | Fast inference, Llama/Mixtral models |
| [Anthropic](https://console.anthropic.com) | ❌ No | Claude models |
| [OpenAI](https://platform.openai.com) | ❌ No | GPT models |
| [OpenRouter](https://openrouter.ai) | ✅ Some | 300+ models, free tier available |
| [Ollama](http://localhost:11434) | ✅ Local | Run models locally |

## Installation

### Via HACS (recommended)

1. Add this repository as a **Custom Repository** in HACS:
   - HACS → Integrations → ⋮ → Custom repositories
   - URL: `https://github.com/wizz666/homeassistant-ai-hub`
   - Category: **Integration**
2. Search for **AI Hub** and install
3. Restart Home Assistant
4. Go to **Settings → Integrations → + Add Integration → AI Hub**

### Manual

1. Copy `custom_components/ai_hub/` to your HA `custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings → Integrations → + Add Integration → AI Hub**

## Configuration

After installation, go to **Settings → Integrations → AI Hub → Configure** to enter your API keys. All fields are optional — only fill in the services you use.

The integration creates the following `input_text` entities that other integrations can read:

| Entity | Description |
|---|---|
| `input_text.ai_hub_groq_key` | Groq API key |
| `input_text.ai_hub_anthropic_key` | Anthropic API key |
| `input_text.ai_hub_openai_key` | OpenAI API key |
| `input_text.ai_hub_openrouter_key` | OpenRouter API key |
| `input_text.ai_hub_openrouter_model` | OpenRouter default model |
| `input_text.ai_hub_ollama_url` | Ollama server URL |
| `input_text.ai_hub_ollama_model` | Ollama default model |

## For Integration Developers

Read AI Hub keys in your pyscript or custom component:

```python
# pyscript
groq_key = state.get("input_text.ai_hub_groq_key") or ""

# custom_component
state = hass.states.get("input_text.ai_hub_groq_key")
groq_key = state.state if state and state.state not in ("", "unknown", "unavailable") else ""
```

## Requirements

- Home Assistant 2024.1.0 or newer
- API keys for the AI services you want to use (all optional)

## License

MIT License — see [LICENSE](LICENSE)
