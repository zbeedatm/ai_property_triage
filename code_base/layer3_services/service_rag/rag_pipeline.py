"""
RAGPipeline
-----------
1. Embed the incoming description with a sentence-transformer model.
2. Query Pinecone for the top-k most similar past listings.
3. Inject retrieved context into a LangChain prompt.
4. Generate a short insight via:
   - **Ollama** (default): Ollama Cloud or local `OLLAMA_HOST` + `OLLAMA_API_KEY` when using cloud.
   - **llama_cpp** (legacy): Mistral 7B GGUF via llama-cpp-python (`RAG_LLM_BACKEND=llama_cpp`).
"""

import logging
import os
import threading
from dataclasses import dataclass

from ollama import Client as OllamaClient
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from langchain.prompts import PromptTemplate
from langchain_community.llms import LlamaCpp
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt template (same as Chroma variant)
# ---------------------------------------------------------------------------

RAG_PROMPT = PromptTemplate(
    input_variables=["description", "context"],
    template="""You are a senior real estate analyst. A listing agent has submitted a new property description.
You have retrieved the three most similar past listings from the agency's knowledge base.

Your task:
- Compare the new listing to the retrieved listings.
- Identify what makes it similar or distinct.
- Cite each retrieved listing by its title when you reference it.
- Do NOT invent any facts, prices, or features not present in the retrieved listings.
- Keep your insight to 3–5 sentences.

--- New listing ---
{description}

--- Retrieved similar listings ---
{context}

--- Your insight ---""",
)


# ---------------------------------------------------------------------------
# Data class for a single retrieved listing
# ---------------------------------------------------------------------------

@dataclass
class RetrievedListing:
    id: str
    title: str
    description: str
    similarity_score: float


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class RAGPipeline:
    def __init__(
        self,
        pinecone_api_key: str,
        index_name: str,
        model_path: str,
        embedding_model: str,
        top_k: int = 3,
    ):
        self.top_k = top_k
        self._llm_lock = threading.Lock()
        self.llm_backend = os.getenv("RAG_LLM_BACKEND", "ollama").lower().strip()

        # --- Pinecone ---
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index = self.pc.Index(index_name)
        self.index_name = index_name
        logger.info("Connected to Pinecone index '%s'.", index_name)

        # --- Embedding model ---
        self.embed_model = SentenceTransformer(embedding_model)
        logger.info("Loaded embedding model: %s", embedding_model)

        # --- Insight LLM: Ollama (default) or local GGUF ---
        self.llm = None
        self.chain = None
        self.ollama_client: OllamaClient | None = None
        self.ollama_model: str | None = None

        if self.llm_backend == "ollama":
            host = os.getenv("OLLAMA_HOST", "https://ollama.com").rstrip("/")
            model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b")
            key = os.getenv("OLLAMA_API_KEY", "").strip()
            if not key:
                raise ValueError(
                    "RAG_LLM_BACKEND=ollama requires OLLAMA_API_KEY in the environment "
                    "(Docker Compose: set it in docker/secrets/rag.env; "
                    "see docker/examples/rag.env.example for keys and comments)."
                )
            headers = {"Authorization": f"Bearer {key}"}
            self.ollama_client = OllamaClient(host=host, headers=headers)
            self.ollama_model = model
            logger.info("RAG insight LLM: Ollama at %s model=%s", host, model)
        else:
            llama_threads = int(os.getenv("RAG_LLM_THREADS", "1"))
            self.llm = LlamaCpp(
                model_path=model_path,
                n_ctx=4096,
                n_gpu_layers=0,
                n_threads=llama_threads,
                temperature=0.2,
                max_tokens=512,
                verbose=False,
            )
            self.chain = LLMChain(llm=self.llm, prompt=RAG_PROMPT)
            logger.info(
                "RAG insight LLM: llama.cpp from %s (n_threads=%d)",
                model_path,
                llama_threads,
            )

    def vector_count(self) -> int:
        stats = self.index.describe_index_stats()
        return stats.total_vector_count

    # -----------------------------------------------------------------------

    def _retrieve(self, description: str) -> list[RetrievedListing]:
        """Encode the query and search Pinecone for top-k listings."""
        n_docs = self.vector_count()
        if n_docs == 0:
            return []

        query_embedding = self.embed_model.encode(description).tolist()

        results = self.index.query(
            vector=query_embedding,
            top_k=min(self.top_k, n_docs),
            include_metadata=True,
        )

        listings: list[RetrievedListing] = []
        for match in results.get("matches", []):
            meta = match.get("metadata", {})
            similarity = round(match.get("score", 0.0), 4)
            listings.append(
                RetrievedListing(
                    id=str(meta.get("listing_id", match.get("id", "unknown"))),
                    title=str(meta.get("title", "Untitled")),
                    description=str(meta.get("text", "")),
                    similarity_score=similarity,
                )
            )
        return listings

    def _build_context(self, listings: list[RetrievedListing]) -> str:
        """Format retrieved listings into the prompt context block."""
        parts = []
        for i, listing in enumerate(listings, start=1):
            parts.append(
                f"[{i}] {listing.title} (similarity: {listing.similarity_score})\n{listing.description}"
            )
        return "\n\n".join(parts)

    def _insight_via_ollama(self, description: str, context: str) -> str:
        assert self.ollama_client is not None and self.ollama_model is not None
        prompt_text = RAG_PROMPT.format(description=description, context=context)
        with self._llm_lock:
            resp = self.ollama_client.chat(
                model=self.ollama_model,
                messages=[{"role": "user", "content": prompt_text}],
                stream=False,
                options={"temperature": 0.2},
            )
        if isinstance(resp, dict):
            msg = resp.get("message") or {}
            text = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "") or ""
        else:
            m = getattr(resp, "message", None)
            text = (getattr(m, "content", None) or "") if m is not None else ""
        return str(text).strip()

    def run(self, description: str) -> dict:
        """Full RAG pipeline — retrieve → generate → return structured result."""
        kb_count = self.vector_count()
        listings = self._retrieve(description)

        if not listings:
            return {
                "similar_listings": [],
                "insight": "No similar listings found in the knowledge base.",
                "retrieved_count": 0,
                "knowledge_base_documents": kb_count,
            }

        context = self._build_context(listings)

        if self.ollama_client is not None:
            insight = self._insight_via_ollama(description, context)
        elif self.chain is not None:
            with self._llm_lock:
                out = self.chain.invoke({"description": description, "context": context})
            if isinstance(out, dict):
                insight = out.get("text") or out.get("output") or ""
                if not insight and len(out) == 1:
                    insight = next(iter(out.values()))
            else:
                insight = out or ""
            insight = str(insight).strip()
        else:
            insight = "Insight LLM is not configured."

        return {
            "similar_listings": [
                {
                    "id": l.id,
                    "title": l.title,
                    "description": l.description,
                    "similarity_score": l.similarity_score,
                }
                for l in listings
            ],
            "insight": insight,
            "retrieved_count": len(listings),
            "knowledge_base_documents": kb_count,
        }
