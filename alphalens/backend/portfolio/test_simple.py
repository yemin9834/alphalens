#!/usr/bin/env python3
"""Simple local test for Portfolio agent."""

import json
import os

from dotenv import load_dotenv

load_dotenv(override=True)
os.environ.setdefault("MOCK_LAMBDAS", "true")

from alphalens_shared.test_logging import configure_test_logging

configure_test_logging()

from lambda_handler import lambda_handler

PORTFOLIO = [
    {"ticker": "NVDA", "weight": 35},
    {"ticker": "MSFT", "weight": 25},
    {"ticker": "CASH", "weight": 40},
]

RANKED = [
    {
        "ticker": "TSM",
        "companyName": "TSMC",
        "opportunityView": "Attractive",
        "opportunityScore": 72,
        "rankReason": "Strong supplier exposure",
        "positiveSignal": "Momentum positive",
        "riskSignal": "Volatility medium",
        "metrics": {
            "entryAttractiveness": "Medium",
            "suggestedEntryRange": "100 - 110",
            "riskInvalidationLevel": "Below 95",
        },
    }
]


def main():
    print("Testing Portfolio Agent...")
    print("=" * 60)

    result = lambda_handler(
        {
            "riskProfile": "balanced",
            "portfolio": PORTFOLIO,
            "rankedCandidates": RANKED,
            "marketCondition": "Neutral",
        },
        None,
    )
    print(f"Status Code: {result['statusCode']}")

    body = json.loads(result["body"])
    rec = body.get("recommendation", {})
    print(f"Risk level: {rec.get('riskLevel')}")
    print(f"Final view: {rec.get('finalView', '')[:120]}...")
    print(f"Actions: {len(rec.get('actions', []))}")
    for action in rec.get("actions", [])[:3]:
        print(f"  {action.get('type')} {action.get('ticker')}: {action.get('reason', '')[:60]}")

    report = body.get("portfolioReport")
    if report:
        print(f"Portfolio report: {report.get('executiveSummary', '')[:120]}...")

    print("=" * 60)
    return 0 if result["statusCode"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
