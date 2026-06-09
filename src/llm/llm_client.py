from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any, Optional
from langchain_openai import ChatOpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from configs.llm import LLMConfig, resolve_model



_RETRYABLE_HINTS = (
    "aborted", "timeout", "timed out", "overloaded", "temporarily",
    "rate limit", "429", "500", "502", "503", "504",
)
_MAX_TRANSIENT_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
_REQUEST_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))


def _is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(hint in msg for hint in _RETRYABLE_HINTS)


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
        max_tokens: int = 8000,
        **kwargs: Any,
    ) -> None:
        resolved = resolve_model(model)
        if resolved["base_url"]:
            kwargs.setdefault("openai_api_base", resolved["base_url"])
        # Resilience cho lỗi HTTP-level tạm thời (timeout, 5xx thật).
        kwargs.setdefault("timeout", _REQUEST_TIMEOUT)
        kwargs.setdefault("max_retries", _MAX_TRANSIENT_RETRIES)
        super().__init__(
            model=resolved["model"],
            openai_api_key=api_key or resolved["api_key"],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


    def _generate(self, *args: Any, **kwargs: Any):
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_TRANSIENT_RETRIES + 1):
            try:
                return super()._generate(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — phân loại lại ngay dưới
                last_exc = exc
                if attempt >= _MAX_TRANSIENT_RETRIES or not _is_transient(exc):
                    raise
                time.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]

    async def _agenerate(self, *args: Any, **kwargs: Any):
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_TRANSIENT_RETRIES + 1):
            try:
                return await super()._agenerate(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — phân loại lại ngay dưới
                last_exc = exc
                if attempt >= _MAX_TRANSIENT_RETRIES or not _is_transient(exc):
                    raise
                await asyncio.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]
