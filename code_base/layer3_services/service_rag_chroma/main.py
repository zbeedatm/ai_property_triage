"""
RAG Service — POST /query
Retrieves similar past property listings from ChromaDB and generates
an insight using Mistral 7B via llama-cpp-python.
"""

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag_pipeline import RAGPipeline
from seed_chroma import ensure_seeded

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory where this package lives — used so CHROMA_PATH defaults are stable regardless of cwd.
_SERVICE_DIR = Path(__file__).resolve().parent


def _resolve_under_service_dir(path_raw: str) -> str:
    """Turn relative paths into absolute paths under service_rag/ (fixes empty Chroma when cwd != service_rag)."""
    p = Path(path_raw)
    return str(p.resolve() if p.is_absolute() else (_SERVICE_DIR / p).resolve())


# ---------------------------------------------------------------------------
# Lifespan: load heavy resources once at startup
# ---------------------------------------------------------------------------

rag: RAGPipeline | None = None
ACTIVE_CHROMA_PATH: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag, ACTIVE_CHROMA_PATH
    logger.info("Loading RAG pipeline...")
    chroma_path_raw = os.getenv("CHROMA_PATH", "./chroma_db")
    chroma_path = _resolve_under_service_dir(chroma_path_raw)
    ACTIVE_CHROMA_PATH = chroma_path
    model_path = _resolve_under_service_dir(os.getenv("MODEL_PATH", "../../../models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"))
    embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    if os.getenv("RAG_AUTO_SEED", "true").lower() in ("1", "true", "yes"):
        try:
            ensure_seeded(chroma_path=chroma_path, embedding_model=embedding_model)
        except Exception:
            logger.exception(
                'RAG_AUTO_SEED failed. Seed manually from service_rag: python seed_chroma.py --chroma-path ./chroma_db'
            )

    rag = RAGPipeline(
        chroma_path=chroma_path,
        model_path=model_path,
        embedding_model=embedding_model,
        top_k=int(os.getenv("TOP_K", "3")),
    )
    doc_count = rag.collection.count()
    if doc_count == 0:
        logger.warning(
            "ChromaDB at %s has 0 documents — RAG will always return \"No similar listings...\".\n"
            "  Seed the KB (paths are resolved relative to service_rag/ if CHROMA_PATH is relative):\n"
            '  cd "%s"\n'
            '  python seed_chroma.py --chroma-path "%s"',
            chroma_path,
            _SERVICE_DIR,
            chroma_path_raw,
        )
    logger.info("RAG pipeline ready (%d vectors in knowledge base at %s).", doc_count, chroma_path)
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Property RAG Service",
    description="Retrieves similar past listings and generates insights using Mistral 7B.",
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

class QueryRequest(BaseModel):
    description: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "3-bedroom apartment in Tel Aviv, renovated kitchen, sea view, 120sqm"
            }
        }
    }


class SimilarListing(BaseModel):
    id: str
    title: str
    description: str
    similarity_score: float


class QueryResponse(BaseModel):
    similar_listings: list[SimilarListing]
    insight: str
    retrieved_count: int
    knowledge_base_documents: int = 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    out = {
        "status": "ok",
        "model": "mistral-7b-instruct-v0.2.Q4_K_M",
        "chroma_path": ACTIVE_CHROMA_PATH
        or _resolve_under_service_dir(os.getenv("CHROMA_PATH", "./chroma_db")),
    }
    if rag is None:
        out["chromadb_documents"] = None
        out["warning"] = "Pipeline still loading"
        return out
    try:
        n = rag.collection.count()
        out["chromadb_documents"] = n
        if n == 0:
            out["warning"] = "Knowledge base empty — run python seed_chroma.py with matching CHROMA_PATH"
    except Exception as exc:
        out["chromadb_documents"] = -1
        out["chromadb_error"] = str(exc)
    return out


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    if not request.description.strip():
        raise HTTPException(status_code=400, detail="description must not be empty")

    if rag is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialised")

    try:
        result = rag.run(request.description)
        return result
    except Exception as exc:
        logger.exception("RAG pipeline error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
