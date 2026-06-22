#!/usr/bin/env python3
"""Full test for Analyst agent via deployed Lambda."""

import json
import os

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

FUNCTION_NAME = os.getenv("ANALYST_FUNCTION", "alphalens-analyst")
NARRATIVE_FLAG = os.getenv("USE_LLM_ANALYST_NARRATIVE", "false").lower() == "true"


def main():
    print("Testing Analyst Lambda")
    print("=" * 60)
    print(f"USE_LLM_ANALYST_NARRATIVE (local .env): {NARRATIVE_FLAG}")
    print("(Set the same flag on alphalens-analyst in AWS for Lambda-side narrative)")
    print("(Uses yfinance in Lambda — may take 15-45 seconds with narrative)")

    payload = {
        "riskProfile": "balanced",
        "candidates": [
            {
                "ticker": "TSM",
                "relationshipType": "supplier",
                "tickerValidation": "validated",
                "confidence": "High",
            },
            {
                "ticker": "MSFT",
                "relationshipType": "partner",
                "tickerValidation": "validated",
                "confidence": "High",
            },
        ],
    }

    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    result = json.loads(response["Payload"].read())

    if isinstance(result, dict) and result.get("statusCode") == 200:
        body = json.loads(result["body"])
        ranked = body.get("rankedCandidates", [])
        report = body.get("analysisReport") or {}
        warnings = body.get("warnings", [])

        print(f"✅ Analyst OK — ranked {len(ranked)} candidates")
        for row in ranked[:3]:
            print(f"   {row['ticker']}: {row.get('opportunityView')}")

        if report:
            note = report.get("methodologyNote", "")
            llm_like = "no LLM" not in note.lower()
            print(f"\nAnalysis report ({'LLM' if llm_like else 'deterministic'}):")
            print(f"   {report.get('executiveSummary', '')[:200]}...")
            if report.get("topOpportunities"):
                top = report["topOpportunities"][0]
                print(f"   Top: {top.get('ticker')} — {top.get('summary', '')[:100]}...")
        else:
            print("\n⚠️  No analysisReport in response")

        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print(f"   - {w}")

        if NARRATIVE_FLAG and report and "no LLM" in report.get("methodologyNote", "").lower():
            print(
                "\n💡 Narrative flag is on locally but response looks deterministic. "
                "Set USE_LLM_ANALYST_NARRATIVE=true on alphalens-analyst Lambda "
                "and terraform apply, then repackage/redeploy analyst zip."
            )
            return 1

        return 0

    print(json.dumps(result, indent=2))
    print("\n❌ Analyst test failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
