import json
import sys
import os
import asyncio
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.callbacks import AsyncCallbackHandler

from rag.index import index_from_json
from configs.llm import normalize_model_id
from src.agents.Supervisor_agent import build_supervisor, Context
from src.memory.short_memory import (
    make_thread_config,
    init_checkpointer,
    close_checkpointer,
    get_checkpointer,
    hide_thread,
    get_hidden_thread_ids,
)
from src.memory.long_memory import (
    init_long_memory,
    close_long_memory,
)
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_admin_user,
)


def _ensure_properties_data() -> int:
    """Tạo bảng properties nếu chưa có, nạp data_clean.csv nếu bảng đang rỗng.

    Idempotent — chạy mỗi lần startup nhưng chỉ ingest khi DB mới (bảng rỗng),
    để mọi DB mới (Docker/cloud) tự đầy đủ dữ liệu mà không cần thao tác tay.
    """
    from data.database import Database

    Database.create_tables()
    with Database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM properties")
            count = cur.fetchone()[0]
    if count == 0:
        from data.ingest_data import load_data
        load_data()
        with Database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM properties")
                count = cur.fetchone()[0]
    return count


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_checkpointer()
    await init_long_memory()
    await _ensure_admin_user()
    rows = _ensure_properties_data()
    print(f"[startup] Bảng properties sẵn sàng: {rows} dòng")
    n = index_from_json()
    print(f"[startup] Đã index {n} chunks vào RAG vector store")
    _app.state.graph = build_supervisor()
    yield
    await close_checkpointer()
    await close_long_memory()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    model: str = "gpt-4.1-mini"

class FeedbackRequest(BaseModel):
    session_id: str
    msg_key: str
    rating: str | None = None   
    reason: str | None = None   
    comment: str | None = None  

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    email: str = ""
    phone: str = ""

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    phone: str = ""


async def _ensure_admin_user():
    """Tạo tài khoản admin mặc định nếu chưa có user nào."""
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM users")
            count = (await cur.fetchone())[0]
            if count == 0:
                await cur.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                    ("admin", hash_password("admin123"), "admin"),
                )
                print("[startup] Đã tạo tài khoản admin mặc định (admin/admin123)")


async def _get_user_by_username(username: str):
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, username, password, role FROM users WHERE username = %s",
                (username,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "username": row[1], "password": row[2], "role": row[3]}


async def _register_session(session_id: str, user_id: int, model: str | None = None):
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO user_sessions (session_id, user_id, model) VALUES (%s, %s, %s) "
                "ON CONFLICT (session_id) DO UPDATE SET model = COALESCE(EXCLUDED.model, user_sessions.model)",
                (session_id, user_id, model),
            )


async def _log_chat(user_id: int, session_id: str, model: str | None):
    """Ghi 1 dòng mỗi lượt chat — để đếm số lượt sử dụng theo model."""
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO chat_log (user_id, session_id, model) VALUES (%s, %s, %s)",
                (user_id, session_id, model),
            )



class CharacterCounter(AsyncCallbackHandler):
    def __init__(self):
        self.input_chars = 0
        self.output_chars = 0
        self.total_chars = 0
        self.calls = 0

    async def on_llm_end(self, response, **kwargs):
        self.calls += 1
        for gen_list in response.generations:
            for gen in gen_list:
                self.output_chars += len(str(gen.text) if hasattr(gen, "text") else str(gen))
        self.total_chars = self.input_chars + self.output_chars

    def as_dict(self):
        return {
            "input_chars": self.input_chars,
            "output_chars": self.output_chars,
            "total_chars": self.total_chars,
            "calls": self.calls,
        }


