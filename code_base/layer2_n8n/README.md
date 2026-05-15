# Layer 2 — n8n Orchestration

**Stack:** n8n (self-hosted or cloud) · Gemini / GPT-4o LM nodes · HTTP Request tool nodes

---

## Flow overview

```
Webhook → Guardrails Input → [reject?] → Extractor → AI Agent → LLM Chain
                                                          ↑ tools:
                                                          ├─ RAG Query       (8001)
                                                          ├─ Image Analyser  (8002)
                                                          └─ LangGraph Agent (8004)
       → Guardrails Output → [flag?] → Human Review webhook (optional) → Respond pending review
                                    → Property Router → Residential respond
                                                      → Commercial respond
```

### Node reference

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1 | Webhook Trigger | Webhook | Entry point — `POST /webhook/property-triage` |
| 2 | Guardrails Input Check | HTTP Request | `POST /check/input` — validates listing is genuine |
| 3 | Pass / Reject Router | IF | Blocks invalid submissions with HTTP 422 |
| 4 | Information Extractor | LangChain Extractor | Pulls structured fields from listing text |
| 5 | AI Agent | LangChain Agent | Calls RAG, Image, and LangGraph tools |
| 6 | Final Report LLM Chain | LLM Chain | Cleans and validates the agent JSON output |
| 7 | Guardrails Output Check | HTTP Request | `POST /check/output` — audits report |
| 7b | Output Router | IF | `passed` → property router; else → human-review path |
| 7c | Human Review Webhook | HTTP Request | `POST` to `HUMAN_REVIEW_WEBHOOK_URL` + `/review` when URL is origin-only (`continueOnFail`) |
| 7d | Respond human review pending | Respond to Webhook | Returns JSON for Web UI (`human_review_required`, draft `report`) |
| 8 | Property Type Router | Switch | Splits residential vs commercial response paths |

---

## Setup

### Option A — n8n Cloud (recommended)

