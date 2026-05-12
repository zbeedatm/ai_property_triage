#!/usr/bin/env python3
"""
Inspect Pinecone without n8n or the full RAG HTTP stack.

Usage (from this folder):

  python inspect_pinecone.py
  python inspect_pinecone.py "3-bedroom apartment in Tel Aviv..."
  python inspect_pinecone.py --ensure-smoke-listing

Loads ./.env if present (PINECONE_API_KEY, PINECONE_INDEX_NAME, EMBEDDING_MODEL).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from pinecone import Pinecone  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

DEFAULT_SMOKE_QUERY = (
    "3-bedroom apartment in Tel Aviv, Florentin. 110sqm, fully renovated kitchen, "
    "two bathrooms, balcony with city view. Asking 3,500,000"
)

EXPECTED_TOP_LISTING_ID_FOR_DEFAULT_QUERY = "LST-001"
SMOKE_LISTING_ID = "LST-INSPECT-SMOKE"
SMOKE_LISTING_TITLE = "Florentin 3BR (inspect default query — verbatim)"


def ensure_smoke_listing(index, embed_model: SentenceTransformer) -> str:
    """
    If SMOKE_LISTING_ID is absent, upsert the verbatim Florentin paragraph.
    Returns "exists" | "inserted".
    """
    result = index.fetch(ids=[SMOKE_LISTING_ID])
    if result.get("vectors", {}).get(SMOKE_LISTING_ID):
        print("--- Ensure smoke listing ---")
        print(f"  Listing id {SMOKE_LISTING_ID} already exists in Pinecone — no insert.")
        print()
        return "exists"

    embedding = embed_model.encode(DEFAULT_SMOKE_QUERY).tolist()
    index.upsert(vectors=[{
        "id": SMOKE_LISTING_ID,
        "values": embedding,
        "metadata": {
            "listing_id": SMOKE_LISTING_ID,
            "title": SMOKE_LISTING_TITLE,
            "property_type": "apartment",
            "text": DEFAULT_SMOKE_QUERY,
        },
    }])
    print("--- Ensure smoke listing ---")
    print(f"  Inserted id {SMOKE_LISTING_ID} into Pinecone index.")
    print()
    return "inserted"


def main() -> int:
    parser = argparse.ArgumentParser(description="Count Pinecone vectors and run one similarity query.")
    parser.add_argument(
        "query",
        nargs="?",
        default=DEFAULT_SMOKE_QUERY,
        help="Similarity-search text (default: Florentin-style smoke query).",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--ensure-smoke-listing",
        action="store_true",
        help=f"If id {SMOKE_LISTING_ID!r} is missing, insert the default Florentin paragraph.",
    )
    args = parser.parse_args()

    api_key = os.getenv("PINECONE_API_KEY", "")
    index_name = os.getenv("PINECONE_INDEX_NAME", "property-listings")
    embed_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    if not api_key:
        print("ERROR: PINECONE_API_KEY not set. Set it in .env or as an environment variable.")
        return 1

    print("--- Pinecone smoke test ---")
    print(f"index_name:      {index_name}")
    print(f"embedding_model: {embed_name}")
    print()

    pc = Pinecone(api_key=api_key)

    existing = [idx.name for idx in pc.list_indexes()]
    if index_name not in existing:
        print(f"ERROR: Index '{index_name}' does not exist. Available: {existing}")
        print("  Fix: python seed_pinecone.py")
        return 1

    index = pc.Index(index_name)
    embed_model = SentenceTransformer(embed_name)

    if args.ensure_smoke_listing:
        ensure_smoke_listing(index, embed_model)

    stats = index.describe_index_stats()
    n = stats.total_vector_count
    print(f"Index '{index_name}' vector count: {n}")
    if n == 0:
        print("ERROR: index is empty. Seed the KB, then re-run this script.")
        return 1

    print()
    print("Query text:")
    print(args.query[:200] + ("..." if len(args.query) > 200 else ""))
    print()

    query_embedding = embed_model.encode(args.query).tolist()
    k = min(args.top_k, n)
    results = index.query(vector=query_embedding, top_k=k, include_metadata=True)

    matches = results.get("matches", [])
    print(f"Top {k} results (higher score = more similar):")
    for i, match in enumerate(matches, start=1):
        meta = match.get("metadata", {})
        score = match.get("score", 0)
        title = meta.get("title", "?")
        lid = meta.get("listing_id", match.get("id", "?"))
        text = meta.get("text", "")
        print(f"  [{i}] {lid} | {title}")
        print(f"       score={score:.4f}")
        print(f"       text: {text[:120]}...")
        print()

    if args.query.strip() == DEFAULT_SMOKE_QUERY.strip() and matches:
        print("--- Default smoke query — expectation check ---")
        top_lid = matches[0].get("metadata", {}).get("listing_id", matches[0].get("id"))

        if top_lid == SMOKE_LISTING_ID:
            print(
                f"  OK: top hit is {SMOKE_LISTING_ID} (verbatim text stored)."
            )
        elif top_lid == EXPECTED_TOP_LISTING_ID_FOR_DEFAULT_QUERY:
            print(
                f"  OK: top hit is {EXPECTED_TOP_LISTING_ID_FOR_DEFAULT_QUERY} (seed Florentin neighbour)."
            )
        else:
            print(
                f"  NOTE: top hit is {top_lid!r}. Check embedding model vs seed data."
            )
        print()

    out = {
        "index_name": index_name,
        "vector_count": n,
        "top_results": [
            {
                "listing_id": m.get("metadata", {}).get("listing_id", m.get("id")),
                "title": m.get("metadata", {}).get("title"),
                "score": float(m.get("score", 0)),
                "snippet": m.get("metadata", {}).get("text", "")[:200],
            }
            for m in matches
        ],
    }
    print("JSON summary:")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