@app.post("/auth/login")
async def login(req: LoginRequest):
    user = await _get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai tên đăng nhập hoặc mật khẩu")
    token = create_access_token(user["id"], user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"], "username": user["username"]}


@app.post("/auth/register", status_code=201)
async def register(req: RegisterRequest):
    if len(req.username) < 3:
        raise HTTPException(status_code=400, detail="Username phải có ít nhất 3 ký tự")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu phải có ít nhất 6 ký tự")
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "INSERT INTO users (username, password, email, phone, role) VALUES (%s, %s, %s, %s, 'user') RETURNING id",
                    (req.username, hash_password(req.password), req.email or None, req.phone or None),
                )
                user_id = (await cur.fetchone())[0]
            except Exception:
                raise HTTPException(status_code=400, detail="Username đã tồn tại")
    token = create_access_token(user_id, req.username, "user")
    return {"access_token": token, "token_type": "bearer", "role": "user", "username": req.username}


@app.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT username, email, phone, role, created_at FROM users WHERE id = %s",
                (int(current_user["sub"]),),
            )
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User không tồn tại")
    return {
        "id": current_user["sub"],
        "username": row[0],
        "email": row[1],
        "phone": row[2],
        "role": row[3],
        "created_at": row[4].isoformat() if row[4] else None,
    }




_AGENT_STEPS = {
    "supervisor": "Đang phân tích yêu cầu...",
    "analyst_agent": "Đang phân tích, thống kê dữ liệu...",
    "finance_agent": "Đang tính toán tài chính...",
    "recommendation_agent": "Đang tìm kiếm bất động sản phù hợp...",
}


def _build_chat_payload(msgs: list, usage: dict | None = None) -> dict:
    """Xử lý danh sách messages và trả về payload chuẩn cho frontend."""
    extra = {"usage": usage} if usage else {}
    if not msgs:
        return {"type": "text", "content": "", **extra}

    final_text = msgs[-1].content if hasattr(msgs[-1], "content") else ""

    try:
        data = json.loads(final_text)
        if "chart_type" in data and "columns" in data and "data" in data:
            return {"type": "chart", "data": data, **extra}
    except (json.JSONDecodeError, TypeError):
        pass

    last_human_idx = next(
        (len(msgs) - 1 - i for i, msg in enumerate(reversed(msgs)) if isinstance(msg, HumanMessage)),
        0,
    )
    current_turn_msgs = msgs[last_human_idx + 1:]

    chart_data = None
    recommendation_text = None
    analyst_text = None

    for msg in reversed(current_turn_msgs):
        if not isinstance(msg, ToolMessage):
            continue
        tool_name = getattr(msg, "name", "") or ""
        content = msg.content or ""

        if chart_data is None:
            try:
                data = json.loads(content)
                if "chart_type" in data and "columns" in data and "data" in data:
                    chart_data = data
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

        if analyst_text is None and tool_name == "analyst_agent" and content.strip():
            analyst_text = content
        if recommendation_text is None and tool_name == "recommendation_agent" and content.strip():
            recommendation_text = content

    if chart_data and recommendation_text:
        return {"type": "mixed", "chart": chart_data, "text": recommendation_text, **extra}
    if chart_data and analyst_text:
        return {"type": "mixed", "chart": chart_data, "text": analyst_text, **extra}
    if chart_data:
        return {"type": "chart", "data": chart_data, **extra}
    # Danh sách BĐS / phân tích: ưu tiên message cuối của supervisor (đã được chuẩn hoá
    # format theo Supervisor_prompt), để stream hiển thị GIỐNG HỆT lúc reload từ checkpointer
    # — vốn cũng đọc AIMessage cuối của supervisor. Tránh lệch định dạng (vd mất số 1.2.3)
    # do output thô của sub-agent không nhất quán.
    if analyst_text or recommendation_text:
        if final_text and final_text.strip():
            return {"type": "text", "content": final_text, **extra}
        # Fallback hiếm: supervisor không trả text → dùng output sub-agent.
        combined = "\n\n".join(t for t in (analyst_text, recommendation_text) if t)
        return {"type": "text", "content": combined, **extra}
    return {"type": "text", "content": final_text, **extra}


