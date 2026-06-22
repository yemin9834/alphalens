#!/usr/bin/env python3
"""Simple local test for Analyst agent."""

import json
import os

from dotenv import load_dotenv

load_dotenv(override=True)
os.environ.setdefault("MOCK_LAMBDAS", "true")

from alphalens_shared.test_logging import configure_test_logging

configure_test_logging()

from lambda_handler import lambda_handler

CANDIDATES = [
    {
        "companyName": "Taiwan Semiconductor",
        "ticker": "TSM",
        "relationshipType": "supplier",
        "relationshipSummary": "Chip manufacturing",
        "confidence": "High",
        "evidenceUrl": "demo",
        "tickerValidation": "validated",
    },
    {
        "companyName": "Broadcom",
        "ticker": "AVGO",
        "relationshipType": "ecosystem",
        "relationshipSummary": "Networking silicon",
        "confidence": "Medium",
        "evidenceUrl": "demo",
        "tickerValidation": "validated",
    },
]


def main():
    print("Testing Analyst Agent...")
    print("=" * 60)
    print("(Uses yfinance — may take 10-20 seconds)")

    result = lambda_handler(
        {"riskProfile": "balanced", "candidates": CANDIDATES},
        None,
    )
    print(f"Status Code: {result['statusCode']}")

    body = json.loads(result["body"])
    ranked = body.get("rankedCandidates", [])
    print(f"Market condition: {body.get('marketCondition', 'N/A')}")
    print(f"Ranked: {len(ranked)} candidates")
    for row in ranked[:5]:
        print(
            f"  #{row.get('rank', '?')} {row['ticker']}: "
            f"score={row.get('opportunityScore', 'N/A')} view={row.get('opportunityView')}"
        )

    report = body.get("analysisReport")
    if report:
        print(f"\nAnalysis report: {report.get('executiveSummary', '')[:120]}...")
    else:
        print("\n⚠️  No analysisReport in response")

    print("=" * 60)
    return 0 if result["statusCode"] == 200 and ranked and report else 1


if __name__ == "__main__":
    raise SystemExit(main())
