# AI Property Triage System

A multi-layer AI pipeline that accepts real estate listing submissions,
validates them, retrieves similar past listings, analyses property images,
and returns a structured triage report.

**Prompts registry:** consolidated system prompts and classifier instructions (WebUI, n8n `flow.json`, Guardrails, RAG, LangGraph) live in [docs/PROMPTS.md](docs/PROMPTS.md).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 — WebUI  (Gradio + Ollama Cloud/local)  port 7860 │
│   Tab 1: Real estate chat assistant                         │
│   Tab 2: Listing submission form → n8n webhook POST         │
└────────────────────────┬────────────────────────────────────┘
                         │ POST /webhook/property-triage
┌────────────────────────▼────────────────────────────────────┐
│  Layer 2 — n8n Orchestration  port 5678                     │
│   Node 1: Webhook Trigger                                   │
│   Node 2: Guardrails Input Check     ──► 8003               │
│   Node 3: Pass / Reject Router                              │
│   Node 4: Information Extractor (LLM)                       │
│   Node 5: AI Agent (LLM + 3 tools)  ──► 8001 8002 8004     │
│   Node 6: Final Report LLM Chain                            │
│   Node 7: Guardrails Output Check    ──► 8003               │
│   Node 8: Property Type Router → Residential / Commercial   │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP calls
┌────────────────────────▼────────────────────────────────────┐
│  Layer 3 — EC2 Microservices (Docker, FastAPI)              │
│   service_rag         port 8001  Pinecone RAG + Ollama insight │
│   service_image       port 8002  PyTorch ResNet-50          │
│   service_guardrails  port 8003  NeMo Guardrails            │
│   service_langgraph   port 8004  LangGraph StateGraph       │
└─────────────────────────────────────────────────────────────┘
```

---

## Folder structure

```
project-root/
├── layer1_webui/
│   ├── app.py                  Gradio UI (two tabs)
│   ├── chat_client.py          Ollama client + system prompt
│   ├── webhook_client.py       n8n POST + report formatter
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── layer2_n8n/
│   ├── flow.json               Import this into n8n
│   ├── docker-compose.yml      Self-host n8n locally
│   ├── .env.example            n8n / compose environment template
│   ├── test_pipeline.py        End-to-end webhook tests
│   └── prompt_logs/
│       ├── rag_prompt_log.md
│       ├── extractor_prompt_log.md
│       ├── agent_prompt_log.md
│       ├── guardrails_prompt_log.md
│       └── ollama_prompt_log.md
│
└── layer3_ec2/
    ├── service_rag/
    │   ├── main.py             FastAPI POST /query
    │   ├── rag_pipeline.py     Pinecone + embeddings + Ollama insight
    │   ├── seed_chroma.py      Populate DB with 20 listings
    │   ├── Dockerfile
    │   └── docker-compose.yml
    │
    ├── service_image/
    │   ├── main.py             FastAPI POST /analyse
    │   ├── model.py            ResNet-50 dual-head model
    │   ├── dataset.py          Mock dataset generator + PyTorch Dataset
    │   ├── train.py            Transfer-learning training script
    │   ├── Dockerfile
    │   └── docker-compose.yml
    │
    ├── service_guardrails/
    │   ├── main.py             FastAPI POST /check/input + /check/output
    │   ├── actions.py          NeMo @action classifiers (3 prompts)
    │   ├── rails/
    │   │   ├── config.yml      NeMo Guardrails config
    │   │   └── main.co         Colang rail definitions
    │   ├── test_rails.py       20-case automated test suite
    │   ├── Dockerfile
    │   └── docker-compose.yml
    │
    └── service_langgraph/
        ├── main.py             FastAPI POST /agent/run
        ├── agent.py            LangGraph StateGraph (planner→executor→synthesiser)
        ├── tools.py            RAG + Image tool wrappers
        ├── benchmark.py        10-query accuracy benchmark
        ├── Dockerfile
        └── docker-compose.yml
```

---

## Port map

| Service | Port | Technology |
|---------|------|-----------|
| WebUI | 7860 | Gradio |
| n8n | 5678 | n8n |
| RAG | 8001 | FastAPI + Pinecone + Ollama (insight) |
| Image Analyser | 8002 | FastAPI + PyTorch ResNet-50 |
| Guardrails | 8003 | FastAPI + NeMo Guardrails |
| LangGraph Agent | 8004 | FastAPI + LangGraph |

---

## Quick start

### WebUI only (Layer 1)

Use this to try **chat** quickly. The **Submit listing** tab still needs n8n and Layer 3 running.

**Ollama Cloud:** create an API key at [ollama.com/settings/keys](https://ollama.com/settings/keys), then in `code_base/layer1_webui/.env` (copy from `.env.example`) set `OLLAMA_HOST=https://ollama.com`, `OLLAMA_API_KEY`, and `OLLAMA_MODEL` (e.g. `gpt-oss:120b`).

