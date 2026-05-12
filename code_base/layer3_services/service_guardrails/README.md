# Service 3 — Guardrails

**Stack:** FastAPI · NeMo Guardrails 0.9 · Colang 1.0 · OpenAI GPT-4o-mini

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| POST | `/check/input` | Validate a listing submission |
| POST | `/check/output` | Audit an AI-generated report |

### POST /check/input

```json
// Request
{ "text": "3-bedroom apartment in Tel Aviv, 110sqm, renovated, 4.2M ILS" }

// Response — valid listing
{ "passed": true, "reason": null }

// Response — blocked
{ "passed": false, "reason": "This submission does not appear to be a genuine property listing..." }
```

### POST /check/output

```json
// Request
{
  "report": "This property guarantees a 15% annual rental yield.",
  "original_listing": "3BR apartment in Tel Aviv..."
}

// Response — flagged
{ "passed": false, "reason": "Report contains unverifiable or fabricated claims" }

// Response — clean
{ "passed": true, "reason": null }
```

---

## Three rails

| Rail | Colang flow | When it fires |
|------|-------------|---------------|
| A — Input validation | `check input is property listing` | Every submission |
| B — Injection detection | `block prompt injection` | Every submission |
| C — Output auditing | `audit output for fabrications` | Every generated report |

---

## Setup

### 1. Set your OpenAI API key

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

### 2. Start the service

```bash
docker compose up --build
```

Available at `http://localhost:8003`.

### 3. Run the test suite

```bash
# Service must be running
python test_rails.py --base-url http://localhost:8003
```

This runs all 20 test cases (10 input + 10 output) and prints a pass/fail report.  
Record results in `../../layer2_n8n/prompt_logs/guardrails_prompt_log.md`.

---

## Iterating the prompts

The three classifier prompts live in `actions.py`:

| Constant | Rail |
|----------|------|
| `_INPUT_VALIDATION_PROMPT` | Rail A — is it a listing? |
| `_INJECTION_DETECTION_PROMPT` | Rail B — prompt injection? |
| `_OUTPUT_AUDIT_PROMPT` | Rail C — fabrication in report? |

Edit the prompt → restart the container → re-run `test_rails.py` → log results.

---

## Fail-open policy

Both endpoints catch infrastructure errors and return `passed=True` with a `reason` field explaining the error. This prevents guardrail failures from blocking the entire pipeline. Review logs in production to catch repeated errors.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required. Your OpenAI API key. |
| `GUARDRAILS_MODEL` | `gpt-4o-mini` | Model used for classification calls |
| `RAILS_CONFIG_PATH` | `./rails` | Path to NeMo config directory |

---

## EC2 Deployment

```bash
docker build -t property-guardrails .
docker run -d \
  -p 8003:8000 \
  -e OPENAI_API_KEY=sk-... \
  --name property_guardrails \
  property-guardrails
```
