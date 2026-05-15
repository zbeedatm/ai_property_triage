# Service 1 — RAG Service

**Stack:** FastAPI · LangChain · Llama.cpp (Mistral 7B GGUF) · ChromaDB · sentence-transformers

---

## Quick start (Docker)

1. **GGUF model** — download into `../../../models` (repo root `models/`), e.g.:

   ```bash
   pip install huggingface_hub
   huggingface-cli download TheBloke/Mistral-7B-Instruct-v0.2-GGUF \
     mistral-7b-instruct-v0.2.Q4_K_M.gguf --local-dir ../../../models
   ```

2. **Seed ChromaDB** (once):

   ```bash
   docker compose run --rm rag python seed_chroma.py
   ```

3. **Start**

   ```bash
   docker compose up --build
   ```

4. **Test**

   ```bash
   curl -X POST http://localhost:8001/query \
     -H "Content-Type: application/json" \
     -d '{"description": "3-bedroom apartment, Tel Aviv, sea view, renovated kitchen"}'
   ```

**Local (no Docker):** see **Setup** below — `pip install -r requirements.txt`, `python seed_chroma.py`, then `python -m uvicorn main:app --host 0.0.0.0 --port 8001`.

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

### 1. Download the GGUF model

```bash
mkdir -p models
# Option A — HuggingFace CLI
pip install huggingface_hub
huggingface-cli download \
  TheBloke/Mistral-7B-Instruct-v0.2-GGUF \
  mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  --local-dir ../../../models

# Option B — direct wget (get URL from HuggingFace model page)
wget -P models/ <URL_TO_GGUF_FILE>
```

### 2. Seed ChromaDB

Run this once before starting the service.  
It creates the `chroma_db/` directory and populates it with 20 synthetic listings.

```bash
# Inside the container:
docker compose run --rm rag python seed_chroma.py

# Or locally (if running without Docker):
pip install -r requirements.txt
python seed_chroma.py --chroma-path ./chroma_db
```

### 3. Start the service

```bash
docker compose up --build
```

The API will be available at `http://localhost:8001`.

---

## Testing

```bash
# Health check
curl http://localhost:8001/health

# Query
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"description": "3-bedroom apartment, Tel Aviv, sea view, renovated kitchen, 110sqm"}'

# Interactive docs
open http://localhost:8001/docs
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_PATH` | `./chroma_db` | Path to ChromaDB storage directory |
| `MODEL_PATH` | `../../../models/mistral-7b-instruct-v0.2.Q4_K_M.gguf` | Path to GGUF file |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model name |
| `TOP_K` | `3` | Number of similar listings to retrieve |

Copy `.env.example` to `.env` and adjust as needed.

---

## Prompt Engineering

The RAG prompt lives in `rag_pipeline.py` → `RAG_PROMPT`.  
Log all iterations in `../../layer2_n8n/prompt_logs/rag_prompt_log.md`.

---

## EC2 Deployment

```bash
# On EC2 — after git clone and placing the GGUF model:
docker build -t property-rag .
docker run -d \
  -p 8001:8000 \
  -v $(pwd)/models:/app/models:ro \
  -v $(pwd)/chroma_db:/app/chroma_db \
  --name property_rag \
  property-rag
```

Restrict the EC2 security group inbound rule on port 8001 to your n8n IP only.
