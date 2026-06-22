#!/usr/bin/env python3
"""Simple local test for Validator agent."""

import json
import os

from dotenv import load_dotenv

load_dotenv(override=True)
os.environ.setdefault("MOCK_LAMBDAS", "true")

from alphalens_shared.test_logging import configure_test_logging

configure_test_logging()

from lambda_handler import lambda_handler

SAMPLE_CANDIDATES = [
    {
        "companyName": "Taiwan Semiconductor",
        "ticker": "TSM",
        "relationshipType": "supplier",
        "relationshipSummary": "Manufacturing partner",
        "confidence": "High",
        "evidenceUrl": "demo",
    },
    {
        "companyName": "Not A Real Ticker",
        "ticker": "!!!",
        "relationshipType": "supplier",
        "relationshipSummary": "Invalid format",
        "confidence": "Low",
        "evidenceUrl": "demo",
    },
]


def main():
    print("Testing Validator Agent...")
    print("=" * 60)

    result = lambda_handler({"candidates": SAMPLE_CANDIDATES}, None)
    print(f"Status Code: {result['statusCode']}")

    body = json.loads(result["body"])
    validated = body.get("validatedCandidates", [])
    print(f"Validated: {len(validated)} candidates")
    for row in validated:
        reason = row.get("validationReason", "")
        print(f"  {row['ticker']}: {row.get('tickerValidation', 'unknown')} — {reason}")

    report = body.get("validationReport")
    if report:
        print(f"Validation report: {report.get('executiveSummary', '')[:120]}...")

    print("=" * 60)
    return 0 if result["statusCode"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
