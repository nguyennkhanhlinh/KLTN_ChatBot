from contextlib import contextmanager

import pytest

from data.database import Database
import src.tools.retrieve_context as rc


class _MockCursor:
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


class _MockConn:
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
    cursor = _MockCursor()

    @contextmanager
    def _get_conn(*args, **kwargs):
        yield _MockConn(cursor)

    monkeypatch.setattr(Database, "get_conn", _get_conn)
    return cursor



class _MockVectorStore:
    def __init__(self):
        self.results = []  # list[(Document, score)]

    def similarity_search_with_relevance_scores(self, query, k, filter=None):
        results = self.results
        # Mô phỏng metadata filter của PGVector: lọc theo ma_code $in ngay khi search.
        if filter:
            allowed = set(filter.get("ma_code", {}).get("$in", []))
            if allowed:
                results = [
                    (d, s) for d, s in results
                    if str(d.metadata.get("ma_code")) in allowed
                ]
        return results[:k]


class _MockReranker:
    def __init__(self):
        self.scores = None  # None -> điểm giảm dần theo thứ tự

    def predict(self, pairs, show_progress_bar=False):
        if self.scores is not None:
            return self.scores
        return [1.0 - i * 0.1 for i in range(len(pairs))]


@pytest.fixture
def mock_rag(monkeypatch):

    mock_vs = _MockVectorStore()
    mock_rr = _MockReranker()
    monkeypatch.setattr(rc, "vector_store", mock_vs)
    monkeypatch.setattr(rc, "_reranker", mock_rr)
    return mock_vs, mock_rr
