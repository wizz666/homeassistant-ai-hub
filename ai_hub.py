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
  input_text.ai_hub_ollama_url         – Ollama server-URL (standard: http://localhost:11434)
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
_busy                   = [False]
_total_calls            = [0]
_calls_by_prov          = {}   # {"groq": 5, "anthropic": 2, ...}
_system_prompt_override = [None]  # Sätts tillfälligt av automation builder

# ── Chathistorik (Ollama) ──────────────────────────────────────────────────────
_chat_history    = []   # [{"role": "user"|"assistant", "content": str, "ts": str}]
_MAX_HISTORY     = 20   # max antal meddelanden att hålla (10 turns)

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
        "groq":        "input_text.ai_hub_groq_key",
        "anthropic":   "input_text.ai_hub_anthropic_key",
        "openai":      "input_text.ai_hub_openai_key",
        "openrouter":  "input_text.ai_hub_openrouter_key",
    }
    entity = mapping.get(provider)
    if entity:
        key = (state.get(entity) or "").strip()
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
    for p in ("groq", "openrouter", "anthropic", "openai"):
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
        sys_msg = _build_system_message()
        messages = []
        if sys_msg:
            messages.append({"role": "system", "content": sys_msg})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model,
            "messages": messages,
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
        sys_msg = _build_system_message()
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if sys_msg:
            payload["system"] = sys_msg
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
        sys_msg = _build_system_message()
        messages = []
        if sys_msg:
            messages.append({"role": "system", "content": sys_msg})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
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


async def _call_openrouter(api_key, prompt, max_tokens):
    """OpenRouter – modell väljs via input_text.ai_hub_openrouter_model."""
    import aiohttp
    model = (state.get("input_text.ai_hub_openrouter_model") or "meta-llama/llama-3.3-70b-instruct:free").strip()
    try:
        sys_msg = _build_system_message()
        messages = []
        if sys_msg:
            messages.append({"role": "system", "content": sys_msg})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.8,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://homeassistant.local",
            "X-Title": "HA AI Hub",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data["choices"][0]["message"]["content"].strip()
                log.warning(f"[AI Hub] OpenRouter HTTP {resp.status}")
    except Exception as e:
        log.warning(f"[AI Hub] OpenRouter-fel: {e}")
    return None


