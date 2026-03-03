# Home Assistant AI Hub

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Stöd_projektet-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/wizz666)

**[🇬🇧 English → README.md](README.md)**

Centraliserad AI-leverantörshantering för Home Assistant. Ange dina API-nycklar en gång — alla integrationer använder dem automatiskt. Stöder molnleverantörer (Groq, Anthropic, OpenAI) och **lokal AI via Ollama** — inget internet krävs.

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
                     input_text.ai_hub_ollama_url   ← lokal AI, ingen nyckel
                     input_select.ai_hub_default_provider
```
Uppdatera en gång. Klart.

---

## Funktioner

- **En plats för alla API-nycklar** — Groq, Anthropic, OpenAI
- **Lokal AI med Ollama** — kör AI på din egen server, ingen API-nyckel, inget internet
- **Leverantörsbyte** — ändra standardleverantören och alla integrationer följer med
- **Auto-routing** — `auto`-läget provar Ollama → Groq → Anthropic → OpenAI → ha_ai_task
- **Inbyggt chattgränssnitt** — dedikerad Ollama-flik i dashboarden
- **Inbyggt testgränssnitt** — skriv en prompt, skicka, se svaret
- **Användningsstatistik** — totala anrop och anrop per leverantör
- **Statussensor** — `ready / busy / error` med metadata
- **Fungerar med alla pyscript-integrationer** — anropa `pyscript.ai_hub_ask` från vilken automation som helst

---

## Leverantörer som stöds

| Leverantör | Kostnad | Modell | Kommentar |
|------------|---------|--------|-----------|
| **Ollama** | Gratis | Valfri modell du installerar | Lokalt, privat, inget internet |
| **Groq** | Gratis tier | llama-3.3-70b-versatile | Rekommenderas som molnalternativ |
| **Anthropic** | ~$0,25/1M tokens | claude-haiku-4-5 | Snabb och hög kvalitet |
| **OpenAI** | ~$0,15/1M tokens | gpt-4o-mini | Brett stöd |
| **ha_ai_task** | Gratis | Beror på HA-setup | Använder den AI som är konfigurerad i HA |

---

## Integrationer som använder AI Hub

- 🏎️ [OpenF1](https://github.com/wizz666/homeassistant-openf1) — live-rackommentar + sessionreferat
- 🛒 [Grocery Tracker](https://github.com/wizz666/homeassistant-grocery-tracker) — receptförslag
- 📖 [Chronicle AI](https://github.com/wizz666/homeassistant-chronicle-ai) — hem-Q&A + Energi-Coach

---

## Krav

- Home Assistant 2024.1+
- [Pyscript](https://github.com/custom-components/pyscript) (via HACS)
- För Ollama: en separat maskin eller server med minst 4 GB RAM (se nedan)

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

Gå till **AI Hub → Nycklar** och ange minst en API-nyckel, eller konfigurera Ollama för en helt lokal uppsättning.

**Skaffa en gratis Groq-nyckel** (rekommenderas som molnalternativ):
1. Gå till [console.groq.com](https://console.groq.com)
2. Skapa ett gratis konto
3. Gå till **API Keys** → **Create API Key**
4. Klistra in under **AI Hub → Nycklar → Groq**

---

## Lokal AI med Ollama (ingen API-nyckel, inget internet)

Ollama låter dig köra stora språkmodeller lokalt på valfri maskin i ditt nätverk. AI Hub ansluter till den via ditt lokala nätverk — ingen data lämnar hemmet.

### Systemkrav

| RAM | Vad som passar |
|-----|----------------|
| 4 GB | phi3:mini, llama3.2:1b, gemma2:2b |
| 8 GB | llama3.2:3b, mistral:7b |
| 16 GB+ | llama3.1:8b, llama3.1:70b (kvantiserad) |

> Raspberry Pi 5 (8 GB), en gammal laptop, en NAS, eller vilken alltid-på Linux-maskin som helst fungerar utmärkt.

### Steg 1 — Installera Ollama på servern

**Linux / Raspberry Pi:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:** Ladda ner installationsfilen från [ollama.com](https://ollama.com)

Efter installation startar Ollama automatiskt som en tjänst på port `11434`.

### Steg 2 — Tillåt nätverksåtkomst (Linux)

Som standard lyssnar Ollama bara på localhost. För att Home Assistant ska kunna nå den, lägg till en miljövariabel:

```bash
sudo systemctl edit ollama
```

I editorn som öppnas, lägg till:
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

Starta om tjänsten:
```bash
sudo systemctl restart ollama
```

**Verifiera att den är nåbar** från din HA-maskin:
```bash
curl http://<server-ip>:11434/api/tags
```
Du ska få ett JSON-svar.

### Steg 3 — Hämta en modell

```bash
# Rekommenderas för de flesta maskiner (2–4 GB RAM)
ollama pull phi3

# Lättviktsalternativ (~1 GB RAM)
ollama pull llama3.2:1b

# Högre kvalitet, kräver 8+ GB RAM
ollama pull llama3.1:8b
```

Lista installerade modeller:
```bash
ollama list
```

### Steg 4 — Konfigurera AI Hub

Gå till **AI Hub → Nycklar** och fyll i:

| Fält | Värde |
|------|-------|
| **Ollama Server-URL** | `http://<server-ip>:11434` |
| **Ollama Modell** | `phi3:latest` (eller den du hämtade) |

Gå till **AI Hub → Nycklar → Standardleverantör** och välj `ollama`.

### Steg 5 — Testa det

Gå till fliken **AI Hub → Ollama**. Skriv en fråga och klicka **Skicka till Ollama**. Svaret visas nedanför — helt lokalt, inget internet.

### Felsökning Ollama

| Fel | Orsak | Lösning |
|-----|-------|---------|
| `connection refused` | Ollama lyssnar inte på nätverket | Lägg till `OLLAMA_HOST=0.0.0.0` (se Steg 2) |
| `HTTP 500: model requires X GiB` | För lite RAM | Använd en mindre modell (`ollama pull llama3.2:1b`) |
| `model not found` | Fel modellnamn | Kör `ollama list` och kopiera det exakta namnet |
| Långsamma svar | Normalt vid första anropet | Modellen laddas in i minnet, efterföljande anrop är snabbare |

---

## Användning

### Från automationer eller skript

```yaml
service: pyscript.ai_hub_ask
data:
  prompt: "Vad ska jag laga till middag med kyckling och pasta?"
  provider: ollama        # eller groq, anthropic, openai, auto
  max_tokens: 200         # valfritt
  caller: "min_automation"  # valfritt, syns i statistiken
```

Svaret skrivs till `sensor.ai_hub_last_response`.

### Från pyscript

```python
await pyscript.ai_hub_ask(
    prompt="Skriv en mening om Formel 1 på svenska.",
    caller="openf1"
)
# Svar tillgängligt på:
# state.get("sensor.ai_hub_last_response")
```

### Testgränssnitt

Gå till **AI Hub → Testa**, skriv en prompt, klicka **Skicka**. Svaret visas nedanför.

---

## Sensorer

| Sensor | Beskrivning |
|--------|-------------|
| `sensor.ai_hub_status` | `ready` / `busy` / `error` — attrs: provider, caller, total_calls |
| `sensor.ai_hub_last_response` | Senaste AI-svar — attrs: prompt, provider_used, timestamp, caller |
| `sensor.ai_hub_providers` | Antal konfigurerade leverantörer — attrs: groq, anthropic, openai, ollama, ha_ai_task |

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
