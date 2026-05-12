"""
benchmark.py
------------
Runs 10 benchmark queries against the LangGraph agent service and
measures tool-call accuracy, routing decisions, and report completeness.

Use this to track improvement across tool description iterations.
Log results in: prompt_logs/agent_prompt_log.md

Usage:
    python benchmark.py --base-url http://localhost:8004
"""

import argparse
import asyncio
import json
import time

import httpx

BASE_URL = "http://localhost:8004"

# ---------------------------------------------------------------------------
# 10 benchmark queries
# Each entry defines:
#   description   : listing text
#   image_urls    : list of URLs (empty = no images)
#   expect_rag    : True if rag_query should be called
#   expect_images : True if analyse_images should be called
#   expect_routing: "residential" or "commercial"
# ---------------------------------------------------------------------------

BENCHMARKS = [
    {
        "name": "Full residential listing with images",
        "description": "3-bedroom apartment in Tel Aviv, 110sqm, renovated kitchen, sea view. Asking 4.2M ILS.",
        "image_urls": ["https://via.placeholder.com/300/kitchen", "https://via.placeholder.com/300/bedroom"],
        "expect_rag": True,
        "expect_images": True,
        "expect_routing": "residential",
    },
    {
        "name": "Residential listing — no images",
        "description": "2-bedroom apartment in Haifa Carmel, 75sqm, new building, energy rating A. 2.4M ILS.",
        "image_urls": [],
        "expect_rag": True,
        "expect_images": False,
        "expect_routing": "residential",
    },
    {
        "name": "Commercial office listing",
        "description": "240sqm open-plan office in Ramat Gan Diamond Exchange, 14th floor, 10 parking spots. 7.8M ILS.",
        "image_urls": [],
        "expect_rag": True,
        "expect_images": False,
        "expect_routing": "commercial",
    },
    {
        "name": "Villa with pool — multiple images",
        "description": "5-bedroom villa in Savyon, 600sqm, heated pool, landscaped garden, smart-home. 18.5M ILS.",
        "image_urls": [
            "https://via.placeholder.com/300/exterior",
            "https://via.placeholder.com/300/living",
            "https://via.placeholder.com/300/pool",
        ],
        "expect_rag": True,
        "expect_images": True,
        "expect_routing": "residential",
    },
    {
        "name": "Retail unit — commercial routing",
        "description": "85sqm ground-floor retail unit in central Jerusalem, glass frontage, leased to café. 3.1M ILS.",
        "image_urls": [],
        "expect_rag": True,
        "expect_images": False,
        "expect_routing": "commercial",
    },
    {
        "name": "Listing with no price mentioned",
        "description": "Renovated 3-bedroom cottage in Moshav Beit Herut, 800sqm plot, solar water heater.",
        "image_urls": [],
        "expect_rag": True,
        "expect_images": False,
        "expect_routing": "residential",
    },
    {
        "name": "Industrial warehouse — commercial",
        "description": "1800sqm industrial warehouse in Ashdod port zone, 10m clear height, 3 loading docks. 12M ILS.",
        "image_urls": [],
        "expect_rag": True,
        "expect_images": False,
        "expect_routing": "commercial",
    },
    {
        "name": "Penthouse with roof garden + images",
        "description": "3BR penthouse in Rehovot, 130sqm + 90sqm roof garden, community pool. 5.1M ILS.",
        "image_urls": [
            "https://via.placeholder.com/300/terrace",
            "https://via.placeholder.com/300/bathroom",
        ],
        "expect_rag": True,
        "expect_images": True,
        "expect_routing": "residential",
    },
    {
        "name": "Very short listing — minimal data",
        "description": "Studio apartment, Beer Sheva, 38sqm. 650K ILS.",
        "image_urls": [],
        "expect_rag": True,
        "expect_images": False,
        "expect_routing": "residential",
    },
    {
        "name": "Historic stone house — unusual property",
        "description": "3BR stone house in Old Jaffa, 140sqm, vaulted ceilings, courtyard, protected facade. 6.5M ILS.",
        "image_urls": ["https://via.placeholder.com/300/exterior"],
        "expect_rag": True,
        "expect_images": True,
        "expect_routing": "residential",
    },
]

REQUIRED_REPORT_FIELDS = [
    "property_type", "routing_decision", "location", "price_ils",
    "num_rooms", "key_features", "image_scores", "similar_listings",
    "rag_insight", "enrichment_notes", "confidence",
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_benchmark(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        results = []

        print("\n══════════════════════════════════════════════════════════════")
        print("  LangGraph Agent Benchmark — Iteration 1")
        print("══════════════════════════════════════════════════════════════")

        for i, case in enumerate(BENCHMARKS, start=1):
            print(f"\n[{i:02d}] {case['name']}")
            t0 = time.time()

            try:
                resp = await client.post(
                    "/agent/run",
                    json={
                        "description": case["description"],
                        "image_urls":  case["image_urls"],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                elapsed = round(time.time() - t0, 1)

                report   = data.get("report", {})
                rag_got  = data.get("rag_retrieved", 0) > 0
                img_got  = data.get("images_analysed", 0) > 0
                routing  = report.get("routing_decision", "unknown")

                # Check expectations
                rag_ok     = rag_got  == case["expect_rag"]
                img_ok     = img_got  == case["expect_images"]
                routing_ok = routing  == case["expect_routing"]

                # Check all required fields present
                missing = [f for f in REQUIRED_REPORT_FIELDS if f not in report]
                fields_ok = len(missing) == 0

                overall = rag_ok and img_ok and routing_ok and fields_ok

                print(f"     {'✓' if rag_ok     else '✗'} RAG called:      {rag_got}  (expected {case['expect_rag']})")
                print(f"     {'✓' if img_ok     else '✗'} Images called:   {img_got}  (expected {case['expect_images']})")
                print(f"     {'✓' if routing_ok else '✗'} Routing:         {routing}  (expected {case['expect_routing']})")
                print(f"     {'✓' if fields_ok  else '✗'} All fields:      {'yes' if fields_ok else 'MISSING: ' + str(missing)}")
                print(f"     ⏱  {elapsed}s   {'PASS' if overall else 'FAIL'}")

                results.append(overall)

            except Exception as exc:
                print(f"     ✗ ERROR: {exc}")
                results.append(False)

        passed = sum(results)
        print("\n══════════════════════════════════════════════════════════════")
        print(f"  Result: {passed}/{len(BENCHMARKS)} passed")
        print("══════════════════════════════════════════════════════════════\n")
        print("Log these results as Version 1 in prompt_logs/agent_prompt_log.md\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.base_url))