@app.post("/chat")
async def chat(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["sub"])
    config = make_thread_config(req.session_id)
    config["configurable"]["user_id"] = user_id
    config["metadata"] = {
        "session_id": req.session_id,
        "user_id": user_id,
        "username": current_user["username"],
    }
    counter = CharacterCounter()

    await _register_session(req.session_id, int(current_user["sub"]), req.model)
    await _log_chat(int(current_user["sub"]), req.session_id, req.model)

    supervisor = build_supervisor(model=normalize_model_id(req.model))
    result = await supervisor.ainvoke(
        {"messages": [HumanMessage(content=req.question)]},
        {**config, "callbacks": [counter]},
        context=Context(user_id=user_id),
    )
    usage = counter.as_dict()
    print(
        f"[/chat user={current_user['username']} session={req.session_id}] "
        f"{usage['calls']} calls — total={usage['total_chars']:,} chars"
    )
    return _build_chat_payload(result["messages"], usage)




@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """SSE endpoint: stream từng bước agent, gửi kết quả cuối khi xong."""
    user_id = str(current_user["sub"])
    config = make_thread_config(req.session_id)
    config["configurable"]["user_id"] = user_id
    config["metadata"] = {
        "session_id": req.session_id,
        "user_id": user_id,
        "username": current_user["username"],
    }
    await _register_session(req.session_id, int(current_user["sub"]), req.model)
    await _log_chat(int(current_user["sub"]), req.session_id, req.model)
    supervisor = build_supervisor(model=normalize_model_id(req.model))

    async def generate():
        try:
            yield f"data: {json.dumps({'type': 'step', 'agent': 'supervisor', 'label': _AGENT_STEPS['supervisor']})}\n\n"

            final_msgs: list = []
            seen_calls: set = set()  # tránh phát trùng 1 lần gọi tool (theo id)
            async for state in supervisor.astream(
                {"messages": [HumanMessage(content=req.question)]},
                {**config},
                stream_mode="values",
                context=Context(user_id=user_id),
            ):
                msgs = state.get("messages", []) if isinstance(state, dict) else []
                if msgs:
                    final_msgs = msgs
                # Phát step mỗi khi Supervisor quyết định gọi 1 sub-agent (tool_call mới)
                for m in msgs:
                    for tc in getattr(m, "tool_calls", None) or []:
                        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                        if call_id in seen_calls or name not in _AGENT_STEPS:
                            continue
                        seen_calls.add(call_id)
                        yield f"data: {json.dumps({'type': 'step', 'agent': name, 'label': _AGENT_STEPS[name]})}\n\n"

            payload = _build_chat_payload(final_msgs)
            yield f"data: {json.dumps({'type': 'done', 'result': payload})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


def _msg_to_dict(m) -> dict:
    if isinstance(m, HumanMessage):
        content = m.content if isinstance(m.content, str) else str(m.content)
        return {"role": "user", "content": content}
    content = m.content if isinstance(m.content, str) else str(m.content)
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "chart_type" in data and "columns" in data and "data" in data:
            return {"role": "chart", "data": data}
    except (json.JSONDecodeError, TypeError):
        pass
    return {"role": "bot", "content": content}


def _filter_visible(msgs: list) -> list:
    result = []
    pending_ai = None
    pending_chart_tool = None  # last ToolMessage with chart JSON in this turn
    for m in msgs:
        if isinstance(m, HumanMessage):
            # Flush previous turn
            if pending_chart_tool is not None:
                result.append(pending_chart_tool)
                # Bỏ pending_ai khi đã có chart — AIMessage chỉ là tóm tắt lại, sẽ trùng
            elif pending_ai is not None:
                result.append(pending_ai)
            pending_ai = None
            pending_chart_tool = None
            result.append(m)
        elif isinstance(m, AIMessage):
            pending_ai = m
        elif isinstance(m, ToolMessage):
            try:
                data = json.loads(m.content)
                if "chart_type" in data and "columns" in data and "data" in data:
                    pending_chart_tool = m
            except (json.JSONDecodeError, TypeError):
                pass
    # Flush last turn
    if pending_chart_tool is not None:
        result.append(pending_chart_tool)
    elif pending_ai is not None:
        result.append(pending_ai)
    return result


