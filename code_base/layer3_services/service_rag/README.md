# Service 1 — RAG Service (Pinecone)

**Stack:** FastAPI · LangChain · Pinecone · sentence-transformers · **Ollama** (default insight LLM) · optional llama.cpp (GGUF)

---

## Quick start (Docker)

1. Set `PINECONE_API_KEY` (and index settings) in `.env` or `docker/secrets/rag.env` (see `docker/examples/rag.env.example`).

2. **Insight LLM (default: Ollama Cloud)** — set `OLLAMA_HOST=https://ollama.com`, `OLLAMA_API_KEY`, and `OLLAMA_MODEL`. **Legacy:** for `RAG_LLM_BACKEND=llama_cpp`, put a GGUF under `../../../models` and set `MODEL_PATH`.

3. Seed Pinecone once (or rely on `RAG_AUTO_SEED=true`):

   ```bash
   docker compose run --rm rag python seed_pinecone.py
   ```

4. Start:

   ```bash
   docker compose up --build
   ```

5. Test:

   ```bash
   curl -X POST http://localhost:8001/query \
     -H "Content-Type: application/json" \
     -d '{"description": "3-bedroom apartment, Tel Aviv, sea view, renovated kitchen"}'
   ```

**Local (no Docker):** `pip install -r requirements.txt` then `python -m uvicorn main:app --host 0.0.0.0 --port 8001` from this directory (after `.env` and seed).

---

## Endpoint

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| POST | `/query` | Retrieve similar listings + generate insight |

### POST /query

**Request body:**
```json
{ "description": "3-bedroom apartment in Tel Aviv, renovated, sea view" }
```

**Response:**
```json
{
  "similar_listings": [
    {
      "id": "LST-015",
      "title": "Sea-View 3BR, Bat Yam Boardwalk",
      "description": "...",
      "similarity_score": 0.87
    }
  ],
  "insight": "The submitted listing shares strong similarities with LST-015...",
  "retrieved_count": 3
}
```

---

## Setup

### 1. Get a Pinecone API Key

1. Sign up at [https://app.pinecone.io](https://app.pinecone.io)
2. Create an API key from the Pinecone dashboard
3. Copy `docker/examples/rag.env.example` → `docker/secrets/rag.env`, **or** for local runs in this folder: `cp .env.example .env`

### 2. Ollama insight LLM (default)

Set in `rag.env` (or `.env` for local runs):

| Variable | Example | Description |
|----------|---------|-------------|
| `RAG_LLM_BACKEND` | `ollama` | Default: call Ollama HTTP API |
| `OLLAMA_HOST` | `https://ollama.com` | Cloud or local server |
| `OLLAMA_API_KEY` | *(key)* | Required when using Ollama Cloud |
| `OLLAMA_MODEL` | `gpt-oss:120b` | Model id |

### 3. (Optional) Legacy GGUF via llama.cpp

Set `RAG_LLM_BACKEND=llama_cpp`, download a GGUF into `../../../models`, set `MODEL_PATH`, and mount `./models:/app/models:ro` in Docker Compose.

### 4. Seed Pinecone

Run once before starting the service (creates serverless index + synthetic listings if empty).

```bash
docker compose run --rm rag python seed_pinecone.py
```

Or locally: `pip install -r requirements.txt && python seed_pinecone.py`

> **Note:** The service auto-seeds on first startup if `RAG_AUTO_SEED=true` (default).

### 5. Start the service

```bash
docker compose up --build
```

API: `http://localhost:8001`

---

## Testing

```bash
curl http://localhost:8001/health

curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"description": "3-bedroom apartment, Tel Aviv, sea view, renovated kitchen, 110sqm"}'

open http://localhost:8001/docs
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PINECONE_API_KEY` | *(required)* | Pinecone API key |
| `PINECONE_INDEX_NAME` | `property-listings` | Index name |
| `PINECONE_CLOUD` | `aws` | Serverless cloud |
| `PINECONE_REGION` | `us-east-1` | Region |
| `RAG_LLM_BACKEND` | `ollama` | `ollama` or `llama_cpp` |
| `OLLAMA_HOST` | `https://ollama.com` | Ollama base URL |
| `OLLAMA_API_KEY` | *(empty)* | Required for Ollama Cloud when `RAG_LLM_BACKEND=ollama` |
| `OLLAMA_MODEL` | `gpt-oss:120b` | Model for insights |
| `MODEL_PATH` | *(see example)* | GGUF path — **only** for `llama_cpp` |
| `RAG_LLM_THREADS` | `1` | CPU threads for llama.cpp |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embeddings |
| `TOP_K` | `3` | Top similar listings |
| `RAG_AUTO_SEED` | `true` | Auto-seed when index empty |

---

## Prompt engineering

RAG prompt: `rag_pipeline.py` → `RAG_PROMPT`.  
Log iterations in `../../layer2_n8n/prompt_logs/rag_prompt_log.md`.

---

## EC2 / Docker run (single container)

```bash
docker build -t property-rag-pinecone .
docker run -d \
  -p 8001:8000 \
  -e PINECONE_API_KEY=your-key-here \
  -e PINECONE_INDEX_NAME=property-listings \
  -e OLLAMA_HOST=https://ollama.com \
  -e OLLAMA_API_KEY=your-ollama-key \
  -e OLLAMA_MODEL=gpt-oss:120b \
  --name property_rag_pinecone \
  property-rag-pinecone
```

Restrict inbound port 8001 to trusted callers (e.g. n8n).

---

## Key differences from ChromaDB variant

| Aspect | service_rag_chroma | service_rag (Pinecone) |
|--------|-------------------|------------------------|
| Vector store | ChromaDB (local) | Pinecone (cloud-managed) |
| Persistence | Local `chroma_db/` directory | Pinecone serverless index |
| Docker volumes | GGUF + chroma_db (typical) | Optional GGUF **only** if `llama_cpp` |
| Similarity metric | L2 distance → converted to 0-1 | Cosine similarity (native) |
| Env config | `CHROMA_PATH` | `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, Ollama vars |
| Seed script | `seed_chroma.py` | `seed_pinecone.py` |
| Inspect script | `inspect_chroma.py` | `inspect_pinecone.py` |
