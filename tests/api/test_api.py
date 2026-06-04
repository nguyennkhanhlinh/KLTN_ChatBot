"""Test toàn bộ API endpoint.

Phân nhóm:
  - Không cần gì: /health
  - Auth: endpoint bảo vệ phải chặn khi thiếu/sai token
  - Chat (mock LLM): /chat, /chat/stream — supervisor được mock, không gọi OpenAI
  - Validation: /auth/register, /admin/users kiểm tra dữ liệu trước khi đụng DB
  - DB (fake_db): login, me, sessions, admin — DB được giả lập
"""
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


# --------------------------------------------------------------------------- #
# /health
# --------------------------------------------------------------------------- #
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# --------------------------------------------------------------------------- #
# Auth: bắt buộc đăng nhập / phân quyền
# --------------------------------------------------------------------------- #
class TestAuthRequired:
    async def test_chat_requires_token(self, client):
        res = await client.post("/chat", json={"question": "hi"})
        assert res.status_code == 401

    async def test_me_requires_token(self, client):
        res = await client.get("/auth/me")
        assert res.status_code == 401

    async def test_sessions_requires_token(self, client):
        res = await client.get("/sessions")
        assert res.status_code == 401

    async def test_admin_requires_token(self, client):
        res = await client.get("/admin/users")
        assert res.status_code == 401

    async def test_admin_rejects_normal_user(self, client, user_headers):
        # token hợp lệ nhưng role=user -> 403
        res = await client.get("/admin/users", headers=user_headers)
        assert res.status_code == 403

    async def test_invalid_token(self, client):
        res = await client.get("/auth/me", headers={"Authorization": "Bearer rac-roi"})
        assert res.status_code == 401


