# Home Assistant AI Hub

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support_this_project-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/wizz666)

**[🇸🇪 Svenska → README.sv.md](README.sv.md)**

Centralised AI provider management for Home Assistant. Enter your API keys once — all integrations use them automatically.

---

## The problem this solves

Without AI Hub, each integration has its own API key fields:
```
OpenF1        → input_text.f1_ai_api_key
Grocery Tracker → input_text.grocery_api_key_groq
Chronicle AI  → input_text.chronicle_ai_api_key
...
```

When a key expires you update it in three places. Want to switch from Groq to Anthropic? Change it everywhere.

**With AI Hub:**
```
All integrations → input_text.ai_hub_groq_key
                   input_text.ai_hub_anthropic_key
                   input_text.ai_hub_openai_key
                   input_select.ai_hub_default_provider
```
Update once. Done.

---

## Features

- **One place for all API keys** — Groq, Anthropic, OpenAI
- **Provider switching** — change the default provider and all integrations follow
- **Auto-routing** — `auto` mode tries Groq → Anthropic → OpenAI → ha_ai_task
- **Built-in test interface** — type a prompt, send it, see the response
- **Usage statistics** — total calls and calls per provider per session
- **Status sensor** — `ready / busy / error` with metadata
- **Works with any pyscript integration** — call `pyscript.ai_hub_ask` from any automation

## Supported providers

| Provider | Cost | Model | Notes |
|----------|------|-------|-------|
| **Groq** | Free tier | llama-3.3-70b-versatile | Recommended for getting started |
| **Anthropic** | ~$0.25/1M tokens | claude-haiku-4-5 | Fast and high quality |
| **OpenAI** | ~$0.15/1M tokens | gpt-4o-mini | Widely supported |
| **ha_ai_task** | Free | Depends on HA setup | Uses whatever AI is configured in HA |

## Integrations that use AI Hub

- 🏎️ [OpenF1](https://github.com/wizz666/homeassistant-openf1) — live race commentary + session recap
- 🛒 [Grocery Tracker](https://github.com/wizz666/homeassistant-grocery-tracker) — recipe suggestions
- 📖 [Chronicle AI](https://github.com/wizz666/homeassistant-chronicle-ai) — home Q&A + energy coach

---

## Requirements

- Home Assistant 2024.1+
- [Pyscript](https://github.com/custom-components/pyscript) (via HACS)

---

## Installation

### 1. Install Pyscript

Install via HACS. Add to `configuration.yaml`:
```yaml
pyscript:
  allow_all_imports: true
  hass_is_global: true
```

### 2. Copy files

| File | Destination |
|------|------------|
| `ai_hub.py` | `config/pyscript/ai_hub.py` |
| `ai_hub_package.yaml` | `config/packages/ai_hub_package.yaml` |
| `ai_hub_dashboard.yaml` | `config/dashboards/ai_hub_dashboard.yaml` |

Enable packages in `configuration.yaml` if not already:
```yaml
homeassistant:
  packages: !include_dir_named packages
```

### 3. Register the dashboard

Add to `configuration.yaml`:
```yaml
lovelace:
  dashboards:
    ai-hub:
      mode: yaml
      title: "AI Hub"
      icon: mdi:robot
      show_in_sidebar: true
      filename: dashboards/ai_hub_dashboard.yaml
```

### 4. Restart Home Assistant

After restart, **AI Hub** appears in the sidebar.

### 5. Enter your API keys

Go to **AI Hub → Nycklar** and enter at least one API key.

**Get a free Groq key** (recommended):
1. Go to [console.groq.com](https://console.groq.com)
2. Create a free account
3. Go to **API Keys** → **Create API Key**
4. Copy and paste into `AI Hub → Nycklar → Groq`

---

## Usage

### From automations or scripts

```yaml
service: pyscript.ai_hub_ask
data:
  prompt: "What should I cook tonight with chicken and pasta?"
  provider: groq        # optional, uses default if omitted
  max_tokens: 200       # optional
  caller: "my_automation"  # optional, shows in statistics
```

The response is written to `sensor.ai_hub_last_response`.

### From pyscript

```python
# Call the service (non-blocking, result goes to sensor)
await pyscript.ai_hub_ask(
    prompt="Write a sentence about F1 in Swedish.",
    caller="openf1"
)
# Response available at:
# state.get("sensor.ai_hub_last_response")
```

### Test from dashboard

Go to **AI Hub → Testa**, type a prompt, click **Skicka**. The response appears below.

---

## Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.ai_hub_status` | `ready` / `busy` / `error` — attrs: provider, caller, total_calls |
| `sensor.ai_hub_last_response` | Latest AI response text — attrs: prompt, provider_used, timestamp, caller |
| `sensor.ai_hub_providers` | Number of configured providers — attrs: groq, anthropic, openai, ha_ai_task (booleans) |

---

## For integration developers

If you're building a pyscript integration that needs AI, read keys like this:

```python
def _get_ai_key(provider):
    """AI Hub first, then own fallback key."""
    hub_entities = {
        "groq":      "input_text.ai_hub_groq_key",
        "anthropic": "input_text.ai_hub_anthropic_key",
        "openai":    "input_text.ai_hub_openai_key",
    }
    entity = hub_entities.get(provider, "")
    key = (state.get(entity) or "").strip() if entity else ""
    if key and key not in ("unknown", "none", "unavailable"):
        return key
    # Fallback to your own integration's key field:
    return (state.get("input_text.my_integration_api_key") or "").strip()
```

Read the default provider:
```python
provider = state.get("input_select.ai_hub_default_provider") or "auto"
```

---

## Support

If you find this useful, a coffee is always appreciated ☕

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/wizz666)

## License

MIT — see [LICENSE](LICENSE)
