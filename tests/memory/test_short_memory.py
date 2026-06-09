import pytest

import src.memory.short_memory as sm


class _FakeCursor:
    def __init__(self):
        self.executed = []          # log (sql, params) đã chạy
        self.fetchall_result = []   # rows trả cho fetchall()

    async def execute(self, sql, params=None):
        self.executed.append((sql, params))

    async def fetchall(self):
        return self.fetchall_result

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
        self.closed = False

    def connection(self):
        return self._conn

    async def close(self):
        self.closed = True


@pytest.fixture
def fake_pool(monkeypatch):
    cursor = _FakeCursor()
    pool = _FakePool(cursor)
    monkeypatch.setattr(sm, "_pool", pool)
    monkeypatch.setattr(sm, "_checkpointer", object())  # giả lập đã init
    return pool


async def test_hide_thread_inserts(fake_pool):
    await sm.hide_thread("t-123")
    sql, params = fake_pool._conn._cursor.executed[-1]
    assert "INSERT INTO hidden_threads" in sql
    assert "ON CONFLICT" in sql          # soft-delete: trùng thì bỏ qua
    assert params == ("t-123",)


async def test_get_hidden_thread_ids(fake_pool):
    fake_pool._conn._cursor.fetchall_result = [("a",), ("b",), ("a",)]
    result = await sm.get_hidden_thread_ids()
    assert result == {"a", "b"}          # trả về set -> tự khử trùng


async def test_get_hidden_thread_ids_empty(fake_pool):
    result = await sm.get_hidden_thread_ids()
    assert result == set()


async def test_close_checkpointer(fake_pool):
    await sm.close_checkpointer()
    assert fake_pool.closed is True
    assert sm._pool is None
    assert sm.get_checkpointer() is None


async def test_close_checkpointer_noop_when_already_closed(monkeypatch):
    # _pool = None -> không raise, không làm gì
    monkeypatch.setattr(sm, "_pool", None)
    await sm.close_checkpointer()
    assert sm._pool is None
