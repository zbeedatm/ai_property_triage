# Prompt Engineering Log — RAG Retrieval Prompt
**Surface:** EC2 Service 1 — LangChain + Llama.cpp  
**Component:** Context injection and citation instructions  
**Required iterations:** 5 minimum

---

## Test Suite (run every version against these)

| # | Input description | Expected behaviour |
|---|---|---|
| 1 | "3-bedroom apartment in Tel Aviv, recently renovated, sea view" | Returns 3 similar listings, cites each by name |
| 2 | "Commercial office space, 200sqm, parking included" | Does not confuse with residential listings |
| 3 | "Villa with pool, garden, 5 rooms" | Cites retrieved listings, does not fabricate extra details |
| 4 | "Studio apartment, 35sqm, central location" | Handles small properties correctly |
| 5 | "Industrial warehouse, 1000sqm" | Routes to commercial context correctly |
| 6 | Gibberish / very short input | Fails gracefully, returns empty or low-confidence response |
| 7 | Listing with missing price | Does not invent a price |
| 8 | Listing in Hebrew | Handles or gracefully rejects non-English input |
| 9 | Duplicate of an existing listing | Retrieves it as top-1, cites it correctly |
| 10 | Luxury penthouse with unusual features | Retrieves best partial match, acknowledges gap |

---

## Version 1 — Baseline

**Date:**  
**Prompt:**

```
You are a real estate assistant. Given the following retrieved listings, answer the question.

Retrieved context:
{context}

User query:
{query}

Answer:
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

## Version 2 — Targeted Iteration

**Failure addressed from V1:**  
**Change made:**

**Prompt:**

```
[paste updated prompt here]
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

**Prompt:**

```
[paste updated prompt here]
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

**Prompt:**

```
[paste updated prompt here]
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

**Prompt:**

```
[paste updated prompt here]
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

**Final prompt:**

```
[paste final prompt here]
```

**Design decisions:**

| Prompt element | Justification |
|---|---|
| | |

**Pass rate:** __ / 10 test cases

**Key learnings:**
- 
- 
- 
