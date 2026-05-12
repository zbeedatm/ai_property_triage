"""
RAGPipeline
-----------
1. Embed the incoming description with a sentence-transformer model.
2. Query ChromaDB for the top-k most similar past listings.
3. Inject retrieved context into a LangChain prompt.
4. Generate a short insight with Mistral 7B via llama-cpp-python.
"""

import logging
import os
import threading
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from langchain.prompts import PromptTemplate
from langchain_community.llms import LlamaCpp
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt template (Iteration 1 — log improvements in prompt_logs/)
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
        chroma_path: str,
        model_path: str,
        embedding_model: str,
        top_k: int = 3,
    ):
        self.top_k = top_k
        # llama-cpp-python is not safe for concurrent inference — parallel /query calls segfault (Windows/Linux).
        self._llm_lock = threading.Lock()

        # --- ChromaDB ---
        # self.chroma_client = chromadb.PersistentClient(path=chroma_path)
         # --- ChromaDB (telemetry off: avoids PostHog API mismatches / noise)
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="property_listings",
            embedding_function=self.embed_fn,
        )
        logger.info(
            "ChromaDB collection 'property_listings' loaded — %d documents",
            self.collection.count(),
        )

        # --- Mistral 7B via llama-cpp-python ---
        llama_threads = int(os.getenv("RAG_LLM_THREADS", "1"))
        self.llm = LlamaCpp(
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=0,          # set > 0 if GPU available
            n_threads=llama_threads,
            temperature=0.2,
            max_tokens=512,
            verbose=False,
        )
        self.chain = LLMChain(llm=self.llm, prompt=RAG_PROMPT)
        logger.info("Mistral 7B loaded from %s (n_threads=%d)", model_path, llama_threads)

    # -----------------------------------------------------------------------

    def _retrieve(self, description: str) -> list[RetrievedListing]:
        """Query ChromaDB and return top-k listings."""
        n_docs = self.collection.count()
        if n_docs == 0:
            return []

        results = self.collection.query(
            query_texts=[description],
            n_results=min(self.top_k, n_docs),
            include=["documents", "metadatas", "distances"],
        )

        listings: list[RetrievedListing] = []
        docs = results["documents"][0] if results.get("documents") else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        if n_docs > 0 and (not docs or all(d is None for d in docs)):
            logger.warning(
                "Chroma query returned no document rows despite count()=%s — check embedding model matches seed data.",
                n_docs,
            )

        for doc, meta, dist in zip(docs, metas, distances):
            if doc is None:
                continue
            meta = meta or {}
            if dist is None:
                continue
            # ChromaDB returns L2 distance — convert to a 0-1 similarity score
            similarity = round(1 / (1 + dist), 4)
            listings.append(
                RetrievedListing(
                    id=str(meta.get("listing_id", "unknown")),
                    title=str(meta.get("title", "Untitled")),
                    description=doc,
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

    def run(self, description: str) -> dict:
        """Full RAG pipeline — retrieve → generate → return structured result."""
        kb_count = self.collection.count()
        listings = self._retrieve(description)

        if not listings:
            return {
                "similar_listings": [],
                "insight": "No similar listings found in the knowledge base.",
                "retrieved_count": 0,
                "knowledge_base_documents": kb_count,
            }

        context = self._build_context(listings)
        with self._llm_lock:
            out = self.chain.invoke({"description": description, "context": context})
        if isinstance(out, dict):
            insight = out.get("text") or out.get("output") or ""
            if not insight and len(out) == 1:
                insight = next(iter(out.values()))
        else:
            insight = out or ""
        insight = str(insight).strip()

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