**Local Ollama:** run `ollama serve`, set `OLLAMA_HOST=http://localhost:11434`, pull your model, leave `OLLAMA_API_KEY` empty.

**Run locally**

```bash
cd code_base/layer1_webui
pip install -r requirements.txt && python app.py
```

Open http://localhost:7860

**Run with Docker**

```bash
cd code_base/layer1_webui
docker compose up --build
```

Uses `docker/secrets/webui.env` when present (see `docker/examples/webui.env.example`). For Ollama on the host from Docker, use `OLLAMA_HOST=http://host.docker.internal:11434`.

More detail: `code_base/layer1_webui/README.md`.

### All Layer 3 services (Docker)

From `code_base/layer3_services/` start the four APIs (after env keys and RAG seed — see each service README):

```bash
cd service_rag && docker compose up -d
cd ../service_image && docker compose up -d
cd ../service_guardrails && docker compose up -d
cd ../service_langgraph && docker compose up --build -d
```

Health checks:

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

Overview and per-service setup: `code_base/layer3_services/README.md`.

---

## Full startup sequence

```bash
# ── Step 1: Ollama (chat + RAG insights) ────────────────────
# Recommended: Ollama Cloud — set OLLAMA_HOST=https://ollama.com,
# OLLAMA_API_KEY, and OLLAMA_MODEL in docker/secrets/*.env (see docker/examples/).
# Alternative: local Ollama — ollama pull <model> && ollama serve on port 11434.

# ── Step 2: Layer 3 — services ──────────────────────────────

# RAG — seed Pinecone once, then start (requires PINECONE_* and OLLAMA_* in .env)
cd code_base/layer3_services/service_rag
docker compose run --rm rag python seed_pinecone.py
docker compose up -d

# Image Analyser — generate mock data, train, then start
cd ../service_image
python dataset.py --data-dir ./data
python train.py --data-dir ./data --output ./checkpoints/model.pth --epochs 10
docker compose up -d

# Guardrails
cd ../service_guardrails
# Set OPENAI_API_KEY in .env first
docker compose up -d

# LangGraph Agent
cd ../service_langgraph
docker compose up -d

# ── Step 3: Layer 2 — n8n ────────────────────────────────────
cd ../../layer2_n8n
# Option A: use n8n Cloud → import flow.json manually
# Option B: self-host
docker compose up -d
# Then: open http://localhost:5678 → import flow.json → activate

# ── Step 4: Layer 1 — WebUI ──────────────────────────────────
cd ../layer1_webui
# Edit .env: set N8N_WEBHOOK_URL
docker compose up --build

# ── Step 5: Verify everything ────────────────────────────────
curl http://localhost:8001/health   # RAG
curl http://localhost:8002/health   # Image Analyser
curl http://localhost:8003/health   # Guardrails
curl http://localhost:8004/health   # LangGraph Agent

python layer2_n8n/test_pipeline.py  # End-to-end pipeline test

open http://localhost:7860          # WebUI
```

---

## Prompt iteration checklist

Complete 5 iterations minimum for each surface before final submission:

- [ ] `prompt_logs/rag_prompt_log.md` — RAG retrieval prompt
- [ ] `prompt_logs/extractor_prompt_log.md` — n8n Information Extractor
- [ ] `prompt_logs/agent_prompt_log.md` — n8n AI Agent + tool descriptions
- [ ] `prompt_logs/guardrails_prompt_log.md` — NeMo input + output rail prompts
- [ ] `prompt_logs/ollama_prompt_log.md` — Ollama real estate system prompt

---

## EC2 deployment checklist

- [ ] Launch EC2 (instance sizing: see README_EC2.md), install Docker
- [ ] Configure `docker/secrets/*.env` (Pinecone, Ollama Cloud `OLLAMA_API_KEY`, Gemini, etc.)
- [ ] `docker compose` / `docker build` per deployment layout (see README_EC2.md)
- [ ] Restrict security group: allow inbound 8001–8004 from n8n IP only
- [ ] Update n8n env vars: swap `localhost` → EC2 public IP where needed
- [ ] Re-run `test_pipeline.py` against live webhook
