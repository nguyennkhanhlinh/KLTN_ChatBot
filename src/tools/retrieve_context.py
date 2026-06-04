import os
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests
from langchain_core.tools import tool

from configs.llm import LLMConfig
from rag.embedding import vector_store

RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cohere/rerank-4-pro")
RERANK_TIMEOUT = float(os.getenv("RERANK_TIMEOUT", "30"))

COSINE_THRESHOLD = float(os.getenv("COSINE_THRESHOLD", "0.6"))
RERANK_THRESHOLD = float(os.getenv("RERANK_THRESHOLD", "0.0"))

MIN_CANDIDATES = 10
MAX_CANDIDATES = 30


class OpenRouterReranker:
    """Rerank qua OpenRouter (/v1/rerank, chuẩn Cohere).

    Giữ nguyên interface ``predict(pairs)`` của CrossEncoder: nhận list
    ``(query, document)`` và trả điểm relevance theo đúng thứ tự input.
    """

    def __init__(self, model: str = RERANKER_MODEL):
        self.model = model

    def predict(self, pairs, show_progress_bar: bool = False):
        if not pairs:
            return []
        query = pairs[0][0]
        documents = [p[1] for p in pairs]
        resp = requests.post(
            f"{LLMConfig.OPENROUTER_BASE_URL}/rerank",
            headers={"Authorization": f"Bearer {LLMConfig.OPENROUTER_API_KEY}"},
            json={
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": len(documents),
            },
            timeout=RERANK_TIMEOUT,
        )
        resp.raise_for_status()
        # results: [{"index": i, "relevance_score": s}] — map lại đúng thứ tự input.
        scores = [0.0] * len(documents)
        for r in resp.json()["results"]:
            scores[r["index"]] = r["relevance_score"]
        return scores


_reranker = OpenRouterReranker(RERANKER_MODEL)


@tool(response_format="content_and_artifact")
def retrieve_context(
    query: str,
    ma_codes: Optional[list[str]] = None,
    k: int = 5,
):
    """Semantic search các tin đăng BĐS theo nội dung mô tả.

    Pipeline:
    1. Vector search lấy candidate.
    2. Lọc score >= COSINE_THRESHOLD.
    3. Nếu kết quả sau threshold < 10, lấy thêm các doc dưới threshold gần 0.6 nhất.
    4. Cross-encoder rerank.
    5. Trả top k.
    """

    if ma_codes is not None and len(ma_codes) == 0:
        return "", []

    if ma_codes:
        ma_set = {str(c) for c in ma_codes}

        # Số lượng search stage 1:
        # nếu len(ma_codes) < 30 thì lấy len(ma_codes)
        # nếu len(ma_codes) > 30 thì lấy tối đa 30
        pool = min(len(ma_codes), MAX_CANDIDATES)

        # Nhưng nếu SQL có >= 10 mã thì cố lấy ít nhất 10 candidate
        pool = max(pool, min(MIN_CANDIDATES, len(ma_codes)))

        raw = vector_store.similarity_search_with_relevance_scores(
            query,
            k=pool,
        )

        # Chỉ giữ doc thuộc ma_codes từ SQL
        raw_in_sql = [
            (doc, score)
            for doc, score in raw
            if str(doc.metadata.get("ma_code")) in ma_set
        ]

    else:
        pool = MAX_CANDIDATES

        raw_in_sql = vector_store.similarity_search_with_relevance_scores(
            query,
            k=pool,
        )

    # Nhóm 1: đạt threshold
    passed = [
        (doc, score)
        for doc, score in raw_in_sql
        if score >= COSINE_THRESHOLD
    ]

    # Nhóm 2: dưới threshold, lấy gần threshold nhất
    below = [
        (doc, score)
        for doc, score in raw_in_sql
        if score < COSINE_THRESHOLD
    ]

    below = sorted(
        below,
        key=lambda x: abs(COSINE_THRESHOLD - x[1])
    )

    # Nếu passed < 10 thì bù thêm từ below
    target_min = MIN_CANDIDATES

    if ma_codes:
        target_min = min(MIN_CANDIDATES, len(ma_codes))

    need_more = max(0, target_min - len(passed))

    selected = passed + below[:need_more]

    # Dedupe theo ma_code
    seen, deduped = set(), []

    for doc, score in selected:
        code = str(doc.metadata.get("ma_code"))

        if not code or code in seen:
            continue

        seen.add(code)
        deduped.append(doc)

    if not deduped:
        return "", []

    # Stage 2: Cross-encoder rerank
    pairs = [(query, d.page_content) for d in deduped]
    scores = _reranker.predict(pairs, show_progress_bar=False)

    ranked = sorted(
        zip(deduped, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    final = [
        doc
        for doc, score in ranked
        if score >= RERANK_THRESHOLD
    ][:k]

    serialized = "\n\n".join(
        f"Source: {doc.metadata}\nContent: {doc.page_content}"
        for doc in final
    )

    return serialized, final