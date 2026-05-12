"""
RAG Service (Pinecone) — POST /query
Retrieves similar past property listings from Pinecone and generates
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
from seed_pinecone import ensure_seeded

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_SERVICE_DIR = Path(__file__).resolve().parent


def _resolve_under_service_dir(path_raw: str) -> str:
    """Turn relative paths into absolute paths under service_rag/."""
    p = Path(path_raw)
    return str(p.resolve() if p.is_absolute() else (_SERVICE_DIR / p).resolve())


# ---------------------------------------------------------------------------
# Lifespan: load heavy resources once at startup
# ---------------------------------------------------------------------------

rag: RAGPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag
    logger.info("Loading RAG pipeline (Pinecone) ...")

    pinecone_api_key = os.getenv("PINECONE_API_KEY", "")
    index_name = os.getenv("PINECONE_INDEX_NAME", "property-listings")
    cloud = os.getenv("PINECONE_CLOUD", "aws")
    region = os.getenv("PINECONE_REGION", "us-east-1")
    model_path = _resolve_under_service_dir(
        os.getenv("MODEL_PATH", "../../../models/mistral-7b-instruct-v0.2.Q4_K_M.gguf")
    )
    embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    if not pinecone_api_key:
        logger.error("PINECONE_API_KEY is not set — the RAG service cannot start.")
        raise RuntimeError("PINECONE_API_KEY environment variable is required.")

    if os.getenv("RAG_AUTO_SEED", "true").lower() in ("1", "true", "yes"):
        try:
            ensure_seeded(
                pinecone_api_key=pinecone_api_key,
                index_name=index_name,
                embedding_model=embedding_model,
                cloud=cloud,
                region=region,
            )
        except Exception:
            logger.exception(
                "RAG_AUTO_SEED failed. Seed manually: python seed_pinecone.py"
            )

    try:
        rag = RAGPipeline(
            pinecone_api_key=pinecone_api_key,
            index_name=index_name,
            model_path=model_path,
            embedding_model=embedding_model,
            top_k=int(os.getenv("TOP_K", "3")),
        )
        doc_count = rag.vector_count()
        if doc_count == 0:
            logger.warning(
                "Pinecone index '%s' has 0 vectors — RAG will always return \"No similar listings...\".\n"
                "  Seed the KB: python seed_pinecone.py",
                index_name,
            )
        logger.info("RAG pipeline ready (%d vectors in Pinecone index '%s').", doc_count, index_name)
    except Exception:
        logger.exception(
            "Failed to initialise RAGPipeline — /query will return 503.\n"
            "  Check that Pinecone index '%s' exists and PINECONE_API_KEY is valid.\n"
            "  Seed with: python seed_pinecone.py",
            index_name,
        )
        rag = None
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Property RAG Service (Pinecone)",
    description="Retrieves similar past listings from Pinecone and generates insights using Mistral 7B.",
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
        "vector_store": "pinecone",
        "index_name": os.getenv("PINECONE_INDEX_NAME", "property-listings"),
    }
    if rag is None:
        out["pinecone_vectors"] = None
        out["warning"] = "Pipeline still loading"
        return out
    try:
        n = rag.vector_count()
        out["pinecone_vectors"] = n
        if n == 0:
            out["warning"] = "Knowledge base empty — run python seed_pinecone.py"
    except Exception as exc:
        out["pinecone_vectors"] = -1
        out["pinecone_error"] = str(exc)
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
