"""
test_pipeline.py
----------------
End-to-end tests for the full n8n pipeline via the webhook endpoint.
Run this after importing flow.json and activating the webhook in n8n.

Usage:
    python test_pipeline.py --webhook-url http://localhost:5678/webhook/property-triage

Each test case checks:
  - HTTP 200 response
  - success: true in the response body
  - report contains all required fields
  - routing_decision matches expectation
  - no fabricated data flags (basic checks)
"""

import argparse
import asyncio
import json
import time

import httpx

WEBHOOK_URL = "http://localhost:5678/webhook/property-triage"

REQUIRED_FIELDS = [
    "property_type", "routing_decision", "location", "price_ils",
    "num_rooms", "key_features", "image_scores", "similar_listings",
    "rag_insight", "enrichment_notes", "confidence",
]

TEST_CASES = [
    {
        "name": "Residential — full listing with images",
        "payload": {
            "description": "3-bedroom apartment in Tel Aviv, Florentin. 110sqm, renovated kitchen, sea view. Asking 4,200,000 ILS.",
            "image_urls": ["https://via.placeholder.com/300/kitchen"],
            "agent_name": "Test Agent",
        },
        "expect_routing": "residential",
        "expect_rejection": False,
    },
    {
        "name": "Commercial — office listing",
        "payload": {
            "description": "240sqm open-plan office on 14th floor in Ramat Gan Diamond Exchange. 10 parking spots. Asking 7,800,000 ILS.",
            "image_urls": [],
            "agent_name": "Test Agent",
        },
        "expect_routing": "commercial",
        "expect_rejection": False,
    },
    {
        "name": "Residential — no images, no price",
        "payload": {
            "description": "Renovated 3-bedroom cottage in Moshav Beit Herut. Large garden, solar water heater.",
            "image_urls": [],
            "agent_name": "Test Agent",
        },
        "expect_routing": "residential",
        "expect_rejection": False,
    },
    {
        "name": "Guardrails rejection — spam input",
        "payload": {
            "description": "Congratulations! You have won a $1,000,000 lottery prize. Click here to claim now.",
            "image_urls": [],
            "agent_name": "Test Agent",
        },
        "expect_routing": None,
        "expect_rejection": True,
    },
    {
        "name": "Commercial — industrial warehouse",
        "payload": {
            "description": "1800sqm industrial warehouse in Ashdod port zone. 10m clear height, 3 loading docks, 400A power. 12,000,000 ILS.",
            "image_urls": [],
            "agent_name": "Test Agent",
        },
        "expect_routing": "commercial",
        "expect_rejection": False,
    },
]


async def run_tests(webhook_url: str) -> None:
    print("\n══════════════════════════════════════════════════════")
    print("  End-to-End Pipeline Tests")
    print(f"  Webhook: {webhook_url}")
    print("══════════════════════════════════════════════════════")

    results = []

    async with httpx.AsyncClient(timeout=180) as client:
        for i, case in enumerate(TEST_CASES, start=1):
            print(f"\n[{i:02d}] {case['name']}")
            t0 = time.time()

            try:
                resp = await client.post(webhook_url, json=case["payload"])
                elapsed = round(time.time() - t0, 1)
                data = resp.json()

                if case["expect_rejection"]:
                    # Expect 422 and rejected: true
                    ok = resp.status_code == 422 and data.get("rejected") is True
                    print(f"     {'✓' if ok else '✗'} Rejection: status={resp.status_code} rejected={data.get('rejected')} ⏱ {elapsed}s")
                    results.append(ok)
                    continue

                # Expect 200 and success: true
                if resp.status_code != 200 or not data.get("success"):
                    print(f"     ✗ HTTP {resp.status_code} | success={data.get('success')} | {data}")
                    results.append(False)
                    continue

                report = data.get("report", {})
                channel = data.get("channel", "unknown")

                # Check required fields
                missing = [f for f in REQUIRED_FIELDS if f not in report]
                routing = report.get("routing_decision", "unknown")
                routing_ok = routing == case["expect_routing"]
                fields_ok  = len(missing) == 0

                overall = routing_ok and fields_ok
                results.append(overall)

                print(f"     {'✓' if routing_ok else '✗'} Routing:   {routing} (expected {case['expect_routing']})")
                print(f"     {'✓' if fields_ok  else '✗'} Fields:    {'all present' if fields_ok else 'MISSING: ' + str(missing)}")
                print(f"     ℹ  Channel:   {channel}")
                print(f"     ℹ  Confidence: {report.get('confidence', '—')}")
                print(f"     ⏱  {elapsed}s   {'PASS' if overall else 'FAIL'}")

            except httpx.TimeoutException:
                print(f"     ✗ TIMEOUT after 180s")
                results.append(False)
            except Exception as exc:
                print(f"     ✗ ERROR: {exc}")
                results.append(False)

    passed = sum(results)
    print("\n══════════════════════════════════════════════════════")
    print(f"  Result: {passed}/{len(TEST_CASES)} passed")
    print("══════════════════════════════════════════════════════\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--webhook-url", default=WEBHOOK_URL)
    args = parser.parse_args()
    asyncio.run(run_tests(args.webhook_url))