async def _get_messages(thread_id: str) -> list:
    snapshot = await get_checkpointer().aget_tuple(make_thread_config(thread_id))
    if not snapshot:
        return []
    raw = snapshot.checkpoint.get("channel_values", {}).get("messages", []) or []
    return _filter_visible(raw)


async def _build_session_list(thread_ids: list, hidden: set) -> list:
    sessions = []
    for tid in thread_ids:
        if tid in hidden:
            continue
        msgs = await _get_messages(tid)
        if not msgs:
            continue
        first_user = next((m for m in msgs if isinstance(m, HumanMessage)), None)
        if first_user:
            raw = first_user.content if isinstance(first_user.content, str) else str(first_user.content)
            title = raw[:40] + ("…" if len(raw) > 40 else "")
        else:
            title = "(trống)"
        try:
            created_at = int(tid.split("_")[-1]) if "_" in tid else int(tid)
        except ValueError:
            created_at = None
        sessions.append({
            "id": tid,
            "title": title,
            "createdAt": created_at,
            "messages": [_msg_to_dict(m) for m in msgs],
        })
    return sessions




@app.post("/feedback")
async def submit_feedback(req: FeedbackRequest, current_user: dict = Depends(get_current_user)):
    """Lưu/đổi/bỏ đánh giá like-dislike cho 1 tin nhắn bot (upsert theo user+session+msg)."""
    user_id = int(current_user["sub"])
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if req.rating is None:
                await cur.execute(
                    "DELETE FROM message_feedback "
                    "WHERE user_id = %s AND session_id = %s AND msg_key = %s",
                    (user_id, req.session_id, req.msg_key),
                )
            else:
                await cur.execute(
                    "INSERT INTO message_feedback "
                    "  (user_id, session_id, msg_key, rating, reason, comment) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (user_id, session_id, msg_key) DO UPDATE SET "
                    "  rating = EXCLUDED.rating, reason = EXCLUDED.reason, "
                    "  comment = EXCLUDED.comment, created_at = NOW()",
                    (user_id, req.session_id, req.msg_key, req.rating, req.reason, req.comment),
                )
    return {"ok": True}


@app.get("/feedback/{session_id}")
async def get_feedback(session_id: str, current_user: dict = Depends(get_current_user)):
    """Trả về các đánh giá đã lưu của user cho 1 phiên — để khôi phục màu like/dislike."""
    user_id = int(current_user["sub"])
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT msg_key, rating, reason FROM message_feedback "
                "WHERE user_id = %s AND session_id = %s",
                (user_id, session_id),
            )
            rows = await cur.fetchall()
    return {"feedback": [{"msg_key": r[0], "rating": r[1], "reason": r[2]} for r in rows]}


@app.get("/sessions")
async def list_sessions(current_user: dict = Depends(get_current_user)):
    """Chỉ trả về sessions của user hiện tại."""
    user_id = int(current_user["sub"])
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT session_id FROM user_sessions WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            thread_ids = [row[0] for row in await cur.fetchall()]

    hidden = await get_hidden_thread_ids()
    sessions = await _build_session_list(thread_ids, hidden)
    return sessions


@app.get("/sessions/{thread_id}")
async def get_session(thread_id: str, current_user: dict = Depends(get_current_user)):
    msgs = await _get_messages(thread_id)
    return {"messages": [_msg_to_dict(m) for m in msgs]}


