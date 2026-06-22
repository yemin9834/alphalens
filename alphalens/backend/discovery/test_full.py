#!/usr/bin/env python3
"""
Full AWS discovery test — same routing as the orchestrator.

When DISCOVERY_SERVICE_URL is set: tests alphalens-discovery-live (HTTP, LLM + MCP).
Otherwise: invokes slim alphalens-discovery Lambda (curated JSON fallback).
"""

from __future__ import annotations

import json
import os

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

FUNCTION_NAME = os.getenv("DISCOVERY_FUNCTION", "alphalens-discovery")
SERVICE_URL = os.getenv("DISCOVERY_SERVICE_URL", "").strip().rstrip("/")

DISCOVERY_PAYLOAD = {
    "coreCompany": "NVIDIA",
    "coreTicker": "NVDA",
    "scope": "level-1",
}


def test_curated_lambda() -> int:
    """Invoke slim alphalens-discovery zip Lambda (Guide 3 MVP)."""
    print(f"Testing curated discovery Lambda ({FUNCTION_NAME})")
    print("=" * 60)

    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(DISCOVERY_PAYLOAD),
    )
    result = json.loads(response["Payload"].read())

    if isinstance(result, dict) and result.get("statusCode") == 200:
        body = json.loads(result["body"])
        print(f"✅ Curated discovery OK — {len(body.get('candidates', []))} candidates")
        return 0

    print(json.dumps(result, indent=2))
    print("\n❌ Curated discovery test failed")
    return 1


def main() -> int:
    if SERVICE_URL:
        print("DISCOVERY_SERVICE_URL is set — testing live discovery (alphalens-discovery-live)")
        print()
        from test_service import test_live_discovery

        return test_live_discovery(SERVICE_URL)

    print("DISCOVERY_SERVICE_URL not set — testing slim curated Lambda")
    print("(Set DISCOVERY_SERVICE_URL in alphalens/.env to test live MCP discovery)")
    print()
    return test_curated_lambda()


if __name__ == "__main__":
    raise SystemExit(main())
