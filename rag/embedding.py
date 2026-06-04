import logging
import os
import sys
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import DistanceStrategy
from openai import OpenAI

from configs.db import VectorDBConfig
from configs.llm import LLMConfig

load_dotenv()
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION", "properties_chunks")
# OpenRouter giới hạn ~512 token / input; chia batch để tránh request quá lớn.
EMBED_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", 64))


class PropertyEmbeddingService(Embeddings):
    """Embeddings e5 gọi hoàn toàn qua OpenRouter (/v1/embeddings).

    Cả index (``embed_documents``) lẫn retrieve (``embed_query``) đều qua API,
    không nạp model local. Giữ tiền tố ``query:`` / ``passage:`` mà e5 yêu cầu.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        if self._initialized:
            return
        self.model_name = model_name
        self.client = OpenAI(
            api_key=LLMConfig.OPENROUTER_API_KEY,
            base_url=LLMConfig.OPENROUTER_BASE_URL,
        )
        logger.info(f"Embeddings via OpenRouter: {model_name}")
        self._initialized = True

    def _embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        out: List[List[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            resp = self.client.embeddings.create(model=self.model_name, input=batch)
            # Sắp theo index để chắc chắn đúng thứ tự với input.
            out.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
        return out

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed([f"passage: {t}" for t in texts])

    def embed_query(self, text: str) -> List[float]:
        return self._embed([f"query: {text}"])[0]


embeddings = PropertyEmbeddingService()

vector_store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=VectorDBConfig.connection_string(),
    use_jsonb=True,
    distance_strategy=DistanceStrategy.COSINE,
)
