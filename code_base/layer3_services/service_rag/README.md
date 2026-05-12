# Service 1 — RAG Service (Pinecone)

**Stack:** FastAPI · LangChain · Llama.cpp (Mistral 7B GGUF) · Pinecone · sentence-transformers

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
3. Copy `.env` and fill in your `PINECONE_API_KEY`

### 2. Download the GGUF model

```bash
mkdir -p ../../models
# Option A — HuggingFace CLI
pip install huggingface_hub
huggingface-cli download \
  TheBloke/Mistral-7B-Instruct-v0.2-GGUF \
  mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  --local-dir ../../../models

# Option B — direct wget (get URL from HuggingFace model page)
wget -P models/ <URL_TO_GGUF_FILE>
```

### 3. Seed Pinecone

Run this once before starting the service.
It creates a serverless Pinecone index and populates it with 20 synthetic listings.

```bash
# Inside the container:
docker compose run --rm rag python seed_pinecone.py

# Or locally (if running without Docker):
pip install -r requirements.txt
python seed_pinecone.py
```

> **Note:** The service auto-seeds on first startup if `RAG_AUTO_SEED=true` (default).

### 4. Start the service

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
| `PINECONE_API_KEY` | *(required)* | Your Pinecone API key |
| `PINECONE_INDEX_NAME` | `property-listings` | Pinecone index name |
| `PINECONE_CLOUD` | `aws` | Cloud provider for serverless index |
| `PINECONE_REGION` | `us-east-1` | Region for serverless index |
| `MODEL_PATH` | `../../../models/mistral-7b-instruct-v0.2.Q4_K_M.gguf` | Path to GGUF file |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model name |
| `TOP_K` | `3` | Number of similar listings to retrieve |
| `RAG_AUTO_SEED` | `true` | Auto-seed Pinecone on startup if index is empty |
| `RAG_LLM_THREADS` | `1` | Number of CPU threads for llama.cpp |

Copy `.env` and adjust as needed.

---

## Prompt Engineering

The RAG prompt lives in `rag_pipeline.py` → `RAG_PROMPT`.
Log all iterations in `../../layer2_n8n/prompt_logs/rag_prompt_log.md`.

---

## EC2 Deployment

```bash
# On EC2 — after git clone and placing the GGUF model:
docker build -t property-rag-pinecone .
docker run -d \
  -p 8001:8000 \
  -v $(pwd)/models:/app/models:ro \
  -e PINECONE_API_KEY=your-key-here \
  -e PINECONE_INDEX_NAME=property-listings \
  --name property_rag_pinecone \
  property-rag-pinecone
```

Restrict the EC2 security group inbound rule on port 8001 to your n8n IP only.

---

## Key differences from ChromaDB variant

| Aspect | service_rag_chroma | service_rag (Pinecone) |
|--------|-------------------|------------------------|
| Vector store | ChromaDB (local) | Pinecone (cloud-managed) |
| Persistence | Local `chroma_db/` directory | Pinecone serverless index |
| Docker volumes | GGUF model + chroma_db | GGUF model only |
| Similarity metric | L2 distance → converted to 0-1 | Cosine similarity (native) |
| Env config | `CHROMA_PATH` | `PINECONE_API_KEY`, `PINECONE_INDEX_NAME` |
| Seed script | `seed_chroma.py` | `seed_pinecone.py` |
| Inspect script | `inspect_chroma.py` | `inspect_pinecone.py` |
