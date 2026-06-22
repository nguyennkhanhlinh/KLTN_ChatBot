import json
import os
import sys
import time

import psycopg
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configs.db import VectorDBConfig
from rag.embedding import COLLECTION_NAME, embeddings, vector_store

JSON_PATH = os.path.join(os.path.dirname(__file__), "descriptions_clean_1.json")

CHUNK_SIZE    = 1000
CHUNK_OVERLAP = 100

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n", ". ", " ", ""],
)

def _build_docs(item: dict) -> list[Document]:
    chunks = _splitter.split_text(item.get("mo_ta", ""))
    return [
        Document(page_content=chunk, metadata={"ma_code": item.get("ma_code")})
        for chunk in chunks
    ]


def _chunk_items(items: list[dict]) -> list[Document]:
    docs = []
    for item in items:
        if item.get("mo_ta"):
            docs.extend(_build_docs(item))
    return docs


def _build_chunk_ids(chunks: list[Document]) -> list[str]:
    seen: dict[str, int] = {}
    ids = []
    for c in chunks:
        ma = c.metadata.get("ma_code") or "unknown"
        n = seen.get(ma, 0)
        seen[ma] = n + 1
        ids.append(f"{ma}-{n}")
    return ids

def _existing_chunk_count() -> int:
    with psycopg.connect(
        host=VectorDBConfig.HOST, port=VectorDBConfig.PORT,
        dbname=VectorDBConfig.NAME, user=VectorDBConfig.USER,
        password=VectorDBConfig.PASSWORD,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.langchain_pg_collection')")
            if cur.fetchone()[0] is None:
                return 0
            cur.execute(
                "SELECT COUNT(*) FROM langchain_pg_embedding e "
                "JOIN langchain_pg_collection c ON c.uuid = e.collection_id "
                "WHERE c.name = %s",
                (COLLECTION_NAME,),
            )
            return int(cur.fetchone()[0])


def index_from_json(json_path: str = JSON_PATH, force: bool = False) -> int:
    """Load tin đăng từ JSON → chunk → embed → upsert vào pgvector.
    Skip nếu collection đã có đúng số chunks (force=True để bỏ qua check)."""
    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    items = [i for i in items if (i.get("mo_ta") or "").strip()]
    print(f"Loaded {len(items)} tin từ {json_path}")

    chunks = _chunk_items(items)
    print(f"Đã chunk thành {len(chunks)} đoạn")

    if not force:
        existing = _existing_chunk_count()
        if existing > 0:
            print(f"Skip indexing: đã có {existing} chunks trong pgvector.")
            return existing

    texts     = [c.page_content for c in chunks]
    metadatas = [c.metadata for c in chunks]
    ids       = _build_chunk_ids(chunks)

    t0 = time.time()
    embs = embeddings.embed_documents(texts)
    t1 = time.time()

    vector_store.add_embeddings(texts=texts, embeddings=embs, metadatas=metadatas, ids=ids)
    t2 = time.time()

    print(f"Embedding: {t1 - t0:.2f}s  ({len(texts)} chunks, {len(texts) / max(t1 - t0, 1e-9):.1f}/s)")
    print(f"Insert   : {t2 - t1:.2f}s")
    print(f"Total    : {t2 - t0:.2f}s")
    return len(chunks)


if __name__ == "__main__":
    n = index_from_json(force=True)
    print(f"Done. Index xong {n} chunks.")
