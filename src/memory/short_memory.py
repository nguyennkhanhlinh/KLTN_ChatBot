import sys
import os
import asyncio
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Windows: psycopg async cần SelectorEventLoop, không chạy được với ProactorEventLoop (default)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from psycopg_pool import AsyncConnectionPool
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from configs.db import DBConfig


MAX_USER_TURNS = 5


DBConfig.validate()

DB_URI = (
    f"postgresql://{DBConfig.USER}:{DBConfig.PASSWORD}"
    f"@{DBConfig.HOST}:{DBConfig.PORT}/{DBConfig.NAME}"
)

_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None


async def init_checkpointer() -> AsyncPostgresSaver:
    """Mở pool + tạo bảng checkpoint. Gọi 1 lần lúc app khởi động."""
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    _pool = AsyncConnectionPool(
        conninfo=DB_URI,
        max_size=DBConfig.POOL_MAX,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    )
    await _pool.open()

    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()

    async with _pool.connection() as conn:
        async with conn.cursor() as cur:
            # Bảng đánh dấu thread bị ẩn (soft delete)
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS hidden_threads ("
                "  thread_id TEXT PRIMARY KEY,"
                "  hidden_at TIMESTAMPTZ DEFAULT NOW()"
                ")"
            )
            # Bảng người dùng
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "  id SERIAL PRIMARY KEY,"
                "  username VARCHAR(50) UNIQUE NOT NULL,"
                "  password TEXT NOT NULL,"
                "  email VARCHAR(100),"
                "  phone VARCHAR(20),"
                "  role VARCHAR(20) NOT NULL DEFAULT 'user',"
                "  created_at TIMESTAMPTZ DEFAULT NOW()"
                ")"
            )
            await cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(100)")
            await cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20)")
            # Bảng liên kết session → user
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS user_sessions ("
                "  session_id TEXT PRIMARY KEY,"
                "  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
                "  model VARCHAR(80),"
                "  created_at TIMESTAMPTZ DEFAULT NOW()"
                ")"
            )
            await cur.execute("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS model VARCHAR(80)")
            # Log mỗi lượt chat → đếm số lượt sử dụng theo model
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS chat_log ("
                "  id BIGSERIAL PRIMARY KEY,"
                "  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,"
                "  session_id TEXT,"
                "  model VARCHAR(80),"
                "  created_at TIMESTAMPTZ DEFAULT NOW()"
                ")"
            )
            # Phản hồi like/dislike cho từng tin nhắn bot (1 user / 1 tin = 1 đánh giá)
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS message_feedback ("
                "  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
                "  session_id TEXT NOT NULL,"
                "  msg_key TEXT NOT NULL,"
                "  rating VARCHAR(10) NOT NULL,"          # 'like' | 'dislike'
                "  reason VARCHAR(20),"                   # wrong_data|irrelevant|incomplete|unclear|other
                "  comment TEXT,"                         # text khi reason = 'other'
                "  created_at TIMESTAMPTZ DEFAULT NOW(),"
                "  PRIMARY KEY (user_id, session_id, msg_key)"
                ")"
            )

    return _checkpointer


async def hide_thread(thread_id: str) -> None:
    """Đánh dấu thread bị ẩn — không hard delete, vẫn còn trong checkpoints."""
    async with _pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO hidden_threads (thread_id) VALUES (%s) "
                "ON CONFLICT (thread_id) DO NOTHING",
                (thread_id,),
            )


async def get_hidden_thread_ids() -> set:
    """Set các thread_id đang bị ẩn."""
    async with _pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT thread_id FROM hidden_threads")
            return {row[0] for row in await cur.fetchall()}


async def close_checkpointer() -> None:
    """Đóng pool. Gọi lúc app tắt."""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        _pool = None
        _checkpointer = None


def get_checkpointer() -> Optional[AsyncPostgresSaver]:
    """Trả về checkpointer (None nếu chưa init).

    build_graph() gọi hàm này lúc compile — nếu chưa init sẽ trả None,
    graph compile không có memory. Đảm bảo gọi init_checkpointer() trước
    khi build_graph() để có persistent memory.
    """
    return _checkpointer


def make_thread_config(thread_id: str) -> dict:
    """Tạo config truyền vào graph.ainvoke / graph.astream."""
    return {"configurable": {"thread_id": str(thread_id)}}


def trim_messages_to_last_user_turns(messages: list) -> list:
    """Pure helper: cắt list messages chỉ giữ MAX_USER_TURNS lượt user gần nhất.

    Cắt từ HumanMessage thứ N tính từ cuối, kèm theo mọi AI/tool message sau nó.
    KHÔNG đụng vào state — chỉ trả list mới để feed vào LLM.
    """
    human_indices = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    if len(human_indices) <= MAX_USER_TURNS:
        return list(messages)
    cutoff = human_indices[-MAX_USER_TURNS]
    return list(messages[cutoff:])
