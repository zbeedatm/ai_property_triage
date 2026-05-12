"""
LangGraph Agent Service — POST /agent/run
Orchestrates calls to the RAG and Image Analyser services,
then synthesises a structured property triage report.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env from this service directory (works regardless of shell cwd)
load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import AgentState, compiled_graph
from tools import _resolve_rag_url

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    force=True,  # uvicorn may configure logging first; we still want our format + tool loggers
)
logger = logging.getLogger(__name__)
# Ensure tool HTTP errors from tools.py always reach the console (same process as uvicorn).
logging.getLogger("tools").setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    rag_backend = os.getenv("RAG_BACKEND", "pinecone").strip().lower()
    logger.info(
        "LangGraph Agent Service ready.  RAG_BACKEND=%s  →  %s",
        rag_backend,
        _resolve_rag_url(),
    )
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Property LangGraph Agent Service",
    description="Multi-step agent that retrieves RAG context, analyses images, and synthesises a triage report.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AgentRunRequest(BaseModel):
    description: str
    image_urls:  list[str] | str | None = []

    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "3-bedroom apartment in Tel Aviv, 110sqm, renovated kitchen, sea view. Asking 4.2M ILS.",
                "image_urls": [
                    "https://example.com/kitchen.jpg",
                    "https://example.com/living_room.jpg",
                ],
            }
        }
    }

    def get_image_urls(self) -> list[str]:
        """Normalize image_urls to a list regardless of input format."""
        if not self.image_urls:
            return []
        if isinstance(self.image_urls, str):
            import json
            try:
                parsed = json.loads(self.image_urls)
                return parsed if isinstance(parsed, list) else [self.image_urls]
            except json.JSONDecodeError:
                return [self.image_urls] if self.image_urls.strip() else []
        return self.image_urls


class AgentRunResponse(BaseModel):
    report:        dict
    rag_retrieved: int
    images_analysed: int
    error:         str | None = None
    # Tool-level failures (connection refused, HTTP errors, etc.) — see LangGraph terminal when running uvicorn.
    rag_error:     str | None = None
    image_error:   str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    rag_backend = os.getenv("RAG_BACKEND", "pinecone").strip().lower()
    return {
        "status": "ok",
        "agent": "planner → tool_executor → synthesiser",
        "tools": ["rag_query", "analyse_images"],
        "rag_backend": rag_backend,
        "rag_service_url": _resolve_rag_url(),
    }


@app.post("/agent/run", response_model=AgentRunResponse)
async def agent_run(request: AgentRunRequest):
    if not request.description.strip():
        raise HTTPException(status_code=400, detail="description must not be empty")

    logger.info("Agent request: description=%.80r, image_urls=%r", request.description, request.image_urls)

    initial_state: AgentState = {
        "messages":     [],
        "description":  request.description,
        "image_urls":   request.get_image_urls(),
        "rag_result":   None,
        "image_result": None,
        "tools_done":   False,
        "report":       None,
    }

    try:
        final_state = await compiled_graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("Agent graph error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    report       = final_state.get("report") or {}
    rag_result   = final_state.get("rag_result")   or {}
    image_result = final_state.get("image_result") or {}

    rag_count    = rag_result.get("retrieved_count", 0)
    image_count  = image_result.get("processed", 0)

    rag_err   = rag_result.get("error") if isinstance(rag_result, dict) else None
    image_err = image_result.get("error") if isinstance(image_result, dict) else None

    if rag_err:
        logger.warning("RAG tool failed: %s", rag_err)
    if image_err:
        logger.warning("Image tool failed: %s", image_err)

    return AgentRunResponse(
        report=report,
        rag_retrieved=rag_count,
        images_analysed=image_count,
        error=report.get("error"),
        rag_error=rag_err,
        image_error=image_err,
    )
