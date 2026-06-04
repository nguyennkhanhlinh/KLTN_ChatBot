import os
from dotenv import load_dotenv

load_dotenv()


class LLMConfig:
    # GEMINI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    TEMPERATURE    = float(os.getenv("LLM_TEMPERATURE", 0.0))

    # OPENAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    # OPENROUTER (gateway OpenAI-compatible — model_id dạng "vendor/model")
    OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    @classmethod
    def validate(cls):
        if not cls.GEMINI_API_KEY:
            raise ValueError("Thiếu biến môi trường: GEMINI_API_KEY")


# ============================================================
# Model registry — map model_id (FE gửi lên) -> tham số gọi API
#   provider quyết định api_key + base_url; api_model là tên model
#   thật sự gửi cho endpoint (có thể khác model_id hiển thị).
# ============================================================
MODEL_REGISTRY: dict[str, dict] = {
    # Model OpenAI nhưng gọi qua OpenRouter (api_model = slug "openai/..." gửi lên API)
    "gpt-4.1-mini": {"provider": "openrouter", "api_model": "openai/gpt-4.1-mini"},
    "o4-mini":      {"provider": "openrouter", "api_model": "openai/o4-mini"},
    # OpenRouter dùng nguyên slug "vendor/model" làm tên model gửi lên API
    "deepseek/deepseek-v4-flash":  {"provider": "openrouter"},
    "qwen/qwen3.5-flash-02-23":    {"provider": "openrouter"},
}


def resolve_model(model_id: str) -> dict:
    """Trả về {model, api_key, base_url} cho ChatOpenAI dựa trên model_id.

    Model lạ (không có trong registry) mặc định coi như provider OpenRouter —
    model_id được dùng nguyên làm slug "vendor/model" gửi lên API.
    """
    spec = MODEL_REGISTRY.get(model_id, {"provider": "openrouter"})
    provider = spec.get("provider", "openrouter")
    api_model = spec.get("api_model", model_id)

    if provider == "openrouter":
        return {
            "model": api_model,
            "api_key": LLMConfig.OPENROUTER_API_KEY,
            "base_url": LLMConfig.OPENROUTER_BASE_URL,
        }

    # openai (mặc định) — base_url None để dùng endpoint chuẩn của OpenAI
    return {
        "model": api_model,
        "api_key": LLMConfig.OPENAI_API_KEY,
        "base_url": None,
    }