@app.delete("/sessions/{thread_id}")
async def delete_session(thread_id: str, current_user: dict = Depends(get_current_user)):
    await hide_thread(thread_id)
    return {"ok": True}

@app.get("/admin/users")
async def admin_list_users(_admin: dict = Depends(get_admin_user)):
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, username, password, email, phone, role, created_at FROM users ORDER BY created_at DESC"
            )
            rows = await cur.fetchall()
    return [
        {"id": r[0], "username": r[1], "password": r[2], "email": r[3], "phone": r[4], "role": r[5], "created_at": r[6].isoformat() if r[6] else None}
        for r in rows
    ]


@app.post("/admin/users")
async def admin_create_user(req: CreateUserRequest, _admin: dict = Depends(get_admin_user)):
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role phải là 'user' hoặc 'admin'")
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "INSERT INTO users (username, password, email, phone, role) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (req.username, hash_password(req.password), req.email or None, req.phone or None, req.role),
                )
                user_id = (await cur.fetchone())[0]
            except Exception:
                raise HTTPException(status_code=400, detail="Username đã tồn tại")
    return {"id": user_id, "username": req.username, "role": req.role}


@app.post("/admin/migrate-sessions")
async def admin_migrate_sessions(admin: dict = Depends(get_admin_user)):
    """Gán tất cả session orphaned (chưa link user) vào admin."""
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT DISTINCT thread_id FROM checkpoints "
                "WHERE thread_id NOT IN (SELECT session_id FROM user_sessions)"
            )
            orphans = [row[0] for row in await cur.fetchall()]
            if orphans:
                admin_id = int(admin["sub"])
                await cur.executemany(
                    "INSERT INTO user_sessions (session_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    [(tid, admin_id) for tid in orphans],
                )
    return {"migrated": len(orphans)}


@app.get("/admin/sessions")
async def admin_list_sessions(_admin: dict = Depends(get_admin_user)):
    """Tất cả sessions của mọi user, kể cả đã bị user xoá (đánh dấu is_deleted)."""
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT us.session_id, u.username, us.created_at "
                "FROM user_sessions us JOIN users u ON us.user_id = u.id "
                "ORDER BY us.created_at DESC LIMIT 200"
            )
            rows = await cur.fetchall()
            await cur.execute("SELECT thread_id, hidden_at FROM hidden_threads")
            hidden_map = {r[0]: r[1] for r in await cur.fetchall()}

    result = []
    for session_id, username, created_at in rows:
        msgs = await _get_messages(session_id)
        if not msgs:
            continue
        first_user = next((m for m in msgs if isinstance(m, HumanMessage)), None)
        if first_user:
            raw = first_user.content if isinstance(first_user.content, str) else str(first_user.content)
            raw = raw
            title = raw[:50] + "…" if len(raw) > 50 else raw
        else:
            title = "(trống)"
        is_deleted = session_id in hidden_map
        result.append({
            "id": session_id,
            "username": username,
            "title": title,
            "created_at": created_at.isoformat() if created_at else None,
            "message_count": len(msgs),
            "is_deleted": is_deleted,
            "deleted_at": hidden_map[session_id].isoformat() if is_deleted else None,
        })
    return result


