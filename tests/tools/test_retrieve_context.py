import pytest
from langchain_core.documents import Document

import src.tools.retrieve_context as rc
from src.tools.retrieve_context import OpenRouterReranker, retrieve_context


def _doc(ma_code, text="mo ta"):
    return Document(page_content=f"{text} {ma_code}", metadata={"ma_code": ma_code})


def _codes(artifact):
    return [str(d.metadata["ma_code"]) for d in artifact]


class TestRetrieveContext:
    def test_empty_ma_codes_short_circuit(self, mock_rag):
        # ma_codes rỗng = SQL không trả mã nào -> trả về rỗng ngay
        content, artifact = retrieve_context.func(query="nhà quận 1", ma_codes=[])
        assert content == ""
        assert artifact == []

    def test_no_results(self, mock_rag):
        vs, _ = mock_rag
        vs.results = []
        content, artifact = retrieve_context.func(query="nhà quận 1")
        assert content == ""
        assert artifact == []

    def test_threshold_and_topk_and_rerank_order(self, mock_rag):
        vs, rr = mock_rag
        d1, d2, d3 = _doc("1"), _doc("2"), _doc("3")
        vs.results = [(d1, 0.9), (d2, 0.7), (d3, 0.5)]  # d3 dưới ngưỡng 0.6
        rr.scores = [0.1, 0.9, 0.5]  # theo thứ tự deduped [d1, d2, d3]
        content, artifact = retrieve_context.func(query="q", k=2)
        assert _codes(artifact) == ["2", "3"]
        assert "Content:" in content

    def test_filter_by_ma_codes(self, mock_rag):
        vs, rr = mock_rag
        d_in1, d_in2, d_out = _doc("1"), _doc("2"), _doc("999")
        vs.results = [(d_in1, 0.9), (d_in2, 0.8), (d_out, 0.95)]
        content, artifact = retrieve_context.func(
            query="q",
            ma_codes=[str(i) for i in range(1, 11)],  # 1..10, không có 999
        )
        assert set(_codes(artifact)) == {"1", "2"}
        assert "999" not in _codes(artifact)

    def test_rerank_threshold_filters_negative(self, mock_rag):
        vs, rr = mock_rag
        d1, d2 = _doc("1"), _doc("2")
        vs.results = [(d1, 0.9), (d2, 0.8)]
        rr.scores = [-1.0, 0.5]  # d1 < RERANK_THRESHOLD(0.0) -> loại
        content, artifact = retrieve_context.func(query="q")
        assert _codes(artifact) == ["2"]

    def test_dedupe_same_ma_code(self, mock_rag):
        vs, rr = mock_rag
        d1, d2 = _doc("5", "tin A"), _doc("5", "tin B")  # trùng ma_code
        vs.results = [(d1, 0.9), (d2, 0.85)]
        content, artifact = retrieve_context.func(query="q")
        assert len(artifact) == 1
        assert _codes(artifact) == ["5"]

class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class TestOpenRouterReranker:
    def test_predict_empty_pairs_no_http(self, monkeypatch):
        def _boom(*a, **k):
            raise AssertionError("không được gọi requests.post khi pairs rỗng")

        monkeypatch.setattr(rc.requests, "post", _boom)
        assert OpenRouterReranker().predict([]) == []

    def test_predict_maps_scores_by_index(self, monkeypatch):
        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            # results trả về đảo thứ tự index -> hàm phải map đúng về vị trí gốc
            return _FakeResp({"results": [
                {"index": 1, "relevance_score": 0.8},
                {"index": 0, "relevance_score": 0.3},
            ]})

        monkeypatch.setattr(rc.requests, "post", fake_post)
        scores = OpenRouterReranker(model="m").predict([("q", "docA"), ("q", "docB")])

        assert scores == [0.3, 0.8]                       # map đúng theo index
        assert captured["url"].endswith("/rerank")
        assert captured["json"]["query"] == "q"
        assert captured["json"]["documents"] == ["docA", "docB"]
        assert captured["json"]["model"] == "m"

    def test_predict_missing_index_defaults_zero(self, monkeypatch):
        # API chỉ chấm 1 doc -> doc còn lại giữ điểm mặc định 0.0
        def fake_post(url, headers=None, json=None, timeout=None):
            return _FakeResp({"results": [{"index": 0, "relevance_score": 0.9}]})

        monkeypatch.setattr(rc.requests, "post", fake_post)
        scores = OpenRouterReranker().predict([("q", "a"), ("q", "b")])
        assert scores == [0.9, 0.0]

    def test_predict_raises_on_http_error(self, monkeypatch):
        class _ErrResp:
            def raise_for_status(self):
                raise RuntimeError("502 Bad Gateway")

            def json(self):
                return {}

        monkeypatch.setattr(rc.requests, "post", lambda *a, **k: _ErrResp())
        with pytest.raises(RuntimeError):
            OpenRouterReranker().predict([("q", "a")])
