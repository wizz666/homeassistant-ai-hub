# Home Assistant AI Hub

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Stöd_projektet-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/wizz666)

**[🇬🇧 English → README.md](README.md)**

Centraliserad AI-leverantörshantering för Home Assistant. Ange dina API-nycklar en gång — alla integrationer använder dem automatiskt.

---

## Problemet som löses

Utan AI Hub har varje integration egna API-nyckelfält:
```
OpenF1          → input_text.f1_ai_api_key
Grocery Tracker → input_text.grocery_api_key_groq
Chronicle AI    → input_text.chronicle_ai_api_key
...
```

När en nyckel går ut måste du uppdatera den på tre ställen. Vill du byta från Groq till Anthropic? Ändra överallt.

**Med AI Hub:**
```
Alla integrationer → input_text.ai_hub_groq_key
                     input_text.ai_hub_anthropic_key
                     input_text.ai_hub_openai_key
                     input_select.ai_hub_default_provider
```
Uppdatera en gång. Klart.

---

## Funktioner

- **En plats för alla API-nycklar** — Groq, Anthropic, OpenAI
- **Leverantörsbyte** — ändra standardleverantören och alla integrationer följer med
- **Auto-routing** — `auto`-läget provar Groq → Anthropic → OpenAI → ha_ai_task
- **Inbyggt testgränssnitt** — skriv en prompt, skicka, se svaret
- **Användningsstatistik** — totala anrop och anrop per leverantör
- **Statussensor** — `ready / busy / error` med metadata
- **Fungerar med alla pyscript-integrationer** — anropa `pyscript.ai_hub_ask` från vilken automation som helst

## Leverantörer som stöds

| Leverantör | Kostnad | Modell | Kommentar |
|------------|---------|-------|-----------|
| **Groq** | Gratis tier | llama-3.3-70b-versatile | Rekommenderas för att komma igång |
| **Anthropic** | ~$0,25/1M tokens | claude-haiku-4-5 | Snabb och hög kvalitet |
| **OpenAI** | ~$0,15/1M tokens | gpt-4o-mini | Brett stöd |
| **ha_ai_task** | Gratis | Beror på HA-setup | Använder den AI som är konfigurerad i HA |

## Integrationer som använder AI Hub

- 🏎️ [OpenF1](https://github.com/wizz666/homeassistant-openf1) — live-rackommentar + sessionreferat
- 🛒 [Grocery Tracker](https://github.com/wizz666/homeassistant-grocery-tracker) — receptförslag
- 📖 [Chronicle AI](https://github.com/wizz666/homeassistant-chronicle-ai) — hem-Q&A + Energi-Coach

---

## Krav

- Home Assistant 2024.1+
- [Pyscript](https://github.com/custom-components/pyscript) (via HACS)

---

## Installation

### 1. Installera Pyscript

Installera via HACS. Lägg till i `configuration.yaml`:
```yaml
pyscript:
  allow_all_imports: true
  hass_is_global: true
```

### 2. Kopiera filer

| Fil | Destination |
|-----|------------|
| `ai_hub.py` | `config/pyscript/ai_hub.py` |
| `ai_hub_package.yaml` | `config/packages/ai_hub_package.yaml` |
| `ai_hub_dashboard.yaml` | `config/dashboards/ai_hub_dashboard.yaml` |

Aktivera packages i `configuration.yaml` om det inte redan är gjort:
```yaml
homeassistant:
  packages: !include_dir_named packages
```

### 3. Registrera dashboarden

Lägg till i `configuration.yaml`:
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

### 4. Starta om Home Assistant

Efter omstart visas **AI Hub** i sidofältet.

### 5. Ange API-nycklar

Gå till **AI Hub → Nycklar** och ange minst en API-nyckel.

**Skaffa en gratis Groq-nyckel** (rekommenderas):
1. Gå till [console.groq.com](https://console.groq.com)
2. Skapa ett gratis konto
3. Gå till **API Keys** → **Create API Key**
4. Kopiera och klistra in under `AI Hub → Nycklar → Groq`

---

## Användning

### Från automationer eller skript

```yaml
service: pyscript.ai_hub_ask
data:
  prompt: "Vad ska jag laga till middag med kyckling och pasta?"
  provider: groq          # valfritt, använder standard om utelämnat
  max_tokens: 200         # valfritt
  caller: "min_automation"  # valfritt, syns i statistiken
```

Svaret skrivs till `sensor.ai_hub_last_response`.

### Testgränssnitt

Gå till **AI Hub → Testa**, skriv en prompt, klicka **Skicka**. Svaret visas nedanför.

---

## Sensorer

| Sensor | Beskrivning |
|--------|-------------|
| `sensor.ai_hub_status` | `ready` / `busy` / `error` — attrs: provider, caller, total_calls |
| `sensor.ai_hub_last_response` | Senaste AI-svar — attrs: prompt, provider_used, timestamp, caller |
| `sensor.ai_hub_providers` | Antal konfigurerade leverantörer — attrs: groq, anthropic, openai, ha_ai_task (bool) |

---

## För integrationsbyggare

Läser du nycklar i en egen pyscript-integration? Gör så här:

```python
def _get_ai_key(provider):
    """AI Hub har prioritet, sedan egna fallback-nycklar."""
    hub_entities = {
        "groq":      "input_text.ai_hub_groq_key",
        "anthropic": "input_text.ai_hub_anthropic_key",
        "openai":    "input_text.ai_hub_openai_key",
    }
    entity = hub_entities.get(provider, "")
    key = (state.get(entity) or "").strip() if entity else ""
    if key and key not in ("unknown", "none", "unavailable"):
        return key
    # Fallback till integrationsspecifik nyckel:
    return (state.get("input_text.min_integration_api_key") or "").strip()
```

Läs standardleverantören:
```python
provider = state.get("input_select.ai_hub_default_provider") or "auto"
```

---

## Stöd projektet

Gillar du det här projektet? En kopp kaffe uppskattas ☕

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/wizz666)

## Licens

MIT — se [LICENSE](LICENSE)
