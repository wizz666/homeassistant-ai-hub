# Home Assistant AI Hub

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support_this_project-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/wizz666)

**[🇸🇪 Svenska → README.sv.md](README.sv.md)**

Centralised AI provider management for Home Assistant. Enter your API keys once — all integrations use them automatically. Supports cloud providers (Groq, Anthropic, OpenAI) and **local AI via Ollama** — no internet required.

---

## The problem this solves

Without AI Hub, each integration has its own API key fields:
```
OpenF1          → input_text.f1_ai_api_key
Grocery Tracker → input_text.grocery_api_key_groq
Chronicle AI    → input_text.chronicle_ai_api_key
...
```

When a key expires you update it in three places. Want to switch from Groq to Anthropic? Change it everywhere.

**With AI Hub:**
```
All integrations → input_text.ai_hub_groq_key
                   input_text.ai_hub_anthropic_key
                   input_text.ai_hub_openai_key
                   input_text.ai_hub_ollama_url   ← local AI, no key needed
                   input_select.ai_hub_default_provider
```
Update once. Done.

---

## Features

- **One place for all API keys** — Groq, Anthropic, OpenAI
- **Local AI with Ollama** — run AI on your own server, no API key, no internet
- **Provider switching** — change the default provider and all integrations follow
- **Auto-routing** — `auto` mode tries Ollama → Groq → Anthropic → OpenAI → ha_ai_task
- **Built-in chat interface** — dedicated Ollama chat tab in the dashboard
- **Built-in test interface** — type a prompt, send it, see the response
- **Usage statistics** — total calls and calls per provider per session
- **Status sensor** — `ready / busy / error` with metadata
- **Works with any pyscript integration** — call `pyscript.ai_hub_ask` from any automation

---

## Supported providers

| Provider | Cost | Model | Notes |
|----------|------|-------|-------|
| **Ollama** | Free | Any model you install | Local, private, no internet required |
| **Groq** | Free tier | llama-3.3-70b-versatile | Recommended cloud option |
| **Anthropic** | ~$0.25/1M tokens | claude-haiku-4-5 | Fast and high quality |
| **OpenAI** | ~$0.15/1M tokens | gpt-4o-mini | Widely supported |
| **ha_ai_task** | Free | Depends on HA setup | Uses whatever AI is configured in HA |

---

## Integrations that use AI Hub

- 🏎️ [OpenF1](https://github.com/wizz666/homeassistant-openf1) — live race commentary + session recap
- 🛒 [Grocery Tracker](https://github.com/wizz666/homeassistant-grocery-tracker) — recipe suggestions
- 📖 [Chronicle AI](https://github.com/wizz666/homeassistant-chronicle-ai) — home Q&A + energy coach

---

## Requirements

- Home Assistant 2024.1+
- [Pyscript](https://github.com/custom-components/pyscript) (via HACS)
- For Ollama: a separate machine or server with at least 4 GB RAM (see below)

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

Go to **AI Hub → Keys** and enter at least one API key, or configure Ollama for a fully local setup.

**Get a free Groq key** (recommended cloud option):
1. Go to [console.groq.com](https://console.groq.com)
2. Create a free account
3. Go to **API Keys** → **Create API Key**
4. Paste into **AI Hub → Keys → Groq**

---

## Local AI with Ollama (no API key, no internet)

Ollama lets you run large language models locally on any machine in your network. AI Hub connects to it over your local network — no data ever leaves your home.

### System requirements

| RAM | What fits |
|-----|-----------|
| 4 GB | phi3:mini, llama3.2:1b, gemma2:2b |
| 8 GB | llama3.2:3b (default), mistral:7b |
| 16 GB+ | llama3.1:8b, llama3.1:70b (quantised) |

> A Raspberry Pi 5 (8 GB), an old laptop, a NAS, or any always-on Linux machine works great.

### Step 1 — Install Ollama on the server

**Linux / Raspberry Pi:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:** Download the installer from [ollama.com](https://ollama.com)

After installation, Ollama starts automatically as a service on port `11434`.

### Step 2 — Allow network access (Linux)

By default Ollama only listens on localhost. To allow Home Assistant to reach it, add an environment variable:

```bash
sudo systemctl edit ollama
```

In the editor that opens, add:
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

Then restart the service:
```bash
sudo systemctl restart ollama
```

**Verify it's accessible** from your HA machine:
```bash
curl http://<server-ip>:11434/api/tags
```
You should see a JSON response.

### Step 3 — Pull a model

```bash
# Recommended for most machines (2–4 GB RAM)
ollama pull phi3

# Lightweight option (~1 GB RAM)
ollama pull llama3.2:1b

# Higher quality, needs 8+ GB RAM
ollama pull llama3.1:8b
```

List installed models:
```bash
ollama list
```

### Step 4 — Configure AI Hub

Go to **AI Hub → Keys** and fill in:

| Field | Value |
|-------|-------|
| **Ollama Server URL** | `http://<server-ip>:11434` |
| **Ollama Model** | `phi3:latest` (or whichever you pulled) |

Go to **AI Hub → Keys → Default provider** and set it to `ollama`.

### Step 5 — Test it

Go to **AI Hub → Ollama** tab. Type a question and click **Send**. The response appears below — entirely locally, no internet.

### Troubleshooting Ollama

| Error | Cause | Fix |
|-------|-------|-----|
| `connection refused` | Ollama not listening on network | Add `OLLAMA_HOST=0.0.0.0` (see Step 2) |
| `HTTP 500: model requires X GiB` | Not enough RAM | Use a smaller model (`ollama pull llama3.2:1b`) |
| `model not found` | Wrong model name | Run `ollama list` and copy the exact name |
| Slow responses | Normal for first run | Model is loading into memory, subsequent calls are faster |

---

## Usage

### From automations or scripts

```yaml
service: pyscript.ai_hub_ask
data:
  prompt: "What should I cook tonight with chicken and pasta?"
  provider: ollama      # or groq, anthropic, openai, auto
  max_tokens: 200       # optional
  caller: "my_automation"  # optional, shows in statistics
```

The response is written to `sensor.ai_hub_last_response`.

### From pyscript

```python
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
| `sensor.ai_hub_providers` | Number of configured providers — attrs: groq, anthropic, openai, ollama, ha_ai_task |

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
