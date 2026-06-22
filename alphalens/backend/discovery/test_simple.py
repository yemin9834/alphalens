#!/usr/bin/env python3
"""Simple local test for Discovery agent (curated fallback)."""

import json
import os

from dotenv import load_dotenv

load_dotenv(override=True)

from alphalens_shared.test_logging import configure_test_logging

configure_test_logging()

from lambda_handler import lambda_handler


def main():
    print("Testing Discovery Agent...")
    print("=" * 60)

    result = lambda_handler(
        {"coreCompany": "NVIDIA", "coreTicker": "NVDA", "scope": "level-1"},
        None,
    )
    print(f"Status Code: {result['statusCode']}")

    body = json.loads(result["body"])
    candidates = body.get("candidates", [])
    print(f"Core: {body.get('coreCompany')} ({body.get('coreTicker')})")
    print(f"Candidates: {len(candidates)}")
    for row in candidates:
        print(f"  {row.get('ticker')}: {row.get('relationshipType')}")

    warnings = body.get("warnings", [])
    if warnings:
        print(f"Warnings: {warnings[0]}")

    print("=" * 60)
    return 0 if result["statusCode"] == 200 and candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
