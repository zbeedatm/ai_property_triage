# Prompt Engineering Log — n8n AI Agent
**Surface:** Node 5 — Agent system prompt and tool descriptions  
**Component:** n8n AI Agent node (GPT-4o or Gemini)  
**Required iterations:** 5 minimum

---

## Agent Role

The agent acts as a **senior property analyst**. It receives the structured extracted fields and image URLs, decides which EC2 tools to call, and returns a structured JSON enrichment object.

## Tools Available to the Agent

| Tool name | Endpoint | When to call |
|---|---|---|
| `rag_query` | `POST /query` on RAG service | Always — retrieve similar past listings |
| `analyse_image` | `POST /analyse` on Image Analyser | For each image URL provided |
| `langgraph_agent` | `POST /agent/run` on LangGraph service | For complex multi-step questions about the listing |

## Expected Agent Output Schema

```json
{
  "property_type": "string",
  "routing_decision": "residential | commercial",
  "image_scores": [
    { "url": "string", "room_type": "string", "condition_score": 1-5 }
  ],
  "similar_listings": ["string"],
  "enrichment_notes": "string",
  "confidence": 0.0-1.0
}
```

---

## Test Suite

| # | Input scenario | Expected agent behaviour |
|---|---|---|
| 1 | Full listing + 3 image URLs | Calls RAG + all 3 image analyses + returns complete JSON |
| 2 | Listing with no images | Calls RAG only, returns empty `image_scores` array |
| 3 | Commercial listing | Sets `routing_decision: "commercial"` |
| 4 | Residential listing | Sets `routing_decision: "residential"` |
| 5 | Listing with ambiguous type | Defaults to residential or asks for clarification |
| 6 | Image URL that is broken/unreachable | Handles gracefully, marks as uncertain |
| 7 | Very short listing text | Still calls all tools, notes low confidence |
| 8 | Listing with renovation questions | Calls LangGraph agent for multi-step reasoning |
| 9 | 5 image URLs | Calls Image Analyser 5 times, aggregates scores |
| 10 | Agent receives garbled JSON from a tool | Handles error, continues with partial data |

---

## Version 1 — Baseline

**Date:**  
**System prompt:**

```
You are a property analyst. You have access to tools. Use them to analyse the listing.

Listing data:
{extracted_fields}

Image URLs:
{image_urls}
```

**Tool descriptions (V1):**

- `rag_query`: Query the knowledge base
- `analyse_image`: Analyse an image
- `langgraph_agent`: Run the agent

**Test results:**

| Test # | Pass / Fail | Notes |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |
| 9 | | |
| 10 | | |

**Observed failure mode:**

---

## Version 2 — Targeted Iteration

**Failure addressed from V1:**  
**Change made:**

**System prompt:**

```
[paste updated prompt here]
```

**Tool descriptions (V2):**

```
[paste updated tool descriptions here]
```

**Test results:**

| Test # | Pass / Fail | Notes |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |
| 9 | | |
| 10 | | |

**Observed failure mode:**

---

## Version 3 — Targeted Iteration

**Failure addressed from V2:**  
**Change made:**

**System prompt:**

```
[paste updated prompt here]
```

**Tool descriptions (V3):**

```
[paste updated tool descriptions here]
```

**Test results:**

| Test # | Pass / Fail | Notes |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |
| 9 | | |
| 10 | | |

**Observed failure mode:**

---

## Version 4 — Refinement

**Failure addressed from V3:**  
**Change made:**

**System prompt + tool descriptions:**

```
[paste updated content here]
```

**Test results:**

| Test # | Pass / Fail | Notes |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |
| 9 | | |
| 10 | | |

**Observed failure mode:**

---

## Version 5 — Refinement

**Failure addressed from V4:**  
**Change made:**

**System prompt + tool descriptions:**

```
[paste updated content here]
```

**Test results:**

| Test # | Pass / Fail | Notes |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |
| 9 | | |
| 10 | | |

---

## Final Entry

**Final system prompt:**

```
[paste final prompt here]
```

**Final tool descriptions:**

```
[paste final tool descriptions here]
```

**Design decisions:**

| Prompt / description element | Justification |
|---|---|
| | |

**Pass rate:** __ / 10 test cases

**Key learnings:**
- 
- 
- 
