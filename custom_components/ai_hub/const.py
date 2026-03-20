"""Constants for AI Hub."""

DOMAIN = "ai_hub"

CONF_GROQ_KEY        = "groq_key"
CONF_ANTHROPIC_KEY   = "anthropic_key"
CONF_OPENAI_KEY      = "openai_key"
CONF_OPENROUTER_KEY  = "openrouter_key"
CONF_OPENROUTER_MODEL = "openrouter_model"
CONF_OLLAMA_URL      = "ollama_url"
CONF_OLLAMA_MODEL    = "ollama_model"

DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
DEFAULT_OLLAMA_URL       = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL     = "llama3.2:latest"

# Maps config key → input_text entity_id (backwards compatibility)
KEY_TO_ENTITY = {
    CONF_GROQ_KEY:         "input_text.ai_hub_groq_key",
    CONF_ANTHROPIC_KEY:    "input_text.ai_hub_anthropic_key",
    CONF_OPENAI_KEY:       "input_text.ai_hub_openai_key",
    CONF_OPENROUTER_KEY:   "input_text.ai_hub_openrouter_key",
    CONF_OPENROUTER_MODEL: "input_text.ai_hub_openrouter_model",
    CONF_OLLAMA_URL:       "input_text.ai_hub_ollama_url",
    CONF_OLLAMA_MODEL:     "input_text.ai_hub_ollama_model",
}