# --------------------------------------------------------------------------- #
# /chat — mock LLM (supervisor giả)
# --------------------------------------------------------------------------- #
class TestChat:
    async def test_text_response(self, client, user_headers, mock_chat):
        # mock_chat mặc định trả AIMessage("Mocked answer")
        res = await client.post("/chat", json={"question": "Xin chào"}, headers=user_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "text"
        assert data["content"] == "Mocked answer"
        assert "usage" in data  # payload luôn kèm thống kê ký tự

    async def test_chart_response(self, client, user_headers, mock_chat):
        chart = {"chart_type": "bar", "columns": ["a", "b"], "data": [[1, 2]]}
        mock_chat.returns([
            HumanMessage(content="vẽ biểu đồ"),
            ToolMessage(content=json.dumps(chart), name="chart_tool", tool_call_id="1"),
        ])
        res = await client.post("/chat", json={"question": "vẽ biểu đồ"}, headers=user_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "chart"
        assert data["data"]["chart_type"] == "bar"

    async def test_mixed_response(self, client, user_headers, mock_chat):
        chart = {"chart_type": "line", "columns": ["x"], "data": [[1]]}
        mock_chat.returns([
            HumanMessage(content="phân tích"),
            ToolMessage(content=json.dumps(chart), name="chart_tool", tool_call_id="1"),
            ToolMessage(content="Tôi gợi ý mua căn A", name="recommendation_agent", tool_call_id="2"),
            AIMessage(content="Đây là kết quả tổng hợp"),
        ])
        res = await client.post("/chat", json={"question": "phân tích"}, headers=user_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "mixed"
        assert data["chart"]["chart_type"] == "line"
        assert data["text"] == "Tôi gợi ý mua căn A"

    async def test_custom_session_and_model(self, client, user_headers, mock_chat):
        res = await client.post(
            "/chat",
            json={"question": "hi", "session_id": "s1", "model": "gpt-4.1-mini"},
            headers=user_headers,
        )
        assert res.status_code == 200


# --------------------------------------------------------------------------- #
# /chat/stream — SSE, mock LLM
# --------------------------------------------------------------------------- #
class TestChatStream:
    async def test_stream_done_event(self, client, user_headers, mock_chat):
        res = await client.post("/chat/stream", json={"question": "hi"}, headers=user_headers)
        assert res.status_code == 200
        body = res.text
        assert '"type": "step"' in body   # bước "đang phân tích..."
        assert '"type": "done"' in body   # sự kiện kết quả cuối
        assert "Mocked answer" in body

    async def test_stream_error_event(self, client, user_headers, mock_chat):
        mock_chat.raises(RuntimeError("LLM sap"))
        res = await client.post("/chat/stream", json={"question": "hi"}, headers=user_headers)
        assert res.status_code == 200  # SSE vẫn 200, lỗi nằm trong event
        body = res.text
        assert '"type": "error"' in body
        assert "LLM sap" in body


# --------------------------------------------------------------------------- #
# Validation (chạy trước khi đụng DB)
# --------------------------------------------------------------------------- #
class TestRegisterValidation:
    async def test_username_too_short(self, client):
        res = await client.post("/auth/register", json={"username": "ab", "password": "123456"})
        assert res.status_code == 400

    async def test_password_too_short(self, client):
        res = await client.post("/auth/register", json={"username": "abc", "password": "123"})
        assert res.status_code == 400


# --------------------------------------------------------------------------- #
# Auth có DB (fake_db)
# --------------------------------------------------------------------------- #
class TestAuthDB:
    async def test_login_success(self, client, fake_db):
        fake_db.cursor.fetchone_results = [(1, "alice", "secret", "user")]
        res = await client.post("/auth/login", json={"username": "alice", "password": "secret"})
        assert res.status_code == 200
        data = res.json()
        assert data["username"] == "alice"
        assert data["role"] == "user"
        assert data["access_token"]

    async def test_login_wrong_password(self, client, fake_db):
        fake_db.cursor.fetchone_results = [(1, "alice", "secret", "user")]
        res = await client.post("/auth/login", json={"username": "alice", "password": "sai"})
        assert res.status_code == 401

    async def test_login_unknown_user(self, client, fake_db):
        fake_db.cursor.fetchone_results = []  # fetchone -> None
        res = await client.post("/auth/login", json={"username": "ghost", "password": "x"})
        assert res.status_code == 401

    async def test_register_success(self, client, fake_db):
        fake_db.cursor.fetchone_results = [(5,)]  # RETURNING id
        res = await client.post("/auth/register", json={"username": "newuser", "password": "123456"})
        assert res.status_code == 201
        assert res.json()["username"] == "newuser"

    async def test_register_duplicate(self, client, fake_db):
        fake_db.cursor.raise_on_execute = Exception("duplicate key")
        res = await client.post("/auth/register", json={"username": "dup", "password": "123456"})
        assert res.status_code == 400

    async def test_me_success(self, client, user_headers, fake_db):
        fake_db.cursor.fetchone_results = [("alice", "a@e.com", "0900", "user", None)]
        res = await client.get("/auth/me", headers=user_headers)
        assert res.status_code == 200
        assert res.json()["username"] == "alice"

    async def test_me_not_found(self, client, user_headers, fake_db):
        fake_db.cursor.fetchone_results = []
        res = await client.get("/auth/me", headers=user_headers)
        assert res.status_code == 404


# --------------------------------------------------------------------------- #
# Sessions (fake_db)
# --------------------------------------------------------------------------- #
class TestSessions:
    async def test_list_empty(self, client, user_headers, fake_db):
        res = await client.get("/sessions", headers=user_headers)
        assert res.status_code == 200
        assert res.json() == []

    async def test_get_session_empty(self, client, user_headers, fake_db):
        res = await client.get("/sessions/abc", headers=user_headers)
        assert res.status_code == 200
        assert res.json() == {"messages": []}

    async def test_rename_session(self, client, user_headers, fake_db):
        res = await client.patch("/sessions/abc", json={"title": "Tên mới"}, headers=user_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["title"] == "Tên mới"

    async def test_delete_session(self, client, user_headers, fake_db):
        res = await client.delete("/sessions/abc", headers=user_headers)
        assert res.status_code == 200
        assert res.json() == {"ok": True}


# --------------------------------------------------------------------------- #
# Admin (fake_db)
# --------------------------------------------------------------------------- #
class TestAdmin:
    async def test_list_users_empty(self, client, admin_headers, fake_db):
        res = await client.get("/admin/users", headers=admin_headers)
        assert res.status_code == 200
        assert res.json() == []

    async def test_create_user_success(self, client, admin_headers, fake_db):
        fake_db.cursor.fetchone_results = [(7,)]
        res = await client.post(
            "/admin/users",
            json={"username": "bob", "password": "123456", "role": "user"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert res.json()["id"] == 7

    async def test_create_user_invalid_role(self, client, admin_headers, fake_db):
        res = await client.post(
            "/admin/users",
            json={"username": "bob", "password": "123456", "role": "superadmin"},
            headers=admin_headers,
        )
        assert res.status_code == 400

    async def test_migrate_sessions(self, client, admin_headers, fake_db):
        res = await client.post("/admin/migrate-sessions", headers=admin_headers)
        assert res.status_code == 200
        assert res.json() == {"migrated": 0}

    async def test_list_sessions_empty(self, client, admin_headers, fake_db):
        res = await client.get("/admin/sessions", headers=admin_headers)
        assert res.status_code == 200
        assert res.json() == []
