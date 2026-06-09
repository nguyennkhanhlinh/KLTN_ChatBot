import os
from dotenv import load_dotenv

load_dotenv()


class LLMConfig:
    TEMPERATURE    = float(os.getenv("LLM_TEMPERATURE", 0.0))

    # OPENAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


MODEL_REGISTRY: dict[str, dict] = {
    "gpt-4.1":      {"provider": "openrouter", "api_model": "openai/gpt-4.1"},
    "gpt-4.1-mini": {"provider": "openrouter", "api_model": "openai/gpt-4.1-mini"},
    "o4-mini":      {"provider": "openrouter", "api_model": "openai/o4-mini"},

    "deepseek/deepseek-v4-flash":     {"provider": "openrouter"},
    "mistralai/mistral-small-2603":   {"provider": "openrouter"},
}


def normalize_model_id(model_id: str | None) -> str:
    """Return a tool-capable configured model id, falling back for stale UI selections."""
    if model_id in MODEL_REGISTRY:
        return model_id
    return LLMConfig.OPENAI_MODEL


def resolve_model(model_id: str) -> dict:
    model_id = normalize_model_id(model_id)
    spec = MODEL_REGISTRY.get(model_id, {"provider": "openrouter"})
    provider = spec.get("provider", "openrouter")
    api_model = spec.get("api_model", model_id)

    if provider == "openrouter":
        return {
            "model": api_model,
            "api_key": LLMConfig.OPENROUTER_API_KEY,
            "base_url": LLMConfig.OPENROUTER_BASE_URL,
        }

    return {
        "model": api_model,
        "api_key": LLMConfig.OPENAI_API_KEY,
        "base_url": None,
    }

