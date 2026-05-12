"""
seed_chroma.py
--------------
Populates the ChromaDB vector store with 20 synthetic property listings.
Run this once before starting the RAG service:

    python seed_chroma.py [--chroma-path ./chroma_db] [--embedding-model ...]

The script is idempotent: re-running it will not create duplicate entries
because it deletes and recreates the collection.
"""

import argparse
import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_SERVICE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Synthetic listings
# ---------------------------------------------------------------------------

LISTINGS = [
    {
        "listing_id": "LST-001",
        "title": "Bright 3BR Apartment, Tel Aviv — Florentin",
        "property_type": "apartment",
        "text": (
            "A spacious 3-bedroom apartment located in the heart of Florentin, Tel Aviv. "
            "110 sqm, fully renovated kitchen with granite countertops, two full bathrooms, "
            "hardwood floors throughout. Building has an elevator. Close to restaurants, "
            "cafes and the Carmel Market. Asking price: 4,200,000 ILS."
        ),
    },
    {
        "listing_id": "LST-002",
        "title": "Sea-View Studio, Netanya Beachfront",
        "property_type": "apartment",
        "text": (
            "Compact studio apartment on the 8th floor of a beachfront building in Netanya. "
            "42 sqm, open-plan layout, fully furnished, panoramic sea views from the balcony. "
            "Suitable for short-term rental investment. Asking price: 1,650,000 ILS."
        ),
    },
    {
        "listing_id": "LST-003",
        "title": "Luxury Villa, Savyon",
        "property_type": "villa",
        "text": (
            "A stunning 6-bedroom private villa in the prestigious Savyon neighbourhood. "
            "600 sqm built area on a 1,200 sqm plot. Heated swimming pool, landscaped garden, "
            "home cinema, smart-home system. Triple garage. Asking price: 18,500,000 ILS."
        ),
    },
    {
        "listing_id": "LST-004",
        "title": "Commercial Office Space, Ramat Gan Diamond Exchange",
        "property_type": "office",
        "text": (
            "240 sqm open-plan office on the 14th floor of a Class-A tower in the Diamond "
            "Exchange district, Ramat Gan. Two meeting rooms, kitchenette, 24/7 security, "
            "10 underground parking spots. Immediate availability. Asking price: 7,800,000 ILS."
        ),
    },
    {
        "listing_id": "LST-005",
        "title": "Garden Apartment, Kfar Shmaryahu",
        "property_type": "apartment",
        "text": (
            "Ground-floor 4-bedroom garden apartment in a quiet residential street in "
            "Kfar Shmaryahu. 160 sqm interior plus 200 sqm private garden with a pergola "
            "and built-in BBQ. Newly painted, updated electrical and plumbing. "
            "Asking price: 8,900,000 ILS."
        ),
    },
    {
        "listing_id": "LST-006",
        "title": "Duplex Penthouse, Herzliya Pituach",
        "property_type": "apartment",
        "text": (
            "Two-level penthouse in a boutique building in Herzliya Pituach. "
            "220 sqm, 4 bedrooms, master suite with jacuzzi, roof terrace with sea view, "
            "private elevator access. Building has a pool and concierge. "
            "Asking price: 14,000,000 ILS."
        ),
    },
    {
        "listing_id": "LST-007",
        "title": "Retail Unit, Jerusalem City Centre",
        "property_type": "retail",
        "text": (
            "Ground-floor retail unit of 85 sqm on a main commercial street in central Jerusalem. "
            "Large glass frontage, air conditioning, back-office room. "
            "Currently leased to a café chain. Net yield approximately 5.2%. "
            "Asking price: 3,100,000 ILS."
        ),
    },
    {
        "listing_id": "LST-008",
        "title": "New Construction 2BR, Haifa Carmel",
        "property_type": "apartment",
        "text": (
            "Brand-new 2-bedroom apartment in a recently completed building on Mount Carmel, Haifa. "
            "75 sqm, open-plan living area, enclosed balcony with sea and mountain views, "
            "energy rating A, earthquake-resistant construction. "
            "Asking price: 2,450,000 ILS."
        ),
    },
    {
        "listing_id": "LST-009",
        "title": "Industrial Warehouse, Ashdod Port Zone",
        "property_type": "industrial",
        "text": (
            "1,800 sqm industrial warehouse in the Ashdod port industrial zone. "
            "10-metre clear height, three loading docks, 400-amp three-phase power supply, "
            "sprinkler system, secured compound with CCTV. "
            "Asking price: 12,000,000 ILS."
        ),
    },
    {
        "listing_id": "LST-010",
        "title": "Renovated Cottage, Moshav Beit Herut",
        "property_type": "house",
        "text": (
            "Charming 3-bedroom stone cottage on a 800 sqm plot in Moshav Beit Herut. "
            "Fully renovated: new kitchen, new bathrooms, underfloor heating, solar water heater. "
            "Large shaded garden, covered parking for two cars. "
            "Asking price: 3,700,000 ILS."
        ),
    },
    {
        "listing_id": "LST-011",
        "title": "City-Centre Studio, Beer Sheva",
        "property_type": "apartment",
        "text": (
            "Compact 38 sqm studio apartment on the 5th floor in downtown Beer Sheva. "
            "Suitable for Ben-Gurion University students or buy-to-let investors. "
            "Close to the new tech park. Asking price: 650,000 ILS."
        ),
    },
    {
        "listing_id": "LST-012",
        "title": "4BR Family Home, Ra'anana",
        "property_type": "house",
        "text": (
            "Detached 4-bedroom family home on a 400 sqm plot in a popular residential "
            "neighbourhood in Ra'anana. 175 sqm built area, large living room, study, "
            "two bathrooms, garden with automatic irrigation. English-speaking community nearby. "
            "Asking price: 7,200,000 ILS."
        ),
    },
    {
        "listing_id": "LST-013",
        "title": "High-Floor 2BR, Givatayim",
        "property_type": "apartment",
        "text": (
            "Bright 2-bedroom apartment on the 12th floor in Givatayim. "
            "80 sqm, renovated bathroom, large balcony with city views, storage room, "
            "one underground parking space. Walking distance to Ramat Gan Park. "
            "Asking price: 2,900,000 ILS."
        ),
    },
    {
        "listing_id": "LST-014",
        "title": "Boutique Office Floor, Tel Aviv Rothschild Blvd",
        "property_type": "office",
        "text": (
            "Entire floor of 180 sqm in a renovated Bauhaus building on Rothschild Boulevard, "
            "Tel Aviv. 8 private offices, reception area, server room, roof access. "
            "Prestigious address suitable for law firms or startups. "
            "Asking price: 9,500,000 ILS."
        ),
    },
    {
        "listing_id": "LST-015",
        "title": "Sea-View 3BR, Bat Yam Boardwalk",
        "property_type": "apartment",
        "text": (
            "Third-floor 3-bedroom apartment directly on the Bat Yam seafront promenade. "
            "105 sqm, fully renovated, open sea view from the living room and master bedroom, "
            "two covered parking spaces, storage unit. "
            "Asking price: 3,800,000 ILS."
        ),
    },
    {
        "listing_id": "LST-016",
        "title": "Rural Villa with Pool, Moshav Gimzo",
        "property_type": "villa",
        "text": (
            "Spacious 5-bedroom rural villa on a 2,000 sqm plot in Moshav Gimzo. "
            "280 sqm built area, private swimming pool, guest suite with separate entrance, "
            "mature fruit orchard. Quiet surroundings, 30 minutes from Tel Aviv. "
            "Asking price: 9,800,000 ILS."
        ),
    },
    {
        "listing_id": "LST-017",
        "title": "Logistics Hub, Modi'in Industrial Park",
        "property_type": "industrial",
        "text": (
            "Modern 3,500 sqm logistics facility in Modi'in industrial park. "
            "Cross-dock layout, 6 loading bays, temperature-controlled section (500 sqm), "
            "offices of 120 sqm attached, fibre internet. "
            "Asking price: 22,000,000 ILS."
        ),
    },
    {
        "listing_id": "LST-018",
        "title": "Penthouse with Roof Garden, Rehovot",
        "property_type": "apartment",
        "text": (
            "Top-floor 3-bedroom penthouse in a new tower in Rehovot. "
            "130 sqm interior plus 90 sqm private roof garden with pergola and outdoor kitchen. "
            "Two parking spaces, storage room, community pool in the building. "
            "Asking price: 5,100,000 ILS."
        ),
    },
    {
        "listing_id": "LST-019",
        "title": "Historic Stone House, Old Jaffa",
        "property_type": "house",
        "text": (
            "A rare 3-bedroom stone house in the historic core of Old Jaffa. "
            "140 sqm spread across two floors, original vaulted ceilings, courtyard garden, "
            "walking distance to the port and galleries. Fully renovated, protected facade. "
            "Asking price: 6,500,000 ILS."
        ),
    },
    {
        "listing_id": "LST-020",
        "title": "Investment Apartment Portfolio, Rishon LeZion",
        "property_type": "apartment",
        "text": (
            "Portfolio of three 2-bedroom apartments in the same building in Rishon LeZion, "
            "sold together. Each unit is 68 sqm, currently tenanted, combined gross yield of 4.8%. "
            "Elevator building, parking for each unit. "
            "Asking price: 5,400,000 ILS (all three)."
        ),
    },
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

def ensure_seeded(chroma_path: str, embedding_model: str) -> int:
    """
    If property_listings has no documents, run seed().
    Returns final document count (after optional seed).
    """
    p = Path(chroma_path)
    resolved = str(p.resolve() if p.is_absolute() else (_SERVICE_DIR / p).resolve())
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=embedding_model
    )
    client = chromadb.PersistentClient(path=resolved, settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(
        name="property_listings",
        embedding_function=embed_fn,
    )
    n = collection.count()
    if n > 0:
        logger.info("ChromaDB already contains %d documents — skipping auto-seed.", n)
        return n
    logger.info("ChromaDB is empty at %s — seeding synthetic listings ...", resolved)
    seed(chroma_path=resolved, embedding_model=embedding_model)
    collection = client.get_collection("property_listings", embedding_function=embed_fn)
    return collection.count()


def seed(chroma_path: str, embedding_model: str) -> None:
    p = Path(chroma_path)
    resolved = str(p.resolve() if p.is_absolute() else (_SERVICE_DIR / p).resolve())
    logger.info("Connecting to ChromaDB at %s ...", resolved)
    client = chromadb.PersistentClient(path=resolved, settings=Settings(anonymized_telemetry=False))

    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=embedding_model
    )

    # Delete existing collection so the script is idempotent
    try:
        client.delete_collection("property_listings")
        logger.info("Deleted existing 'property_listings' collection.")
    except Exception:
        pass

    collection = client.create_collection(
        name="property_listings",
        embedding_function=embed_fn,
    )
    logger.info("Created fresh 'property_listings' collection.")

    ids = [l["listing_id"] for l in LISTINGS]
    documents = [l["text"] for l in LISTINGS]
    metadatas = [
        {
            "listing_id": l["listing_id"],
            "title": l["title"],
            "property_type": l["property_type"],
        }
        for l in LISTINGS
    ]

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    logger.info("Seeded %d listings into ChromaDB.", len(LISTINGS))
    logger.info("Done. Collection now contains %d documents at %s.", collection.count(), resolved)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed ChromaDB with synthetic property listings")
    parser.add_argument("--chroma-path", default="./chroma_db", help="Path to ChromaDB storage directory")
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="HuggingFace sentence-transformer model name",
    )
    args = parser.parse_args()
    seed(chroma_path=args.chroma_path, embedding_model=args.embedding_model)
