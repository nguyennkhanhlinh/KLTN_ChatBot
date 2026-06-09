from contextlib import contextmanager

import pytest

from data.database import Database
import src.tools.retrieve_context as rc


class _FakeCursor:
    def __init__(self):
        self.description = [("col",)]   # execute_sql đọc thuộc tính này
        self.fetchall_results = []      # hàng đợi: mỗi lần fetchall() lấy 1 phần tử
        self.raise_exc = None           # gán Exception để mô phỏng lỗi DB
        self.executed = []              # log câu SQL đã chạy

    def execute(self, query, params=None):
        self.executed.append(str(query))
        if self.raise_exc is not None:
            raise self.raise_exc

    def fetchall(self):
        return self.fetchall_results.pop(0) if self.fetchall_results else []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def mock_db(monkeypatch):
    cursor = _FakeCursor()

    @contextmanager
    def _get_conn(*args, **kwargs):
        yield _FakeConn(cursor)

    monkeypatch.setattr(Database, "get_conn", _get_conn)
    return cursor



class _FakeVectorStore:
    def __init__(self):
        self.results = []  # list[(Document, score)]

    def similarity_search_with_relevance_scores(self, query, k):
        return self.results[:k]


class _FakeReranker:
    def __init__(self):
        self.scores = None  # None -> điểm giảm dần theo thứ tự

    def predict(self, pairs, show_progress_bar=False):
        if self.scores is not None:
            return self.scores
        return [1.0 - i * 0.1 for i in range(len(pairs))]


@pytest.fixture
def mock_rag(monkeypatch):

    fake_vs = _FakeVectorStore()
    fake_rr = _FakeReranker()
    monkeypatch.setattr(rc, "vector_store", fake_vs)
    monkeypatch.setattr(rc, "_reranker", fake_rr)
    return fake_vs, fake_rr
