"""Test retrieve_context — semantic search + cross-encoder rerank.

vector_store và _reranker được mock (fixture mock_rag) để kiểm tra LOGIC lọc:
threshold cosine, bù candidate, lọc theo ma_codes, dedupe, rerank, top-k.
Tool dùng response_format="content_and_artifact" -> gọi .func(...) để lấy tuple
(serialized_text, danh_sach_documents).
"""
from langchain_core.documents import Document

from src.tools.retrieve_context import retrieve_context


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
        # rerank giảm dần: d2(0.9) > d3(0.5) > d1(0.1); lấy top 2
        assert _codes(artifact) == ["2", "3"]
        assert "Content:" in content

    def test_filter_by_ma_codes(self, mock_rag):
        vs, rr = mock_rag
        d_in1, d_in2, d_out = _doc("1"), _doc("2"), _doc("999")
        vs.results = [(d_in1, 0.9), (d_in2, 0.8), (d_out, 0.95)]
        # truyền đủ nhiều mã để pool >= số candidate -> d_out được fetch rồi mới bị lọc
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
