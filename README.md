# KLTN ChatBot — ChatBot tư vấn Bất động sản và tài chính mua nhà
---

## Tính năng chính

- **Phân tích & thống kê** dữ liệu BĐS (giá trung bình, ranking quận/phường, phân bố, xu hướng) kèm **biểu đồ** (bar, line, pie, histogram, stacked bar…).
- **Tư vấn tài chính**: tính khả năng vay, trả góp, LTV, so sánh các kịch bản vay.
- **Gợi ý tin đăng** cụ thể theo điều kiện lọc (quận/phường, giá, diện tích, loại hình) bằng **RAG**.
---

## Cấu trúc thư mục

```
KLTN_ChatBot/
├── backend/        # FastAPI app + auth (JWT)
├── src/
│   ├── agents/     # Supervisor + 3 sub-agent
│   ├── prompts/    # System prompt từng agent
│   ├── tools/      # SQL, finance, RAG, calculator…
│   ├── memory/     # short_memory (checkpointer), long_memory (store)
│   └── llm/        # OpenAIClient (wrapper)
├── rag/            # embedding, index, prepare vector store
├── data/           # crawl, xử lý, ingest dữ liệu + database.py
├── configs/        # cấu hình DB & LLM
├── frontend/       # html / css / js
├── evaluation/     # đánh giá chất lượng 
├── tests/          # pytest
├── docker/        
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---


