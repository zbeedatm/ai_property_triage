"""
seed_pinecone.py
----------------
Populates a Pinecone serverless index with 20 synthetic property listings.
Run this once before starting the RAG service:

    python seed_pinecone.py [--pinecone-api-key ...] [--index-name ...]

The script is idempotent: re-running it will delete and recreate the index.
"""

import argparse
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

from listings_seed_data import LISTINGS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_SERVICE_DIR = Path(__file__).resolve().parent
load_dotenv(_SERVICE_DIR / ".env")

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


def ensure_seeded(
    pinecone_api_key: str,
    index_name: str,
    embedding_model: str,
    cloud: str = "aws",
    region: str = "us-east-1",
) -> int:
    """
    If the Pinecone index doesn't exist or is empty, seed it.
    Uses upsert (no delete/recreate) to avoid burning free-tier index quota.
    Returns the final vector count.
    """
    pc = Pinecone(api_key=pinecone_api_key)

    existing = [idx.name for idx in pc.list_indexes()]

    if index_name in existing:
        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        n = stats.total_vector_count
        if n > 0:
            logger.info("Pinecone index '%s' already contains %d vectors — skipping auto-seed.", index_name, n)
            return n
        logger.info("Pinecone index '%s' exists but is empty — seeding ...", index_name)
    else:
        logger.info("Index '%s' does not exist — creating and seeding ...", index_name)

    seed(
        pinecone_api_key=pinecone_api_key,
        index_name=index_name,
        embedding_model=embedding_model,
        cloud=cloud,
        region=region,
    )

    time.sleep(2)
    index = pc.Index(index_name)
    stats = index.describe_index_stats()
    return stats.total_vector_count


def seed(
    pinecone_api_key: str,
    index_name: str,
    embedding_model: str,
    cloud: str = "aws",
    region: str = "us-east-1",
    force_recreate: bool = False,
) -> None:
    pc = Pinecone(api_key=pinecone_api_key)

    existing = [idx.name for idx in pc.list_indexes()]

    if index_name in existing and force_recreate:
        logger.info("Deleting existing index '%s' (--force-recreate) ...", index_name)
        pc.delete_index(index_name)
        time.sleep(5)
        existing = [idx.name for idx in pc.list_indexes()]

    if index_name not in existing:
        logger.info("Creating serverless index '%s' (cloud=%s, region=%s) ...", index_name, cloud, region)
        pc.create_index(
            name=index_name,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=cloud, region=region),
        )
        while not pc.describe_index(index_name).status.get("ready"):
            logger.info("Waiting for index to be ready ...")
            time.sleep(2)
        logger.info("Index '%s' is ready.", index_name)
    else:
        logger.info("Index '%s' already exists — upserting vectors into it.", index_name)

    index = pc.Index(index_name)

    logger.info("Encoding %d listings with %s ...", len(LISTINGS), embedding_model)
    model = SentenceTransformer(embedding_model)
    texts = [l["text"] for l in LISTINGS]
    embeddings = model.encode(texts, show_progress_bar=True)

    vectors = []
    for listing, emb in zip(LISTINGS, embeddings):
        vectors.append({
            "id": listing["listing_id"],
            "values": emb.tolist(),
            "metadata": {
                "listing_id": listing["listing_id"],
                "title": listing["title"],
                "property_type": listing["property_type"],
                "text": listing["text"],
            },
        })

    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]
        index.upsert(vectors=batch)
        logger.info("Upserted batch %d-%d", i, i + len(batch) - 1)

    time.sleep(2)
    stats = index.describe_index_stats()
    logger.info("Done. Index '%s' now contains %d vectors.", index_name, stats.total_vector_count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Pinecone with synthetic property listings")
    parser.add_argument(
        "--pinecone-api-key",
        default=os.getenv("PINECONE_API_KEY"),
        help="Pinecone API key (or set PINECONE_API_KEY env var)",
    )
    parser.add_argument(
        "--index-name",
        default=os.getenv("PINECONE_INDEX_NAME", "property-listings"),
        help="Pinecone index name",
    )
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        help="HuggingFace sentence-transformer model name",
    )
    parser.add_argument("--cloud", default=os.getenv("PINECONE_CLOUD", "aws"))
    parser.add_argument("--region", default=os.getenv("PINECONE_REGION", "us-east-1"))
    parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Delete and recreate the index (caution: uses free-tier index quota)",
    )
    args = parser.parse_args()

    if not args.pinecone_api_key:
        raise SystemExit("ERROR: --pinecone-api-key or PINECONE_API_KEY env var is required.")

    seed(
        pinecone_api_key=args.pinecone_api_key,
        index_name=args.index_name,
        embedding_model=args.embedding_model,
        cloud=args.cloud,
        region=args.region,
        force_recreate=args.force_recreate,
    )
