import sys
import os
import asyncio
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Windows: psycopg async cần SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from langchain_openai import OpenAIEmbeddings
from langgraph.store.postgres.aio import AsyncPostgresStore

from configs.db import DBConfig, VectorDBConfig
from configs.llm import LLMConfig


DBConfig.validate()
STORE_URI = (
    f"postgresql://{VectorDBConfig.USER}:{VectorDBConfig.PASSWORD}"
    f"@{VectorDBConfig.HOST}:{VectorDBConfig.PORT}/{VectorDBConfig.NAME}"
)

# Embeddings cho long-term memory — vẫn text-embedding-3-small nhưng gọi qua OpenRouter.
MEMORY_EMBED_MODEL = os.getenv("MEMORY_EMBED_MODEL", "openai/text-embedding-3-small")
MEMORY_EMBED_DIMS = int(os.getenv("MEMORY_EMBED_DIMS", 1536))


def _memory_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=MEMORY_EMBED_MODEL,
        openai_api_key=LLMConfig.OPENROUTER_API_KEY,
        openai_api_base=LLMConfig.OPENROUTER_BASE_URL,
    )

_cm = None
_store: Optional[AsyncPostgresStore] = None


async def init_long_memory() -> AsyncPostgresStore:
    """Khởi tạo PostgreSQL store cho long-term memory"""
    global _cm, _store
    if _store is not None:
        return _store

    _cm = AsyncPostgresStore.from_conn_string(
        STORE_URI,
        index={
            "embed": _memory_embeddings(),
            "dims": MEMORY_EMBED_DIMS,
        },
    )
    _store = await _cm.__aenter__()
    await _store.setup()
    return _store


def get_store() -> Optional[AsyncPostgresStore]:
    return _store


async def close_long_memory() -> None:
    """Đóng store. Gọi lúc app tắt."""
    global _cm, _store
    if _cm is not None:
        await _cm.__aexit__(None, None, None)
        _cm = None
        _store = None

async def save_user_memory(user_id: str, key: str, data: dict) -> None:
    """Ghi một entry vào long-term memory của user."""
    assert _store is not None, "Long-term memory chưa được khởi tạo"
    await _store.aput(("users", user_id), key, data)


async def get_user_memory(user_id: str, key: str) -> Optional[dict]:
    """Đọc một entry từ long-term memory của user. Trả None nếu không có."""
    assert _store is not None, "Long-term memory chưa được khởi tạo"
    item = await _store.aget(("users", user_id), key)
    return item.value if item else None


async def update_user_preferences(user_id: str, new_rules: list[str]) -> None:
    existing = await get_user_memory(user_id, "preferences") or {"rules": []}
    rules = existing.get("rules", [])
    for rule in new_rules:
        if rule not in rules:
            rules.append(rule)
    await save_user_memory(user_id, "preferences", {"rules": rules})


async def update_user_profile(user_id: str, new_rules: list[str]) -> None:
    existing = await get_user_memory(user_id, "profile") or {"rules": []}
    rules = existing.get("rules", [])
    for rule in new_rules:
        if rule not in rules:
            rules.append(rule)
    await save_user_memory(user_id, "profile", {"rules": rules})


