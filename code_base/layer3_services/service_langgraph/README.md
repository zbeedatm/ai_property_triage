# Service 4 — LangGraph Agent

**Stack:** FastAPI · LangGraph · LangChain · GPT-4o-mini (or local Mistral 7B)

---

## Endpoint

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| POST | `/agent/run` | Run the full multi-step agent |

### POST /agent/run

**Request:**
```json
{
  "description": "3-bedroom apartment in Tel Aviv, 110sqm, renovated kitchen, sea view. Asking 4.2M ILS.",
  "image_urls": [
    "https://example.com/kitchen.jpg",
    "https://example.com/living_room.jpg"
  ]
}
```

**Response:**
```json
{
  "report": {
    "property_type": "apartment",
    "routing_decision": "residential",
    "location": "Tel Aviv",
    "price_ils": 4200000,
    "num_rooms": 3,
    "key_features": ["renovated kitchen", "sea view", "110sqm"],
    "image_scores": [
      { "url": "...", "room_type": "kitchen", "condition_score": 4.1, "confidence": 0.83 }
    ],
    "similar_listings": ["Sea-View 3BR, Bat Yam Boardwalk", "Bright 3BR Apartment, Tel Aviv — Florentin"],
    "rag_insight": "The submitted listing shares strong similarities with...",
    "enrichment_notes": "This property is competitively priced relative to similar sea-view apartments...",
    "confidence": 0.87
  },
  "rag_retrieved": 3,
  "images_analysed": 2,
  "error": null
}
```

---

## Agent graph

```
[planner] → [tool_executor] → [planner] → ... → [synthesiser] → END
                ↑___________________|
              (loops until all tools called)
```

**planner** — decides which tool to call next (or signals DONE)  
**tool_executor** — calls the tool, stores result in state  
**synthesiser** — writes the final structured JSON report  

---

## Setup

### 1. Ensure sibling services are running

```bash
# RAG service on port 8001 — choose ONE backend:

# Option A: Pinecone (service_rag)
cd ../service_rag && docker compose up -d

# Option B: ChromaDB (service_rag_chroma)
cd ../service_rag_chroma && docker compose up -d

# Image Analyser on port 8002
cd ../service_image && docker compose up -d
```

### 2. Set environment variables

```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY
```

### 3. Start the service

```bash
docker compose up --build
```

Available at `http://localhost:8004`.

### 4. Run the benchmark

```bash
python benchmark.py --base-url http://localhost:8004
```

Runs 10 queries and checks RAG tool calls, image tool calls, routing decisions,
and report field completeness. Log results as Version 1 in
`../../layer2_n8n/prompt_logs/agent_prompt_log.md`.

---

## Iterating the prompts

Two prompts live in `agent.py`:

| Constant | Node | What it controls |
|----------|------|-----------------|
| `PLANNER_SYSTEM` | planner | Which tools to call and when to stop |
| `SYNTHESISER_SYSTEM` | synthesiser | Output JSON schema and grounding rules |

Edit → restart container → re-run benchmark → log results.

---

## Switching to local LLM

```bash
# In one terminal — start llama-cpp server
python -m llama_cpp.server \
  --model ../../../models/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  --port 8080

# In .env
LLM_PROVIDER=local
LOCAL_LLM_URL=http://localhost:8080/v1
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | `openai`, `gemini`, or `local` |
| `OPENAI_API_KEY` | — | Required when LLM_PROVIDER=openai |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `GOOGLE_API_KEY` | — | Required when LLM_PROVIDER=gemini |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `LOCAL_LLM_URL` | `http://localhost:8080/v1` | llama-cpp server URL |
| **`RAG_BACKEND`** | **`pinecone`** | **`pinecone` (service_rag) or `chroma` (service_rag_chroma)** |
| `RAG_PINECONE_URL` | `http://127.0.0.1:8001` | URL for the Pinecone RAG service |
| `RAG_CHROMA_URL` | `http://127.0.0.1:8001` | URL for the ChromaDB RAG service |
| `RAG_SERVICE_URL` | *(auto)* | Explicit override — skips RAG_BACKEND routing |
| `IMAGE_SERVICE_URL` | `http://localhost:8002` | Image Analyser URL |
| `HTTP_TIMEOUT` | `30` | Seconds before tool HTTP calls time out |

### Switching RAG backend

Both RAG services expose the same `POST /query` API. To switch:

```bash
# In .env — use Pinecone (default)
RAG_BACKEND=pinecone

# In .env — use ChromaDB
RAG_BACKEND=chroma
```

If both services run on different hosts/ports, set `RAG_PINECONE_URL` and `RAG_CHROMA_URL` separately.
You can also bypass the flag entirely by setting `RAG_SERVICE_URL` directly.

---

## Port map — all Layer 3 services

| Service | Host port |
|---------|-----------|
| RAG | 8001 |
| Image Analyser | 8002 |
| Guardrails | 8003 |
| LangGraph Agent | 8004 |

---

## EC2 Deployment

```bash
docker build -t property-langgraph-agent .
docker run -d \
  -p 8004:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e RAG_SERVICE_URL=http://<EC2-PRIVATE-IP>:8001 \
  -e IMAGE_SERVICE_URL=http://<EC2-PRIVATE-IP>:8002 \
  --name property_langgraph_agent \
  property-langgraph-agent
```
