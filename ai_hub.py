"""
AI Hub – Centraliserad AI-leverantörshantering  v1.2
=====================================================
Hanterar API-nycklar och routing för alla AI-integrationer i HA.

API-nycklar konfigureras en gång här och används av:
  - OpenF1 (live-kommentar + sessionreferat)
  - Grocery Tracker (receptförslag)
  - Chronicle AI (Q&A + Energi-Coach)
  - ... och framtida integrationer

Konfigurerbara entiteter (skapas av packages/ai_hub.yaml):
  input_text.ai_hub_groq_key          – Groq API-nyckel (gratis på groq.com)
  input_text.ai_hub_anthropic_key     – Anthropic API-nyckel (betalt, antropic.com)
  input_text.ai_hub_openai_key        – OpenAI API-nyckel (betalt, platform.openai.com)
  input_text.ai_hub_ollama_url         – Ollama server-URL (standard: http://192.168.2.116:11434)
  input_text.ai_hub_ollama_model       – Ollama-modell att använda (t.ex. llama3.2, mistral)
  input_select.ai_hub_default_provider – Vilken leverantör som används (auto/ollama/groq/anthropic/openai/ha_ai_task)
  input_select.ai_hub_groq_model      – Vilken Groq-modell som används för text

Groq-modeller (väljs i input_select.ai_hub_groq_model):
  llama-3.3-70b-versatile  → Standard. Bäst kvalitet, ~14 400 anrop/dygn (gratis)
  llama-3.1-8b-instant     → Snabb och lätt. Bra för enkla frågor, ~14 400 anrop/dygn
  llama-3.2-3b-preview     → Minst/snabbast. Mycket hög dagsgräns.
  mixtral-8x7b-32768       → Bra för långa texter (32k kontext)
  gemma2-9b-it             → Google Gemma via Groq

OBS: Groq-modellerna ovan är för TEXT (receptförslag, F1-kommentar etc.).
     Caregiver Modes vision-modell (bildanalys) konfigureras separat i
     Inställningar → Enheter och tjänster → Caregiver Mode → Konfigurera.

Sensorer (skapas automatiskt vid start):
  sensor.ai_hub_status          – ready / busy / error
  sensor.ai_hub_last_response   – senaste AI-svar (text + metadata)
  sensor.ai_hub_providers       – vilka leverantörer som är konfigurerade

Tjänster:
  pyscript.ai_hub_ask(prompt, provider, max_tokens, caller)
  pyscript.ai_hub_test()
"""

# ── Modulnivå-state ────────────────────────────────────────────────────────────
_busy            = [False]
_total_calls     = [0]
_calls_by_prov   = {}   # {"groq": 5, "anthropic": 2, ...}

# ── Nyckelhantering ────────────────────────────────────────────────────────────

def _key_ok(k):
    """True om k är en giltig, ifylld API-nyckel."""
    return bool(k) and k.strip() not in ("", "unknown", "none", "unavailable")


def _get_key(provider):
    """
    Hämtar API-nyckel för provider.
    Prioritet: ai_hub-entity → legacy-nyckel från annan integration
    (Så slipper man lägga in nyckeln igen om den redan finns någonstans.)
    """
    mapping = {
        "groq":      "input_text.ai_hub_groq_key",
        "anthropic": "input_text.ai_hub_anthropic_key",
        "openai":    "input_text.ai_hub_openai_key",
    }
    # Legacy-fallbacks: nycklar från andra integrationer
    legacy = {
        "groq":      "input_text.grocery_api_key_groq",
        "anthropic": "input_text.grocery_api_key_anthropic",
        "openai":    "input_text.grocery_api_key_openai",
    }
    entity = mapping.get(provider)
    if entity:
        key = (state.get(entity) or "").strip()
        if _key_ok(key):
            return key
    # Fallback till legacy-nyckel om ai_hub-nyckel är tom
    leg_entity = legacy.get(provider)
    if leg_entity:
        key = (state.get(leg_entity) or "").strip()
        if _key_ok(key):
            return key
    return ""


def _ollama_available():
    """True om Ollama-URL är satt och en modell är konfigurerad."""
    try:
        url = (state.get("input_text.ai_hub_ollama_url") or "").strip()
        model = (state.get("input_text.ai_hub_ollama_model") or "").strip()
        return bool(url) and url not in ("unknown", "unavailable") and bool(model)
    except Exception:
        return False


def _configured_providers():
    """Returnerar lista med leverantörer som har giltig nyckel."""
    result = []
    if _ollama_available():
        result.append("ollama")
    for p in ("groq", "anthropic", "openai"):
        if _key_ok(_get_key(p)):
            result.append(p)
    result.append("ha_ai_task")   # Alltid tillgänglig om AI är konfigurerat i HA
    return result


# ── Provider-anrop ─────────────────────────────────────────────────────────────

