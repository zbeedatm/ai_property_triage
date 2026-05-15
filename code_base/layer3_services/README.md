# Layer 3 — Microservices

FastAPI services called by n8n: **RAG** (8001), **Image** (8002), **Guardrails** (8003), **LangGraph** (8004).

Each folder has its own `README.md`, `Dockerfile`, and `docker-compose.yml`.

---

## Run all services with Docker

From this directory (`code_base/layer3_services`):

```bash
cd service_rag && docker compose up -d
cd ../service_image && docker compose up -d
cd ../service_guardrails && docker compose up -d
cd ../service_langgraph && docker compose up --build -d
```

Verify:

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

Before RAG answers queries, seed the vector store (Pinecone or Chroma — see the RAG README you use).

---

## Run one service locally (no Docker)

From that service’s folder:

```bash
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port <port>
```

Use the port documented in that service’s README (`8001`–`8004`). Prefer a dedicated virtual environment.

---

## Service README index

| Service | README |
|---------|--------|
| RAG (Pinecone) | [service_rag/README.md](service_rag/README.md) |
| RAG (Chroma + GGUF) | [service_rag_chroma/README.md](service_rag_chroma/README.md) |
| Image analyser | [service_image/README.md](service_image/README.md) |
| Guardrails | [service_guardrails/README.md](service_guardrails/README.md) |
| LangGraph agent | [service_langgraph/README.md](service_langgraph/README.md) |