async def _call_ollama(prompt, max_tokens, messages=None):
    """
    Ollama – lokal LLM-server, native /api/chat endpoint. Ingen nyckel behövs.

    messages: om angiven används full konversationshistorik (multi-turn).
              Format: [{"role": "user"|"assistant", "content": str}, ...]
              Systemprompt injiceras alltid först om konfigurerad.
    """
    import aiohttp
    base_url = (state.get("input_text.ai_hub_ollama_url") or "http://localhost:11434").strip().rstrip("/")
    model = (state.get("input_text.ai_hub_ollama_model") or "phi3:latest").strip()
    try:
        # Bygg meddelandelista: system → historik (eller ensamt user-meddelande)
        if messages is not None:
            ollama_messages = [{"role": h["role"], "content": h["content"]} for h in messages]
        else:
            ollama_messages = [{"role": "user", "content": prompt}]

        sys_msg = _build_system_message()
        if sys_msg:
            ollama_messages = [{"role": "system", "content": sys_msg}] + ollama_messages

        payload = {
            "model": model,
            "messages": ollama_messages,
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

async def _route(prompt, provider, max_tokens, messages=None):
    """
    Skickar prompt till rätt leverantör.

    provider-värden:
      groq / anthropic / openai  → direkt till den leverantören
      ha_ai_task                 → HA:s inbyggda AI
      auto                       → Ollama → Groq → Anthropic → OpenAI → ha_ai_task

    messages: konversationshistorik för multi-turn (används av Ollama)
    """
    p = (provider or "auto").strip().lower()

    if p == "ollama":
        return await _call_ollama(prompt, max_tokens, messages=messages)

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

    if p == "openrouter":
        key = _get_key("openrouter")
        if not _key_ok(key):
            log.warning("[AI Hub] OpenRouter valt men ingen nyckel i input_text.ai_hub_openrouter_key")
            return None
        return await _call_openrouter(key, prompt, max_tokens)

    if p == "ha_ai_task":
        return await _call_ha_ai_task(prompt)

    # auto: Ollama → Groq → Anthropic → OpenAI → ha_ai_task
    if _ollama_available():
        result = await _call_ollama(prompt, max_tokens, messages=messages)
        if result:
            return result

    for prov, call_fn in [
        ("groq",        _call_groq),
        ("openrouter",  _call_openrouter),
        ("anthropic",   _call_anthropic),
        ("openai",      _call_openai),
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


# ── Chathistorik-helpers ───────────────────────────────────────────────────────

def _add_to_history(role, content, ts):
    """Lägger till ett meddelande i chathistoriken och trimmar vid behov."""
    _chat_history.append({"role": role, "content": content, "ts": ts})
    # Trimma till max antal
    while len(_chat_history) > _MAX_HISTORY:
        _chat_history.pop(0)
    _update_chat_sensor()


def _update_chat_sensor():
    """Uppdaterar sensor.ai_hub_chat_history med senaste N meddelanden."""
    lines = []
    for h in _chat_history[-10:]:  # visa senaste 10 meddelanden
        time_str = h["ts"][11:16] if len(h["ts"]) >= 16 else h["ts"]
        if h["role"] == "user":
            lines.append(f"**Du** _{time_str}_\n{h['content']}")
        else:
            lines.append(f"**Ollama** _{time_str}_\n{h['content']}")
    history_md = "\n\n---\n\n".join(lines) if lines else "_Ingen chathistorik ännu._"

    state.set("sensor.ai_hub_chat_history", str(len(_chat_history)), {
        "friendly_name": "AI Hub – Chathistorik",
        "icon": "mdi:chat",
        "history_md": history_md[:4000],
        "message_count": len(_chat_history),
    })


# ── Systemprompt & Hemkontext ─────────────────────────────────────────────────

def _build_system_message():
    """
    Bygger en system-prompt för AI-anrop med:
      1. Fri text från input_text.ai_hub_system_prompt (persona)
      2. Realtidsdata från kommaseparerade entiteter i input_text.ai_hub_context_entities
    Om _system_prompt_override är satt används den istället (t.ex. av automation builder).
    Returnerar sträng eller None om ingenting är konfigurerat.
    """
    if _system_prompt_override[0]:
        return _system_prompt_override[0]

    base = (state.get("input_text.ai_hub_system_prompt") or "").strip()
    if base in ("unknown", "unavailable"):
        base = ""

    ctx_raw = (state.get("input_text.ai_hub_context_entities") or "").strip()
    context_lines = []
    if ctx_raw and ctx_raw not in ("unknown", "unavailable", ""):
        entity_ids = [e.strip() for e in ctx_raw.split(",") if e.strip()]
        for eid in entity_ids:
            try:
                val = state.get(eid)
                if val and val not in ("unavailable", "unknown"):
                    attrs = state.getattr(eid) or {}
                    friendly = attrs.get("friendly_name", eid)
                    unit = attrs.get("unit_of_measurement", "")
                    context_lines.append(
                        f"{friendly}: {val}{' ' + unit if unit else ''}"
                    )
            except Exception:
                pass

    parts = []
    if base:
        parts.append(base)
    if context_lines:
        parts.append("Aktuell hemdata:\n" + "\n".join(context_lines))

    return "\n\n".join(parts) if parts else None


# ── Service: ai_hub_chat_clear ────────────────────────────────────────────────

@service
async def ai_hub_chat_clear():
    """Rensar Ollama-chathistoriken."""
    _chat_history.clear()
    _update_chat_sensor()
    log.info("[AI Hub] Chathistorik rensad")


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

    # Lägg till user-meddelande i chathistorik (om ollama_chat-anrop)
    if caller == "ollama_chat":
        _add_to_history("user", prompt, ts)

    # Multi-turn: skicka full historik till Ollama om det är ett chat-anrop
    messages_ctx = None
    if caller == "ollama_chat" and len(_chat_history) > 0:
        messages_ctx = list(_chat_history)

    try:
        result = await _route(prompt, provider, max_tokens, messages=messages_ctx)

        if result:
            _total_calls[0] += 1
            _calls_by_prov[provider] = _calls_by_prov.get(provider, 0) + 1

            # Lägg till AI-svar i chathistorik
            if caller == "ollama_chat":
                from datetime import datetime as _dt, timezone as _tz
                _add_to_history("assistant", result, _dt.now(_tz.utc).isoformat())

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


# ── Morgonbriefing ─────────────────────────────────────────────────────────────

def _build_morning_prompt():
    """Bygger prompt för morgonbriefingen med hemdata och datum."""
    from datetime import datetime as _dt
    now = _dt.now()
    weekdays = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
    weekday_name = weekdays[now.weekday()]
    date_str = now.strftime(f"{weekday_name} %-d/%-m %Y kl %-H:%M")

    lines = [f"Idag är {date_str}."]

    # Läs kontext-entiteter (samma som systemprompt-kontexten)
    ctx_raw = (state.get("input_text.ai_hub_context_entities") or "").strip()
    if ctx_raw and ctx_raw not in ("unknown", "unavailable", ""):
        entity_ids = [e.strip() for e in ctx_raw.split(",") if e.strip()]
        for eid in entity_ids:
            try:
                val = state.get(eid)
                if val and val not in ("unavailable", "unknown"):
                    attrs = state.getattr(eid) or {}
                    friendly = attrs.get("friendly_name", eid)
                    unit = attrs.get("unit_of_measurement", "")
                    lines.append(f"{friendly}: {val}{' ' + unit if unit else ''}")
            except Exception:
                pass

    context = "\n".join(lines)
    persona = (state.get("input_text.ai_hub_system_prompt") or "").strip()
    if persona in ("unknown", "unavailable"):
        persona = ""

    return (
        f"{persona + chr(10) + chr(10) if persona else ''}"
        f"Ge en kort, vänlig morgonsammanfattning på svenska (3–4 meningar) "
        f"baserad på nedanstående hemdata. Avsluta med en uppmuntrande mening.\n\n"
        f"{context}"
    )


@time_trigger("cron(* 5-10 * * *)")
async def _morning_brief_tick():
    """Kontrollerar varje minut 05–10 om det är dags för morgonbriefing."""
    enabled = state.get("input_boolean.ai_hub_morning_brief")
    if enabled != "on":
        return

    brief_time = (state.get("input_datetime.ai_hub_morning_brief_time") or "").strip()
    if not brief_time or brief_time in ("unknown", "unavailable"):
        return

    from datetime import datetime as _dt
    now_hm = _dt.now().strftime("%H:%M")
    if not brief_time.startswith(now_hm):
        return

    log.info(f"[AI Hub] Morgonbriefing kl {now_hm} – startar")
    await _send_morning_brief()


async def _send_morning_brief():
    """Genererar och levererar morgonbriefingen."""
    prompt = _build_morning_prompt()
    await ai_hub_ask(prompt=prompt, max_tokens=350, caller="morning_brief")

    response = (state.get("sensor.ai_hub_last_response") or "").strip()
    if not response or response in ("–", "unavailable", "unknown"):
        log.warning("[AI Hub] Morgonbriefing – inget svar från AI")
        return

    # Leverera via HA persistent notification (alltid)
    persistent_notification.create(
        title="🌅 Morgonbriefing",
        message=response,
        notification_id="ai_hub_morning_brief",
    )
    log.info(f"[AI Hub] Morgonbriefing levererad ({len(response)} tecken)")


@service
async def ai_hub_morning_brief_now():
    """Skickar morgonbriefing manuellt (oavsett tid/aktivering)."""
    log.info("[AI Hub] Manuell morgonbriefing begärd")
    await _send_morning_brief()


# ── Ollama Modellhantering ─────────────────────────────────────────────────────

# Rekommenderade modeller – visas i installations-UI
_RECOMMENDED_MODELS = [
    {"name": "fixt/home-3b-v3:q3_k_m", "size": "1.4 GB", "desc": "HA-specialiserad (97% JSON-accuracy)", "type": "⭐ HA"},
    {"name": "fixt/home-3b-v3:q2_k",   "size": "1.1 GB", "desc": "HA-specialiserad – minsta variant",     "type": "⭐ HA"},
    {"name": "llama3.2:1b",             "size": "1.3 GB", "desc": "Snabb allmänmodell",                    "type": "Allmän"},
    {"name": "qwen2.5:1.5b",            "size": "1.0 GB", "desc": "Alibaba, liten och snabb",              "type": "Allmän"},
    {"name": "gemma2:2b",               "size": "1.6 GB", "desc": "Google Gemma, bra på svenska",          "type": "Allmän"},
    {"name": "tinyllama:latest",        "size": "0.6 GB", "desc": "Extremt liten, snabbast möjligt",       "type": "Allmän"},
    {"name": "mistral:latest",          "size": "4.1 GB", "desc": "Bäst kvalitet (kräver mer RAM)",        "type": "Stor"},
]


@service
async def ai_hub_ollama_pull(model=None):
    """
    Installerar en Ollama-modell via /api/pull.
    model: modellnamn (t.ex. 'llama3.2:1b'). Läses från
           input_text.ai_hub_ollama_install_model om utelämnat.
    Nedladdning sker på Ollama-servern – kan ta flera minuter.
    Status visas i sensor.ai_hub_ollama_pull_status.
    """
    import aiohttp
    from datetime import datetime as _dt

    if not model or model in ("", "unknown", "unavailable"):
        model = (state.get("input_text.ai_hub_ollama_install_model") or "").strip()
    if not model or model in ("", "unknown", "unavailable"):
        log.warning("[AI Hub] ai_hub_ollama_pull: inget modellnamn angivet")
        return

    base_url = (state.get("input_text.ai_hub_ollama_url") or "http://localhost:11434").strip().rstrip("/")

    state.set("sensor.ai_hub_ollama_pull_status", "downloading", {
        "friendly_name": "AI Hub – Modellnedladdning",
        "icon": "mdi:download",
        "model": model,
        "message": f"Laddar ner {model}… (kan ta flera minuter)",
        "started": _dt.now().strftime("%H:%M:%S"),
    })
    log.info(f"[AI Hub] Startar nedladdning: {model}")

    try:
        async with aiohttp.ClientSession() as sess:
            resp = await sess.post(
                f"{base_url}/api/pull",
                json={"name": model, "stream": False},
                timeout=aiohttp.ClientTimeout(total=600),
            )
            try:
                data = await resp.json(content_type=None)
                status_val = data.get("status", "")
                if resp.status == 200 and "success" in status_val:
                    state.set("sensor.ai_hub_ollama_pull_status", "done", {
                        "friendly_name": "AI Hub – Modellnedladdning",
                        "icon": "mdi:check-circle",
                        "model": model,
                        "message": f"{model} installerad!",
                        "finished": _dt.now().strftime("%H:%M:%S"),
                    })
                    log.info(f"[AI Hub] {model} installerad!")
                    await _refresh_ollama_models()
                else:
                    err = data.get("error", f"HTTP {resp.status}")
                    state.set("sensor.ai_hub_ollama_pull_status", "error", {
                        "friendly_name": "AI Hub – Modellnedladdning",
                        "icon": "mdi:alert-circle",
                        "model": model,
                        "message": f"Fel: {err[:200]}",
                    })
                    log.error(f"[AI Hub] Pull-fel för {model}: {err}")
            finally:
                resp.release()

    except Exception as e:
        state.set("sensor.ai_hub_ollama_pull_status", "error", {
            "friendly_name": "AI Hub – Modellnedladdning",
            "icon": "mdi:alert-circle",
            "model": model,
            "message": f"Anslutningsfel: {str(e)[:200]}",
        })
        log.error(f"[AI Hub] Pull-undantag: {e}")


@time_trigger("startup")
@time_trigger("cron(0 * * * *)")
async def _ollama_models_refresh_auto():
    """Hämtar Ollama-modellista vid start och varje timme."""
    await _refresh_ollama_models()


@service
async def ai_hub_ollama_refresh():
    """Uppdaterar modellistan från Ollama-servern manuellt."""
    log.info("[AI Hub] Manuell modelluppdatering begärd")
    await _refresh_ollama_models()


async def _refresh_ollama_models():
    """
    Hämtar /api/tags från Ollama och uppdaterar:
      sensor.ai_hub_ollama_models   – lista med namn, storlek, parametrar
      input_select.ai_hub_ollama_model_select – dropdown med tillgängliga modeller
    """
    import aiohttp
    from datetime import datetime as _dt
    base_url = (state.get("input_text.ai_hub_ollama_url") or "http://localhost:11434").strip().rstrip("/")

    try:
        async with aiohttp.ClientSession() as sess:
            resp = await sess.get(
                f"{base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=10),
            )
            try:
                if resp.status != 200:
                    log.warning(f"[AI Hub] Ollama /api/tags HTTP {resp.status}")
                    return
                data = await resp.json(content_type=None)
            finally:
                resp.release()

        models_raw = data.get("models", [])

        # Bygg modellista med formaterad storlek – list comprehension (ej generator)
        models = [
            {
                "name":     m.get("name", ""),
                "size_gb":  round(m.get("size", 0) / 1_073_741_824, 1),
                "params":   m.get("details", {}).get("parameter_size", "?"),
                "quant":    m.get("details", {}).get("quantization_level", ""),
            }
            for m in models_raw
        ]
        models.sort(key=lambda x: x["size_gb"])

        model_names = [m["name"] for m in models]
        current = (state.get("input_text.ai_hub_ollama_model") or "phi3:latest").strip()

        # Uppdatera input_select dynamiskt
        if model_names:
            input_select.set_options(
                entity_id="input_select.ai_hub_ollama_model_select",
                options=model_names,
            )
            target = current if current in model_names else model_names[0]
            input_select.select_option(
                entity_id="input_select.ai_hub_ollama_model_select",
                option=target,
            )

        state.set("sensor.ai_hub_ollama_models", str(len(models)), {
            "friendly_name": "AI Hub – Ollama modeller",
            "icon": "mdi:brain",
            "models": models,
            "current_model": current,
            "server": base_url,
            "last_updated": _dt.now().strftime("%H:%M"),
            "recommended": _RECOMMENDED_MODELS,
        })
        log.info(f"[AI Hub] {len(models)} Ollama-modeller hämtade: {model_names}")

    except Exception as e:
        log.warning(f"[AI Hub] Kunde inte hämta Ollama-modeller: {e}")
        state.set("sensor.ai_hub_ollama_models", "0", {
            "friendly_name": "AI Hub – Ollama modeller",
            "icon": "mdi:brain-off",
            "models": [],
            "error": str(e)[:200],
            "last_updated": "–",
        })


# ── Automation Builder ─────────────────────────────────────────────────────────

_AUTOMATION_SYSTEM_PROMPT = """Du är en Home Assistant-expert. Generera BARA YAML för HA:s UI-automationseditor.

OBLIGATORISKT FORMAT – följ EXAKT:

alias: "Automationens namn"
description: "Valfri beskrivning"
triggers:
  - trigger: state
    entity_id: sensor.example
    to: "on"
conditions: []
actions:
  - action: light.turn_on
    target:
      entity_id: light.example
mode: single

KRITISKA REGLER:
1. Använd "triggers:" (plural) på toppnivå – skriv det BARA EN GÅNG
2. Använd "actions:" (plural) på toppnivå – skriv det BARA EN GÅNG
3. Inuti listan: använd "trigger:" och "action:" (singular)
4. Använd ALLTID "action:" – ALDRIG "service:" (deprecated)
5. Avsluta ALLTID med "mode: single"
6. Generera BARA ren YAML – inga kommentarer, inga ```-ramar
7. Använd entiteter från listan nedan om de passar

Tillgängliga entiteter i detta hem:
{entities}"""


def _build_entity_list():
    """Bygger en kontextlista med hemets entiteter för automation builder."""
    domains = [
        "light", "switch", "cover", "climate", "fan",
        "media_player", "binary_sensor", "sensor",
        "input_boolean", "input_number", "input_select",
        "person", "alarm_control_panel",
    ]
    skip_prefixes = [
        "sensor.ai_hub_", "sensor.system_watchdog",
        "input_text.ai_hub_", "input_select.ai_hub_",
        "input_boolean.ai_hub_", "input_datetime.ai_hub_",
    ]
    lines = []
    for domain in domains:
        entities = state.names(domain=domain)
        count = 0
        for eid in sorted(entities):
            skip = False
            for prefix in skip_prefixes:
                if eid.startswith(prefix):
                    skip = True
                    break
            if skip:
                continue
            val = state.get(eid)
            attrs = state.getattr(eid) or {}
            friendly = attrs.get("friendly_name", eid)
            unit = attrs.get("unit_of_measurement", "")
            lines.append(
                f"- {eid} ({friendly}): {val}{' ' + unit if unit else ''}"
            )
            count += 1
            if count >= 15:
                remaining = len(entities) - 15
                if remaining > 0:
                    lines.append(f"  ... (+{remaining} fler {domain}-entiteter)")
                break
    return "\n".join(lines) if lines else "Inga entiteter tillgängliga."


@service
async def ai_hub_build_automation(description=None):
    """
    Genererar HA automation-YAML från en naturlig språkbeskrivning.

    description: t.ex. "Tänd lamporna i vardagsrummet vid solnedgång"
                 Läses från input_text.ai_hub_automation_prompt om utelämnat.
    Resultat sparas i sensor.ai_hub_automation_yaml.
    """
    from datetime import datetime as _dt

    if not description or description in ("", "unknown", "unavailable"):
        description = (state.get("input_text.ai_hub_automation_prompt") or "").strip()
    if not description:
        log.warning("[AI Hub] ai_hub_build_automation: ingen beskrivning angiven")
        return

    state.set("sensor.ai_hub_automation_yaml", "generating", {
        "friendly_name": "AI Hub – Automation YAML",
        "icon": "mdi:robot-outline",
        "description": description,
        "yaml": "",
        "generated_at": "",
    })

    entity_list = _build_entity_list()
    sys_prompt = _AUTOMATION_SYSTEM_PROMPT.format(entities=entity_list)

    _system_prompt_override[0] = sys_prompt
    try:
        provider = (state.get("input_select.ai_hub_default_provider") or "auto").strip().lower()
        result = await _route(description, provider, max_tokens=800)
    finally:
        _system_prompt_override[0] = None

    if result:
        # Rensa bort eventuella markdown-backticks om AI ändå lade dit dem
        clean = result.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(
                [l for l in lines if not l.strip().startswith("```")]
            )

        state.set("sensor.ai_hub_automation_yaml", "ready", {
            "friendly_name": "AI Hub – Automation YAML",
            "icon": "mdi:check-circle-outline",
            "description": description,
            "yaml": clean,
            "generated_at": _dt.now().strftime("%H:%M:%S"),
        })
        log.info(f"[AI Hub] Automation genererad ({len(clean)} tecken)")
    else:
        state.set("sensor.ai_hub_automation_yaml", "error", {
            "friendly_name": "AI Hub – Automation YAML",
            "icon": "mdi:alert-circle-outline",
            "description": description,
            "yaml": "",
            "generated_at": _dt.now().strftime("%H:%M:%S"),
        })
        log.warning("[AI Hub] Automation builder: inget svar från AI")


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
    state.set("sensor.ai_hub_ollama_models", "0", {
        "friendly_name": "AI Hub – Ollama modeller",
        "icon": "mdi:brain",
        "models": [],
        "current_model": "",
        "last_updated": "–",
        "recommended": _RECOMMENDED_MODELS,
    })
    state.set("sensor.ai_hub_ollama_pull_status", "idle", {
        "friendly_name": "AI Hub – Modellnedladdning",
        "icon": "mdi:download-off",
        "model": "",
        "message": "Ingen nedladdning pågår",
    })
    state.set("sensor.ai_hub_automation_yaml", "idle", {
        "friendly_name": "AI Hub – Automation YAML",
        "icon": "mdi:robot-outline",
        "description": "",
        "yaml": "",
        "generated_at": "",
    })
    _update_providers_sensor()
    _update_chat_sensor()
    configured = _configured_providers()
    log.info(f"[AI Hub] v1.5 startad. Konfigurerade leverantörer: {', '.join(configured)}")
