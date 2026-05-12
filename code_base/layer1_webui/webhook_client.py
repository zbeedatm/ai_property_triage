"""
webhook_client.py
-----------------
Sends listing submissions to the n8n webhook and parses the response.

The n8n flow returns the final triage report as JSON.
This module normalises the response so the UI always gets a predictable dict.
"""

import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/property-triage")
HTTP_TIMEOUT    = float(os.getenv("HTTP_TIMEOUT", "120"))   # n8n flows can be slow


async def submit_listing(
    description: str,
    image_urls:  list[str],
    agent_name:  str,
) -> dict:
    """
    POST a listing submission to the n8n webhook.

    Returns a dict with either:
      {"success": True,  "report": {...}}
      {"success": False, "error": "..."}
    """
    payload = {
        "description": description.strip(),
        "image_urls":  [u.strip() for u in image_urls if u.strip()],
        "agent_name":  agent_name.strip(),
    }

    logger.info(
        "Submitting listing to n8n | agent=%s | images=%d",
        agent_name, len(payload["image_urls"]),
    )

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(N8N_WEBHOOK_URL, json=payload)
            resp.raise_for_status()

        body = resp.text.strip()
        if not body:
            logger.warning("n8n returned an empty response body (HTTP %s)", resp.status_code)
            return {"success": False, "error": "n8n returned an empty response. Check that the workflow is active and the 'Respond to Webhook' node is configured correctly."}

        data = json.loads(body)

        report = (
            data.get("report")
            or data.get("data", {}).get("report")
            or data
        )

        return {"success": True, "report": report}

    except httpx.HTTPStatusError as exc:
        logger.error("n8n webhook HTTP error: %s", exc)
        return {"success": False, "error": f"Webhook returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"}

    except httpx.TimeoutException:
        logger.error("n8n webhook timed out after %.0fs", HTTP_TIMEOUT)
        return {"success": False, "error": f"Request timed out after {HTTP_TIMEOUT:.0f}s. The pipeline may still be processing."}

    except Exception as exc:
        logger.exception("Unexpected webhook error")
        return {"success": False, "error": str(exc)}


def format_report_for_display(report: dict) -> str:
    """
    Convert the triage report dict into a readable markdown string
    for display in the Gradio UI.
    """
    if not report:
        return "_No report data received._"

    if "error" in report:
        return f"⚠️ **Pipeline error:** {report['error']}"

    lines = []

    # Header
    prop_type = report.get("property_type", "unknown").replace("_", " ").title()
    routing   = report.get("routing_decision", "unknown").title()
    lines.append(f"## 🏠 {prop_type}  ·  {routing}")
    lines.append("")

    # Key facts
    location  = report.get("location",  "—")
    price     = report.get("price_ils")
    num_rooms = report.get("num_rooms")
    confidence = report.get("confidence", 0)

    lines.append(f"**Location:** {location}")
    lines.append(f"**Price:** {'₪{:,.0f}'.format(price) if price else '—'}")
    lines.append(f"**Rooms:** {num_rooms if num_rooms else '—'}")
    lines.append(f"**Report confidence:** {confidence:.0%}")
    lines.append("")

    # Key features
    features = report.get("key_features", [])
    if features:
        lines.append("**Key features:**")
        for f in features:
            lines.append(f"  - {f}")
        lines.append("")

    # Image scores
    image_scores = report.get("image_scores", [])
    if image_scores:
        lines.append("**Image analysis:**")
        for img in image_scores:
            room      = img.get("room_type", "unknown").replace("_", " ").title()
            score     = img.get("condition_score", 0)
            conf      = img.get("confidence", 0)
            low_conf  = "⚠️ low confidence" if conf < 0.5 else ""
            stars     = "⭐" * round(score)
            lines.append(f"  - {room}: {stars} ({score:.1f}/5)  {low_conf}")
        lines.append("")

    # Similar listings (always show heading — KB matches are seeded, not learnt from repeats)
    similar = report.get("similar_listings", [])
    lines.append("**Similar past listings:**")
    if similar:
        for s in similar:
            if isinstance(s, dict):
                title = (s.get("title") or s.get("id") or "").strip()
                line = title or json.dumps(s, ensure_ascii=False)[:160]
                lines.append(f"  - {line}")
            else:
                lines.append(f"  - {s}")
    else:
        lines.append(
            "  - _No similar listings retrieved._ Typical causes: "
            "the vector store is empty (run `seed_chroma` / restart RAG with auto-seed), "
            "or retrieved_count was 0 for this query."
        )
        if report.get("knowledge_base_documents") is not None:
            lines.append(
                f"  - _(Vectors in KB at query time: {report.get('knowledge_base_documents')}.)_"
            )
    lines.append("")

    # RAG insight
    rag_insight = str(report.get("rag_insight", "") or "").strip()
    if not rag_insight and not similar:
        rag_insight = "No similar listings found in the knowledge base."

    if rag_insight:
        lines.append("**Market insight:**")
        lines.append(f"> {rag_insight}")
        lines.append("")

    # Enrichment notes
    notes = report.get("enrichment_notes", "")
    if notes:
        lines.append("**Analyst notes:**")
        lines.append(notes)

    return "\n".join(lines)
