"""LLM client contract — the standard interface every concrete client must satisfy."""
from __future__ import annotations

from typing import Any, AsyncIterator, Iterator, Protocol, Sequence, runtime_checkable

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool


@runtime_checkable
class BaseLLMClient(Protocol):
    """Standard chat-LLM contract.

    Concrete clients expose the LangChain ``BaseChatModel`` API so they can be
    passed directly to ``langchain.agents.create_agent(model=...)``.
    """

    def invoke(self, input: LanguageModelInput, **kwargs: Any) -> BaseMessage: ...

    def stream(
        self, input: LanguageModelInput, **kwargs: Any
    ) -> Iterator[BaseMessage]: ...

    async def ainvoke(
        self, input: LanguageModelInput, **kwargs: Any
    ) -> BaseMessage: ...

    async def astream(
        self, input: LanguageModelInput, **kwargs: Any
    ) -> AsyncIterator[BaseMessage]: ...

    def bind_tools(
        self, tools: Sequence[BaseTool], **kwargs: Any
    ) -> Runnable[LanguageModelInput, BaseMessage]: ...
