"""
tools.py
--------
LangChain-compatible tool wrappers for the two sibling EC2 services.
Each tool is a plain async function decorated with @tool.

Tool descriptions are at Iteration 1 — log improvements in:
    prompt_logs/agent_prompt_log.md  (tool description section)

Service URLs are read from environment variables so they can be
swapped from localhost → EC2 public IPs without code changes.
"""

import json
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langchain.tools import tool

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30"))


def _resolve_rag_url() -> str:
    """
    Resolve the RAG service URL based on RAG_BACKEND flag.
    Priority: RAG_SERVICE_URL (explicit override) > RAG_BACKEND routing > fallback.
    """
    explicit = os.getenv("RAG_SERVICE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    backend = os.getenv("RAG_BACKEND", "pinecone").strip().lower()
    if backend == "chroma":
        return os.getenv("RAG_CHROMA_URL", "http://127.0.0.1:8001").rstrip("/")
    return os.getenv("RAG_PINECONE_URL", "http://127.0.0.1:8001").rstrip("/")


# ---------------------------------------------------------------------------
# Tool 1 — RAG query
# Iteration 1 description: direct and literal
# ---------------------------------------------------------------------------

@tool
async def rag_query(description: str) -> str:
    """
    Query the property knowledge base with a listing description.
    Use this tool for EVERY new listing to retrieve the most similar
    past properties and get a comparative market insight.

    Input:  A plain-text property description (the full listing text).
    Output: JSON string containing:
            - similar_listings: list of up to 3 past listings with id, title,
              description, and similarity_score
            - insight: a short comparative analysis written by the RAG model
            - retrieved_count: number of listings retrieved

    Always call this tool before forming any opinion about the listing.
    """
    base = _resolve_rag_url()
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{base}/query",
                json={"description": description},
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except httpx.HTTPStatusError as exc:
            logger.error("RAG service HTTP error: %s", exc)
            return json.dumps({"error": f"RAG service returned HTTP {exc.response.status_code}"})
        except httpx.ReadTimeout:
            logger.error(
                "RAG service at %s timed out after %ss — increase HTTP_TIMEOUT (currently %s) in .env",
                base, HTTP_TIMEOUT, HTTP_TIMEOUT,
            )
            return json.dumps({"error": f"RAG service timed out after {HTTP_TIMEOUT}s"})
        except httpx.RequestError as exc:
            backend = os.getenv("RAG_BACKEND", "pinecone").strip().lower()
            logger.error(
                "RAG unreachable at %s (RAG_BACKEND=%s) — check .env: %s",
                base,
                backend,
                exc,
            )
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            logger.error("RAG service call failed: %s", exc)
            return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool 2 — Image analyser
# Iteration 1 description: direct and literal
# ---------------------------------------------------------------------------

@tool
async def analyse_images(image_urls: str) -> str:
    """
    Analyse property photos to classify room types and score condition.
    Use this tool when the listing includes one or more image URLs.
    Pass ALL image URLs provided with the listing in a single call.

    Input:  A JSON array of image URL strings, e.g.:
            '["https://example.com/kitchen.jpg", "https://example.com/bedroom.jpg"]'

    Output: JSON string containing a 'results' list. Each item has:
            - url: the image URL that was analysed
            - room_type: one of kitchen, living_room, bedroom, bathroom,
              exterior, other
            - condition_score: 1.0 (poor) to 5.0 (excellent)
            - confidence: 0.0–1.0 (flag results below 0.5 as uncertain)
            - low_confidence: true if confidence < 0.5
            - error: null if successful, otherwise an error message

    If image_urls is an empty list, skip this tool entirely.
    """
    try:
        urls = json.loads(image_urls) if isinstance(image_urls, str) else image_urls
    except json.JSONDecodeError:
        return json.dumps({"error": "image_urls must be a valid JSON array of strings"})

    if not urls:
        return json.dumps({"results": [], "processed": 0, "failed": 0})

    base = os.getenv("IMAGE_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/")
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{base}/analyse",
                json={"image_urls": urls},
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except httpx.HTTPStatusError as exc:
            logger.error("Image service HTTP error: %s", exc)
            return json.dumps({"error": f"Image service returned HTTP {exc.response.status_code}"})
        except httpx.RequestError as exc:
            logger.error(
                "Image service unreachable at %s — check IMAGE_SERVICE_URL in .env: %s",
                base,
                exc,
            )
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            logger.error("Image service call failed: %s", exc)
            return json.dumps({"error": str(exc)})