async def _call_groq(api_key, prompt, max_tokens):
    """Groq – modell väljs via input_select.ai_hub_groq_model (standard: llama-3.3-70b-versatile)."""
    import aiohttp
    model = (state.get("input_select.ai_hub_groq_model") or "llama-3.3-70b-versatile").strip()
    # Filtrera bort kommentarer om någon råkat inkludera dem
    model = model.split("#")[0].strip() if "#" in model else model
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.8,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data["choices"][0]["message"]["content"].strip()
                log.warning(f"[AI Hub] Groq HTTP {resp.status}")
    except Exception as e:
        log.warning(f"[AI Hub] Groq-fel: {e}")
    return None


async def _call_anthropic(api_key, prompt, max_tokens):
    """Anthropic – claude-haiku-4-5 (snabb och billig)."""
    import aiohttp
    try:
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data["content"][0]["text"].strip()
                log.warning(f"[AI Hub] Anthropic HTTP {resp.status}")
    except Exception as e:
        log.warning(f"[AI Hub] Anthropic-fel: {e}")
    return None


async def _call_openai(api_key, prompt, max_tokens):
    """OpenAI – gpt-4o-mini."""
    import aiohttp
    try:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.8,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data["choices"][0]["message"]["content"].strip()
                log.warning(f"[AI Hub] OpenAI HTTP {resp.status}")
    except Exception as e:
        log.warning(f"[AI Hub] OpenAI-fel: {e}")
    return None


async def _call_ollama(prompt, max_tokens):
    """Ollama – lokal LLM-server, native /api/chat endpoint. Ingen nyckel behövs."""
    import aiohttp
    base_url = (state.get("input_text.ai_hub_ollama_url") or "http://192.168.2.116:11434").strip().rstrip("/")
    model = (state.get("input_text.ai_hub_ollama_model") or "phi3:latest").strip()
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.7},
        }
        headers = {"Content-Type": "application/json"}
        # Använd await sess.post() direkt (inte async with på responsen) –
        # undviker pyscript-bugg med _BaseRequestContextManager vid HTTP-fel
        async with aiohttp.ClientSession() as sess:
            resp = await sess.post(
                f"{base_url}/api/chat",
                headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            )
            try:
                body = await resp.json(content_type=None)
                if resp.status == 200:
                    content = body.get("message", {}).get("content", "").strip()
                    return content or None
                err = body.get("error", str(body))
                log.warning(f"[AI Hub] Ollama HTTP {resp.status}: {err[:200]}")
            finally:
                resp.release()
    except Exception as e:
        log.warning(f"[AI Hub] Ollama-fel: {e}")
    return None


async def _call_ha_ai_task(prompt):
    """HA:s inbyggda AI (Google AI / Anthropic beroende på HA-konfiguration)."""
    try:
        result = await ai_task.generate_data(
            task_name="ai_hub_query",
            instructions=prompt,
        )
        if isinstance(result, str):
            return result.strip() or None
        if isinstance(result, dict):
            return result.get("text") or result.get("result") or None
    except Exception as e:
        log.warning(f"[AI Hub] ha_ai_task-fel: {e}")
    return None


# ── Routing ────────────────────────────────────────────────────────────────────

async def _route(prompt, provider, max_tokens):
    """
    Skickar prompt till rätt leverantör.

    provider-värden:
      groq / anthropic / openai  → direkt till den leverantören
      ha_ai_task                 → HA:s inbyggda AI
      auto                       → Groq → Anthropic → OpenAI → ha_ai_task
                                   (första med giltig nyckel)
    """
    p = (provider or "auto").strip().lower()

    if p == "ollama":
        return await _call_ollama(prompt, max_tokens)

    if p == "groq":
        key = _get_key("groq")
        if not _key_ok(key):
            log.warning("[AI Hub] Groq valt men ingen nyckel i input_text.ai_hub_groq_key")
            return None
        return await _call_groq(key, prompt, max_tokens)

    if p == "anthropic":
        key = _get_key("anthropic")
        if not _key_ok(key):
            log.warning("[AI Hub] Anthropic valt men ingen nyckel i input_text.ai_hub_anthropic_key")
            return None
        return await _call_anthropic(key, prompt, max_tokens)

    if p == "openai":
        key = _get_key("openai")
        if not _key_ok(key):
            log.warning("[AI Hub] OpenAI valt men ingen nyckel i input_text.ai_hub_openai_key")
            return None
        return await _call_openai(key, prompt, max_tokens)

    if p == "ha_ai_task":
        return await _call_ha_ai_task(prompt)

    # auto: Ollama → Groq → Anthropic → OpenAI → ha_ai_task
    if _ollama_available():
        result = await _call_ollama(prompt, max_tokens)
        if result:
            return result

    for prov, call_fn in [
        ("groq",      _call_groq),
        ("anthropic", _call_anthropic),
        ("openai",    _call_openai),
    ]:
        key = _get_key(prov)
        if _key_ok(key):
            result = await call_fn(key, prompt, max_tokens)
            if result:
                return result
    return await _call_ha_ai_task(prompt)


# ── Hjälpfunktion för andra integrationer ─────────────────────────────────────

def ai_hub_get_key(provider):
    """
    Publik hjälpfunktion – används av OpenF1, Grocery Tracker etc.
    Returnerar giltig API-nyckel för angiven provider, eller tom sträng.

    Användning i annan pyscript:
        from ai_hub import ai_hub_get_key   # fungerar ej i pyscript
        # Anropa istället direkt: state.get("input_text.ai_hub_groq_key")
    """
    return _get_key(provider)


