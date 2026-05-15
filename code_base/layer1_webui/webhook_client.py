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


def _format_pct(value) -> str:
    """Format a 0..1 fraction as percent; n8n may send null or omit the field."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "—"


async def submit_listing(
    description: str,
    image_urls:  list[str],
    agent_name:  str,
) -> dict:
    """
    POST a listing submission to the n8n webhook.

    Returns a dict with either:
      {"success": True,  "report": {...}}
      {"success": False, "human_review": True, "message": "...", "flag_reason": "...", "report": {...}}
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
            return {
                "success": False,
                "error": (
                    "n8n returned an empty response. Check that the workflow is active, "
                    "that the 'Respond to Webhook' node runs on every branch "
                    "(including after human review), and re-import `flow.json` if you upgraded the flow."
                ),
            }

        data = json.loads(body)
        # n8n "Respond to Webhook" (JSON) may occasionally double-encode the body as a JSON string.
        if isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict):
            return {
                "success": False,
                "error": "Unexpected response from n8n: body was not a JSON object.",
            }

        # Node 7d: { success: false, human_review_required: true, message, flag_reason, report }.
        # Use truthy human_review_required (not `is True`) so string "true" still routes correctly.
        if data.get("human_review_required"):
            return {
                "success": False,
                "human_review": True,
                "message": data.get("message")
                or "This submission requires human review before a final triage result can be returned.",
                "flag_reason": data.get("flag_reason"),
                "report": data.get("report") if isinstance(data.get("report"), dict) else {},
            }

        # Same Node 7d shape if human_review_required was omitted but guardrails held the run.
        if (
            data.get("success") is False
            and isinstance(data.get("report"), dict)
            and "flag_reason" in data
        ):
            return {
                "success": False,
                "human_review": True,
                "message": data.get("message")
                or "This submission requires human review before a final triage result can be returned.",
                "flag_reason": data.get("flag_reason"),
                "report": data.get("report") or {},
            }

        if data.get("success") is False:
            err = (
                data.get("error")
                or data.get("message")
                or (
                    "Pipeline returned success: false with no report payload."
                    if not data.get("report")
                    else "Pipeline returned success: false (response did not match a known human-review or error shape)."
                )
            )
            return {"success": False, "error": err}

        report = (
            data.get("report")
            or data.get("data", {}).get("report")
            or data
        )
        if not isinstance(report, dict):
            return {
                "success": False,
                "error": "Unexpected response from n8n: report was not a JSON object.",
            }

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

    # Header (explicit `or` — JSON null is present as key with value None)
    prop_type = (report.get("property_type") or "unknown").replace("_", " ").title()
    routing = (report.get("routing_decision") or "unknown").title()
    lines.append(f"## 🏠 {prop_type}  ·  {routing}")
    lines.append("")

    # Key facts
    location = report.get("location") or "—"
    price = report.get("price_ils")
    num_rooms = report.get("num_rooms")

    lines.append(f"**Location:** {location}")
    lines.append(f"**Price:** {'₪{:,.0f}'.format(price) if price else '—'}")
    lines.append(f"**Rooms:** {num_rooms if num_rooms is not None else '—'}")
    lines.append(f"**Report confidence:** {_format_pct(report.get('confidence'))}")
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
            if not isinstance(img, dict):
                continue
            room = (img.get("room_type") or "unknown").replace("_", " ").title()
            try:
                score = float(img.get("condition_score") or 0)
            except (TypeError, ValueError):
                score = 0.0
            try:
                conf = float(img.get("confidence") or 0)
            except (TypeError, ValueError):
                conf = 0.0
            low_conf = "⚠️ low confidence" if conf < 0.5 else ""
            stars = "⭐" * max(0, min(5, round(score)))
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
