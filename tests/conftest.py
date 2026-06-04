"""Pytest fixtures dùng chung cho toàn bộ test API.

pytest tự nạp file này — mọi test trong tests/ dùng được các fixture dưới đây
mà KHÔNG cần import. Lưu ý: client dùng ASGITransport nên KHÔNG chạy lifespan
của app (không init DB, không load model, không build graph thật).
"""
import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from backend.main import app
from backend.auth import create_access_token


@pytest.fixture
async def client():
    """Async HTTP client để gọi thử API endpoint (in-process, không cần server)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --------------------------------------------------------------------------- #
# Auth: tạo JWT thật (get_current_user chỉ decode token, không đụng DB)
# --------------------------------------------------------------------------- #
@pytest.fixture
def user_token():
    """JWT của một user thường (id=1, username=alice, role=user)."""
    return create_access_token(1, "alice", "user")


@pytest.fixture
def admin_token():
    """JWT của admin (id=99, role=admin)."""
    return create_access_token(99, "admin", "admin")


@pytest.fixture
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# --------------------------------------------------------------------------- #
# Mock LLM: thay supervisor graph + bỏ ghi DB cho /chat, /chat/stream
# --------------------------------------------------------------------------- #
class _ChatHandle:
    """Điều khiển hành vi của supervisor giả trong mỗi test.

    Mặc định trả về 1 câu trả lời text. Test có thể đổi:
        mock_chat.returns([...messages...])   # đổi messages graph trả về
        mock_chat.raises(RuntimeError("..."))  # mô phỏng LLM lỗi
    """

    def __init__(self):
        self.messages = [HumanMessage(content="hi"), AIMessage(content="Mocked answer")]
        self.exc = None

    def returns(self, messages):
        self.messages = messages

    def raises(self, exc):
        self.exc = exc


@pytest.fixture
def mock_chat(monkeypatch):
    """Patch build_supervisor (LLM) + _register_session (DB) để test chat offline."""
    handle = _ChatHandle()

    class _FakeSupervisor:
        async def ainvoke(self, state, config=None, *, context=None):
            if handle.exc is not None:
                raise handle.exc
            return {"messages": handle.messages}

    monkeypatch.setattr("backend.main.build_supervisor", lambda *a, **k: _FakeSupervisor())

    async def _noop_register(*a, **k):
        return None

    monkeypatch.setattr("backend.main._register_session", _noop_register)
    return handle


# --------------------------------------------------------------------------- #
# Fake DB: giả lập checkpointer/Postgres cho các endpoint cần DB
# --------------------------------------------------------------------------- #
class _FakeCursor:
    def __init__(self):
        self.fetchone_results = []   # hàng đợi kết quả cho fetchone()
        self.fetchall_results = []   # hàng đợi kết quả cho fetchall()
        self.raise_on_execute = None  # gán Exception để mô phỏng lỗi SQL
        self.executed = []           # log các câu SQL đã chạy (để assert nếu cần)

    async def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self.raise_on_execute is not None:
            exc, self.raise_on_execute = self.raise_on_execute, None
            raise exc

    async def executemany(self, sql, seq):
        self.executed.append((sql, list(seq)))

    async def fetchone(self):
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    async def fetchall(self):
        return self.fetchall_results.pop(0) if self.fetchall_results else []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, cursor):
        self._conn = _FakeConn(cursor)

    def connection(self):
        return self._conn


class _FakeCheckpointer:
    def __init__(self):
        self.cursor = _FakeCursor()
        self.conn = _FakePool(self.cursor)
        self.aget_tuple_result = None  # snapshot trả cho _get_messages

    async def aget_tuple(self, config):
        return self.aget_tuple_result


@pytest.fixture
def fake_db(monkeypatch):
    """Giả lập DB để test endpoint dùng Postgres mà không cần DB thật.

    Cách dùng trong test:
        fake_db.cursor.fetchone_results = [(1, "alice", "secret", "user")]
        fake_db.cursor.fetchall_results = [[...row1...], [...row2...]]
        fake_db.cursor.raise_on_execute = Exception("duplicate")  # lỗi trùng key
    """
    ckpt = _FakeCheckpointer()
    monkeypatch.setattr("backend.main.get_checkpointer", lambda: ckpt)

    async def _no_hidden():
        return set()

    async def _hide(_thread_id):
        return None

    monkeypatch.setattr("backend.main.get_hidden_thread_ids", _no_hidden)
    monkeypatch.setattr("backend.main.hide_thread", _hide)
    return ckpt