# ── Service: ai_hub_ask ────────────────────────────────────────────────────────

@service
async def ai_hub_ask(prompt=None, provider=None, max_tokens=200, caller="unknown"):
    """
    Skicka en prompt till AI och spara svaret i sensor.ai_hub_last_response.

    Parametrar:
      prompt     (str)  – Prompten att skicka (obligatorisk)
      provider   (str)  – groq / anthropic / openai / ha_ai_task / auto
                          Standard: input_select.ai_hub_default_provider
      max_tokens (int)  – Max tokens i svaret (standard: 200)
      caller     (str)  – Namn på anropande integration (för statistik)
    """
    if not prompt:
        log.warning("[AI Hub] ai_hub_ask anropat utan prompt – ignorerar")
        return

    if _busy[0]:
        log.warning("[AI Hub] Redan ett pågående AI-anrop – ignorerar nytt anrop")
        return

    # Bestäm provider (eget argument → ai_hub default → auto)
    if not provider or provider in ("", "default"):
        provider = (state.get("input_select.ai_hub_default_provider") or "auto").strip().lower()

    _busy[0] = True
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()

    state.set("sensor.ai_hub_status", "busy", {
        "friendly_name": "AI Hub – Status",
        "icon": "mdi:robot",
        "provider": provider,
        "caller": caller,
        "total_calls": _total_calls[0],
        "calls_by_provider": dict(_calls_by_prov),
    })

    try:
        result = await _route(prompt, provider, max_tokens)

        if result:
            _total_calls[0] += 1
            _calls_by_prov[provider] = _calls_by_prov.get(provider, 0) + 1

            state.set("sensor.ai_hub_last_response", result[:500], {
                "friendly_name": "AI Hub – Senaste svar",
                "icon": "mdi:chat-outline",
                "prompt": (prompt[:200] if prompt else ""),
                "provider_used": provider,
                "timestamp": ts,
                "caller": caller,
                "total_calls": _total_calls[0],
            })
            state.set("sensor.ai_hub_status", "ready", {
                "friendly_name": "AI Hub – Status",
                "icon": "mdi:robot",
                "provider": provider,
                "caller": caller,
                "total_calls": _total_calls[0],
                "calls_by_provider": dict(_calls_by_prov),
            })
            log.info(f"[AI Hub] Svar OK – {provider}, caller={caller}, {len(result)} tecken")
        else:
            state.set("sensor.ai_hub_status", "error", {
                "friendly_name": "AI Hub – Status",
                "icon": "mdi:robot-dead",
                "provider": provider,
                "caller": caller,
                "error": "Inget svar från leverantören",
                "total_calls": _total_calls[0],
            })
            log.warning(f"[AI Hub] Inget svar från {provider} (caller={caller})")

    except Exception as e:
        state.set("sensor.ai_hub_status", "error", {
            "friendly_name": "AI Hub – Status",
            "icon": "mdi:robot-dead",
            "provider": provider,
            "caller": caller,
            "error": str(e)[:200],
            "total_calls": _total_calls[0],
        })
        log.error(f"[AI Hub] Fel: {e}")

    finally:
        _busy[0] = False
        _update_providers_sensor()


# ── Service: ai_hub_test ───────────────────────────────────────────────────────

@service
async def ai_hub_test():
    """Testa AI Hub med prompten i input_text.ai_hub_test_prompt."""
    prompt = (state.get("input_text.ai_hub_test_prompt") or "").strip()
    if not prompt:
        prompt = "Skriv en mening om Formel 1 på svenska."
    log.info(f"[AI Hub] Testar med prompt: {prompt[:80]}")
    await ai_hub_ask(prompt=prompt, caller="test")


# ── Providers-sensor ───────────────────────────────────────────────────────────

def _update_providers_sensor():
    configured = _configured_providers()
    state.set("sensor.ai_hub_providers", str(len(configured)), {
        "friendly_name": "AI Hub – Aktiva leverantörer",
        "icon": "mdi:robot-outline",
        "providers": configured,
        "groq":       _key_ok(_get_key("groq")),
        "anthropic":  _key_ok(_get_key("anthropic")),
        "openai":     _key_ok(_get_key("openai")),
        "ha_ai_task": True,
    })


# ── Startup ────────────────────────────────────────────────────────────────────

@time_trigger("startup")
async def _startup():
    state.set("sensor.ai_hub_status", "ready", {
        "friendly_name": "AI Hub – Status",
        "icon": "mdi:robot",
        "provider": "–",
        "caller": "–",
        "total_calls": 0,
        "calls_by_provider": {},
    })
    state.set("sensor.ai_hub_last_response", "–", {
        "friendly_name": "AI Hub – Senaste svar",
        "icon": "mdi:chat-outline",
        "prompt": "",
        "provider_used": "–",
        "timestamp": "",
        "caller": "–",
    })
    _update_providers_sensor()
    configured = _configured_providers()
    log.info(f"[AI Hub] v1.0 startad. Konfigurerade leverantörer: {', '.join(configured)}")