@app.get("/admin/stats")
async def admin_stats(_admin: dict = Depends(get_admin_user)):
    """Số liệu tổng hợp cho dashboard admin (chỉ truy vấn SQL, không duyệt checkpoint)."""
    pool = get_checkpointer().conn
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # KPI 
            await cur.execute("SELECT COUNT(*) FROM users")
            total_users = (await cur.fetchone())[0]
            await cur.execute("SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE")
            users_today = (await cur.fetchone())[0]
            await cur.execute("SELECT COUNT(*) FROM user_sessions")
            total_sessions = (await cur.fetchone())[0]
            await cur.execute("SELECT COUNT(*) FROM user_sessions WHERE created_at::date = CURRENT_DATE")
            sessions_today = (await cur.fetchone())[0]
            await cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_sessions")
            active_users = (await cur.fetchone())[0]

            # Người dùng đăng ký theo ngày (14 ngày gần nhất) 
            await cur.execute(
                "SELECT created_at::date AS d, COUNT(*) FROM users "
                "WHERE created_at >= CURRENT_DATE - INTERVAL '13 days' "
                "GROUP BY d ORDER BY d"
            )
            users_by_day = [[r[0].isoformat(), r[1]] for r in await cur.fetchall()]

            # Phiên chat theo ngày (14 ngày gần nhất) 
            await cur.execute(
                "SELECT created_at::date AS d, COUNT(*) FROM user_sessions "
                "WHERE created_at >= CURRENT_DATE - INTERVAL '13 days' "
                "GROUP BY d ORDER BY d"
            )
            sessions_by_day = [[r[0].isoformat(), r[1]] for r in await cur.fetchall()]

            # Top user theo số phiên 
            await cur.execute(
                "SELECT u.username, COUNT(us.session_id) AS c "
                "FROM user_sessions us JOIN users u ON us.user_id = u.id "
                "GROUP BY u.username ORDER BY c DESC LIMIT 8"
            )
            top_users = [[r[0], r[1]] for r in await cur.fetchall()]

            # Tỷ lệ role 
            await cur.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
            role_ratio = [[r[0], r[1]] for r in await cur.fetchall()]

            # So sánh model sử dụng (số lượt chat theo model) 
            await cur.execute(
                "SELECT model, COUNT(*) FROM chat_log "
                "WHERE model IS NOT NULL GROUP BY model ORDER BY 2 DESC"
            )
            model_usage = [[r[0], r[1]] for r in await cur.fetchall()]

            # Phiên theo khung giờ trong ngày 
            await cur.execute(
                "SELECT EXTRACT(HOUR FROM created_at)::int AS h, COUNT(*) "
                "FROM user_sessions GROUP BY h ORDER BY h"
            )
            sessions_by_hour = [[int(r[0]), r[1]] for r in await cur.fetchall()]

            # Feedback like/dislike 
            await cur.execute("SELECT rating, COUNT(*) FROM message_feedback GROUP BY rating")
            _fb = {r[0]: r[1] for r in await cur.fetchall()}
            like_count = _fb.get("like", 0)
            dislike_count = _fb.get("dislike", 0)

            # Lý do không hài lòng (chỉ dislike có chọn lý do)
            await cur.execute(
                "SELECT reason, COUNT(*) FROM message_feedback "
                "WHERE rating = 'dislike' AND reason IS NOT NULL "
                "GROUP BY reason ORDER BY 2 DESC"
            )
            dislike_reasons = [[r[0], r[1]] for r in await cur.fetchall()]


    try:
        from data.database import Database
        with Database.get_conn() as c:
            with c.cursor() as pcur:
                pcur.execute("SELECT COUNT(*) FROM properties")
                total_properties = pcur.fetchone()[0]
    except Exception:
        total_properties = 0

    return {
        "kpi": {
            "total_users": total_users,
            "users_today": users_today,
            "total_sessions": total_sessions,
            "sessions_today": sessions_today,
            "active_users": active_users,
            "total_properties": total_properties,
            "like_count": like_count,
            "dislike_count": dislike_count,
        },
        "users_by_day": users_by_day,
        "sessions_by_day": sessions_by_day,
        "top_users": top_users,
        "role_ratio": role_ratio,
        "model_usage": model_usage,
        "sessions_by_hour": sessions_by_hour,
        "dislike_reasons": dislike_reasons,
    }


if __name__ == "__main__":
    import uvicorn
    import selectors

    async def _serve():
        config = uvicorn.Config(app, host="0.0.0.0", port=8000)
        server = uvicorn.Server(config)
        await server.serve()

    if sys.platform == "win32":
        asyncio.run(
            _serve(),
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
