#!/usr/bin/env python3
"""Test live discovery service via DISCOVERY_SERVICE_URL (local or AWS)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv(override=True)

DISCOVERY_PAYLOAD = {
    "coreCompany": "NVIDIA",
    "coreTicker": "NVDA",
    "scope": "level-1",
}


def test_live_discovery(service_url: str | None = None, *, timeout: int = 300) -> int:
    """
    POST /discover on the live discovery service (alphalens-discovery-live or local uvicorn).

    Returns 0 on success, 1 on failure.
    """
    url = (service_url or os.getenv("DISCOVERY_SERVICE_URL", "")).strip().rstrip("/")
    if not url:
        print("Set DISCOVERY_SERVICE_URL in alphalens/.env")
        return 1

    print(f"Testing live discovery at {url}")
    print("=" * 60)

    health_url = f"{url}/health"
    with urllib.request.urlopen(health_url, timeout=30) as resp:
        health = json.loads(resp.read().decode())
    print(f"Health: {health}")

    data = json.dumps(DISCOVERY_PAYLOAD).encode()
    req = urllib.request.Request(
        f"{url}/discover",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode()}")
        return 1

    candidates = result.get("candidates", [])
    print(f"✅ Live discovery OK — {len(candidates)} candidates")
    for c in candidates[:5]:
        print(f"  - {c.get('ticker')}: {c.get('companyName')}")
    if result.get("warnings"):
        print("Warnings:", result["warnings"])
    return 0


def main() -> int:
    return test_live_discovery()


if __name__ == "__main__":
    raise SystemExit(main())
