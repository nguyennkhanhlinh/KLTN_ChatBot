from __future__ import annotations

import os
import sys
from typing import Any, Optional
from langchain_openai import ChatOpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from configs.llm import LLMConfig, resolve_model


class OpenAIClient(ChatOpenAI):
    """OpenAI-compatible chat client.

    Subclasses ``ChatOpenAI`` so an instance is itself a ``BaseChatModel`` and
    can be passed directly to ``langchain.agents.create_agent(model=...)``.

    Việc route provider (OpenAI / OpenRouter / ...) do ``resolve_model`` lo dựa
    trên tên model, nên mọi nơi chỉ cần ``OpenAIClient(model=...)`` là đủ.
    """

    def __init__(
        self,
        model: str = LLMConfig.OPENAI_MODEL,
        api_key: Optional[str] = None,
        temperature: float = LLMConfig.TEMPERATURE,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        resolved = resolve_model(model)
        if resolved["base_url"]:
            kwargs.setdefault("openai_api_base", resolved["base_url"])
        super().__init__(
            model=resolved["model"],
            openai_api_key=api_key or resolved["api_key"],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


if __name__ == "__main__":
    # Smoke-test qua OpenRouter (OPENAI_API_KEY có thể chưa cấu hình).
    client = OpenAIClient(model="deepseek/deepseek-v4-flash")
    print(client.invoke("Hello, world!"))