1. Create a free account at [cloud.n8n.io](https://cloud.n8n.io)
2. Open your workspace → **Workflows** → **Import from file**
3. Upload `flow.json`
4. Set environment variables (Settings → Environment Variables):

```
RAG_URL            = http://<EC2-IP>:8001
IMAGE_URL          = http://<EC2-IP>:8002
GUARDRAILS_URL     = http://<EC2-IP>:8003
LANGGRAPH_URL      = http://<EC2-IP>:8004
HUMAN_REVIEW_WEBHOOK_URL = <your-slack-or-review-endpoint>
```

5. Add credentials (Settings → Credentials):
   - **OpenAI API** — used by Node 4 (Extractor) and Node 5 (Agent)
   - Or **Google Gemini API** — swap the LM node model in Node 4 and 5

6. Open the flow → click **Activate** (top right toggle)
7. Copy the webhook URL shown — paste it into `layer1_webui/.env` as `N8N_WEBHOOK_URL`

### Option B — Self-hosted (Docker)

```bash
cd layer2_n8n
cp .env.example .env
# Edit .env: set service URLs, credentials

docker compose up -d
# n8n is now at http://localhost:5678

# Import the flow
# UI: Workflows → Import → select flow.json
# Or via API:
curl -u admin:changeme \
  -X POST http://localhost:5678/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d @flow.json
```

### Option C — n8n on the host (`n8n start` / `npx n8n`)

n8n must see **`N8N_BLOCK_ENV_ACCESS_IN_NODE=false`** or expressions like `$env.RAG_URL` are blocked (“access to env vars denied”). Docker Compose sets this for you; a plain local process does **not** unless you export it.

**Layer 3 URLs:** `.env.example` uses **`host.docker.internal`** so **n8n-in-Docker** can reach services on your machine. If **n8n runs on the host**, that hostname usually causes **connection refused** to Node 2 / HTTP tools. The **`run-n8n-local`** scripts set **`http://127.0.0.1:PORT`** when your env is empty or still points at `host.docker.internal`, and rewrite `//localhost` → `//127.0.0.1` to avoid IPv6 `::1` quirks on Windows.

**Windows (PowerShell)** — pick **one** of these:

```powershell
# A) From repo root (AI_Property_Triage) — easiest if you are not inside layer2_n8n:
.\run-n8n-local.ps1
```

```powershell
# B) From the Layer 2 folder (where the script file lives):
cd code_base\layer2_n8n
.\run-n8n-local.ps1
```

```powershell
# C) From anywhere — full path (replace with your clone location):
& "D:\path\to\AI_Property_Triage\code_base\layer2_n8n\run-n8n-local.ps1"
```

If you see **“running scripts is disabled”**: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` then run the script again.

Or skip the script and run:

`$env:N8N_BLOCK_ENV_ACCESS_IN_NODE='false'; n8n start`

**macOS / Linux:**

```bash
chmod +x run-n8n-local.sh
./run-n8n-local.sh
```

Or: `N8N_BLOCK_ENV_ACCESS_IN_NODE=false n8n start`

**Editor vs execution:** Some n8n versions still show an error when **previewing** `$env` in the UI even when the flag is off. **Execute the node or full workflow** to confirm URLs resolve.

---

## Wiring the AI Agent tools (Node 5)

After importing the flow, Node 5 needs its three tool sub-nodes connected:

1. In the n8n canvas, open **Node 5 — AI Agent**
2. Click **Add Tool** three times and select **HTTP Request** for each
3. Name and configure each tool:

| Tool name in agent | Node to link | URL env var | Description to enter |
|---|---|---|---|
| `rag_query` | Tool — RAG Query | `RAG_URL` + `/query` in flow | Query the property knowledge base with the listing description |
| `analyse_images` | Tool — Image Analyser | `IMAGE_URL` + `/analyse` in flow | Classify room types and score condition from image URLs |
| `langgraph_agent` | Tool — LangGraph Agent | `LANGGRAPH_URL` + `/agent/run` in flow | Run multi-step agent analysis on the listing |

> **Note:** The `flow.json` includes these tool node definitions. n8n's import
> may require you to re-link them manually depending on your n8n version.
> The node parameters are all pre-filled in the JSON.
>
> **Expression syntax:** Layer 3 bases use `String($env...).trim().replace(/\/+$/, '').replace(/\s+/g, '') + '/…'`. Human review (Node 7c) trims/sanitizes then **appends `/review` only when the URL has no path** (origin only, e.g. `http://host:9090`); full webhook URLs (e.g. Slack) with a path are left unchanged.

---

## LM node configuration (Node 4, Node 5, and Node 6)

These nodes need a Language Model sub-node attached:

1. Click the **+** on the LM slot of Node 4 (Extractor), Node 5 (Agent), and Node 6 (Final Report LLM Chain)
2. Choose **OpenAI Chat Model** or **Google Gemini Chat Model**
3. Select the credential you added
4. Recommended models:
   - Node 6 (Final Report LLM Chain): `gpt-4o-mini` for report cleanup and JSON formatting
   - Node 4 (Extractor): `gpt-4o-mini` — fast, structured extraction
   - Node 5 (Agent): `gpt-4o` — stronger reasoning for multi-tool orchestration

---

## Testing the flow

### Manual test in n8n

1. Open the flow → click **Test workflow**
2. In the Webhook node, click **Listen for test event**
3. Send a test POST:

```bash
curl -X POST http://localhost:5678/webhook-test/property-triage \
  -H "Content-Type: application/json" \
  -d '{
    "description": "3-bedroom apartment in Tel Aviv, 110sqm, renovated kitchen, sea view. Asking 4.2M ILS.",
    "image_urls": [],
    "agent_name": "Test Agent"
  }'
```

### Automated end-to-end tests

```bash
# Activate the webhook first, then:
pip install httpx
python test_pipeline.py --webhook-url http://localhost:5678/webhook/property-triage
```

Runs 5 cases: 3 residential, 1 commercial, 1 guardrails rejection.

---

## Prompt iteration log files

| File | Node | Iteration target |
|------|------|-----------------|
| `prompt_logs/extractor_prompt_log.md` | Node 4 systemPromptTemplate | 5× |
| `prompt_logs/agent_prompt_log.md` | Node 5 systemMessage + tool descriptions | 5× |
| `prompt_logs/rag_prompt_log.md` | RAG service prompt (layer3) | 5× |
| `prompt_logs/guardrails_prompt_log.md` | Guardrails actions (layer3) | 5× |
| `prompt_logs/ollama_prompt_log.md` | WebUI system prompt (layer1) | 5× |

After each iteration: edit the prompt in n8n → re-run test_pipeline.py → record results.

---

## Swapping localhost → EC2 after deployment

1. Deploy all four Layer 3 services to EC2 (see each service README)
2. Update n8n environment variables:

```
RAG_URL        = http://<EC2-PUBLIC-IP>:8001
IMAGE_URL      = http://<EC2-PUBLIC-IP>:8002
GUARDRAILS_URL = http://<EC2-PUBLIC-IP>:8003
LANGGRAPH_URL  = http://<EC2-PUBLIC-IP>:8004
```

3. Restrict EC2 security group inbound rules on ports 8001–8004
   to your n8n instance IP only
4. Re-run `test_pipeline.py` with the live webhook URL
