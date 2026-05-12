# Prompt Engineering Log — n8n Information Extractor
**Surface:** Node 4 — systemPromptTemplate for structured field extraction  
**Component:** n8n Information Extractor node backed by Gemini  
**Required iterations:** 5 minimum

---

## Fields to Extract

| Field | Type | Notes |
|---|---|---|
| `property_type` | string | apartment, house, villa, office, retail, industrial, other |
| `location` | string | city / neighbourhood as mentioned in text |
| `price` | number or null | numeric only, null if not mentioned |
| `num_rooms` | integer or null | null if not mentioned |
| `key_features` | array of strings | max 5 items |
| `certifications` | array of strings | e.g. energy rating, accessibility, empty array if none |

---

## Test Suite

| # | Input description | Expected output |
|---|---|---|
| 1 | Full listing with all fields present | All 6 fields populated correctly |
| 2 | Listing with no price mentioned | `price: null` |
| 3 | Listing with no room count | `num_rooms: null` |
| 4 | Commercial listing (office) | `property_type: "office"` |
| 5 | Listing with 8 features mentioned | Only top 5 returned in `key_features` |
| 6 | Listing mentioning energy rating A | `certifications: ["energy rating A"]` |
| 7 | Very short listing (2 sentences) | Graceful partial extraction, no fabrication |
| 8 | Listing with ambiguous property type | Best guess or "other" |
| 9 | Listing with price in a foreign currency | Extract number, note currency |
| 10 | Spam / non-listing text | All fields null or empty |

---

## Version 1 — Baseline

**Date:**  
**Prompt:**

```
Extract structured information from the property listing below.
Return a JSON object with these fields: property_type, location, price, num_rooms, key_features, certifications.

Listing:
{input}
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
