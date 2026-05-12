#!/usr/bin/env python3
"""
Inspect ChromaDB without n8n or the full RAG HTTP stack.

Usage (from repo root or from this folder):

  cd layer3_services/service_rag
  .venv\\Scripts\\python inspect_chroma.py
  .venv\\Scripts\\python inspect_chroma.py "3-bedroom apartment in Tel Aviv..."
  .venv\\Scripts\\python inspect_chroma.py --ensure-smoke-listing

Loads ./.env if present (CHROMA_PATH, EMBEDDING_MODEL).

With ``--ensure-smoke-listing``, the default Florentin paragraph is **upserted** into
``property_listings`` under id ``LST-INSPECT-SMOKE`` if that id is not already present;
otherwise a message is printed and nothing is written.

The default query (when you pass no argument) is only **search text** — it is **not**
inserted into Chroma. Listings come from `seed_chroma.py` (e.g. Florentin ≈ `LST-001`).
You will see **similar** stored listings in results, not that query string as a document.

Same as a manual API check:
  curl -s -X POST http://127.0.0.1:8001/query \\
    -H "Content-Type: application/json" \\
    -d "{\\"description\\": \\"your text here\\"}"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

import chromadb  # noqa: E402 — after dotenv
from chromadb.config import Settings
from chromadb.utils import embedding_functions

_SERVICE_DIR = Path(__file__).resolve().parent

# Used as default CLI query only — never written to the vector DB by this script.
DEFAULT_SMOKE_QUERY = (
    "3-bedroom apartment in Tel Aviv, Florentin. 110sqm, fully renovated kitchen, "
    "two bathrooms, balcony with city view. Asking 3,500,000"
)

# For the default query, embeddings should rank the seeded Florentin listing first.
EXPECTED_TOP_LISTING_ID_FOR_DEFAULT_QUERY = "LST-001"

# Optional insert (--ensure-smoke-listing): same text as DEFAULT_SMOKE_QUERY, dedicated Chroma id.
SMOKE_LISTING_ID = "LST-INSPECT-SMOKE"
SMOKE_LISTING_TITLE = "Florentin 3BR (inspect default query — verbatim)"


def ensure_smoke_listing(coll) -> str:
    """
    If SMOKE_LISTING_ID is absent, add the verbatim Florentin paragraph to the collection.
    Returns a short status for stdout: "exists" | "inserted".
    """
    got = coll.get(ids=[SMOKE_LISTING_ID], include=[])
    if got.get("ids"):
        print("--- Ensure smoke listing ---")
        print(f"  Listing id {SMOKE_LISTING_ID} already exists in Chroma — no insert.")
        print()
        return "exists"

    coll.add(
        ids=[SMOKE_LISTING_ID],
        documents=[DEFAULT_SMOKE_QUERY],
        metadatas=[
            {
                "listing_id": SMOKE_LISTING_ID,
                "title": SMOKE_LISTING_TITLE,
                "property_type": "apartment",
            }
        ],
    )
    print("--- Ensure smoke listing ---")
    print(f"  Inserted id {SMOKE_LISTING_ID} into collection 'property_listings'.")
    print()
    return "inserted"


def resolve_chroma(raw: str) -> str:
    p = Path(raw)
    return str(p.resolve() if p.is_absolute() else (_SERVICE_DIR / p).resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description="Count Chroma vectors and run one similarity query.")
    parser.add_argument(
        "query",
        nargs="?",
        default=DEFAULT_SMOKE_QUERY,
        help="Similarity-search text (default: Florentin-style smoke query — not a stored document).",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--ensure-smoke-listing",
        action="store_true",
        help=(
            f"If id {SMOKE_LISTING_ID!r} is missing, insert the default Florentin paragraph; "
            "if present, print a message and skip. Creates DB/collection if needed."
        ),
    )
    args = parser.parse_args()

    chroma_path = resolve_chroma(os.getenv("CHROMA_PATH", "./chroma_db"))
    embed_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    print("--- Chroma smoke test (same path/embed model as RAG service) ---")
    print(f"chroma_path:     {chroma_path}")
    print(f"path exists:     {Path(chroma_path).exists()}")
    print(f"embedding_model: {embed_name}")
    print()

    if not Path(chroma_path).exists() and not args.ensure_smoke_listing:
        print("ERROR: Chroma folder does not exist. Nothing has been persisted yet.")
        print("  Fix:  cd service_rag && python seed_chroma.py --chroma-path ./chroma_db")
        print("  Or start RAG once with RAG_AUTO_SEED=true (default) so ensure_seeded runs.")
        print("  Or use --ensure-smoke-listing to create the store and add the smoke listing.")
        return 1

    client = chromadb.PersistentClient(path=chroma_path, settings=Settings(anonymized_telemetry=False))
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=embed_name)

    if args.ensure_smoke_listing:
        coll = client.get_or_create_collection(name="property_listings", embedding_function=embed_fn)
        ensure_smoke_listing(coll)
    else:
        try:
            coll = client.get_collection("property_listings", embedding_function=embed_fn)
        except Exception as exc:
            print(f"ERROR: could not open collection 'property_listings': {exc}")
            print("  Fix: run seed_chroma.py first.")
            return 1

    n = coll.count()
    print(f"Collection 'property_listings' document count: {n}")
    if n == 0:
        print("ERROR: collection is empty. Seed the KB, then re-run this script.")
        return 1

    print()
    print("Query text:")
    print(args.query[:200] + ("..." if len(args.query) > 200 else ""))
    print()
    k = min(args.top_k, n)
    res = coll.query(
        query_texts=[args.query],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]

    print(f"Top {k} results (lower distance = more similar):")
    for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists), start=1):
        meta = meta or {}
        sim = round(1 / (1 + dist), 4) if dist is not None else 0
        title = meta.get("title", "?")
        lid = meta.get("listing_id", "?")
        print(f"  [{i}] {lid} | {title}")
        print(f"       distance={dist:.4f}  similarity~{sim}")
        print(f"       text: {(doc or '')[:120]}...")
        print()

    if args.query.strip() == DEFAULT_SMOKE_QUERY.strip():
        print("--- Default smoke query — expectation check ---")
        top_lid = (metas[0] or {}).get("listing_id") if metas else None
        smoke_present = bool(coll.get(ids=[SMOKE_LISTING_ID], include=[]).get("ids"))

        if top_lid == SMOKE_LISTING_ID:
            print(
                f"  OK: top hit is {SMOKE_LISTING_ID} (verbatim text stored; use --ensure-smoke-listing to manage it)."
            )
        elif top_lid == EXPECTED_TOP_LISTING_ID_FOR_DEFAULT_QUERY:
            print(
                f"  OK: top hit is {EXPECTED_TOP_LISTING_ID_FOR_DEFAULT_QUERY} "
                "(seed Florentin neighbour). No verbatim row — add with --ensure-smoke-listing if you want exact text in the DB."
            )
        else:
            print(
                f"  NOTE: top hit is {top_lid!r}. "
                "Check CHROMA_PATH, EMBEDDING_MODEL vs seed, or re-seed if the store differs."
            )

        if not smoke_present:
            print(
                f"  (Id {SMOKE_LISTING_ID!r} is not in the collection — the query string is only used for search, "
                "unless you insert it with --ensure-smoke-listing.)"
            )
        print()

    out = {
        "chroma_path": chroma_path,
        "document_count": n,
        "top_results": [
            {
                "listing_id": (m or {}).get("listing_id"),
                "title": (m or {}).get("title"),
                "distance": float(d) if d is not None else None,
                "snippet": (doc or "")[:200],
            }
            for doc, m, d in zip(docs, metas, dists)
        ],
    }
    print("JSON summary:")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
