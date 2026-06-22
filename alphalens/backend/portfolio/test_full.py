#!/usr/bin/env python3
"""Full test for Portfolio agent via deployed Lambda."""

import json
import os

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

FUNCTION_NAME = os.getenv("PORTFOLIO_FUNCTION", "alphalens-portfolio")
NARRATIVE_FLAG = (
    os.getenv("USE_LLM_PORTFOLIO_NARRATIVE", "").lower() == "true"
    or os.getenv("USE_LLM_PORTFOLIO", "false").lower() == "true"
)


def _report_is_llm(report: dict) -> bool:
    note = report.get("methodologyNote", "")
    return bool(note) and "not from an llm" not in note.lower()


def main():
    print("Testing Portfolio Lambda")
    print("=" * 60)
    print(f"USE_LLM_PORTFOLIO_NARRATIVE / USE_LLM_PORTFOLIO (local .env): {NARRATIVE_FLAG}")
    print(
        "(Set the same flag on alphalens-portfolio in AWS for Lambda-side narrative; "
        "may take 10-30s with LLM)"
    )

    payload = {
        "riskProfile": "balanced",
        "marketCondition": "Neutral",
        "portfolio": [
            {"ticker": "NVDA", "weight": 30},
            {"ticker": "CASH", "weight": 70},
        ],
        "rankedCandidates": [
            {
                "ticker": "MSFT",
                "companyName": "Microsoft",
                "opportunityView": "Attractive",
                "opportunityScore": 68,
                "rankReason": "Partner exposure",
                "positiveSignal": "Momentum positive",
                "riskSignal": "Volatility low",
                "metrics": {
                    "entryAttractiveness": "Medium",
                    "suggestedEntryRange": "400 - 420",
                    "riskInvalidationLevel": "Below 380",
                },
            }
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
        rec = body.get("recommendation", {})
        report = body.get("portfolioReport") or {}
        warnings = body.get("warnings", [])
        actions = rec.get("actions", [])

        print(f"✅ Portfolio OK — risk={rec.get('riskLevel')}")
        print(f"   Actions: {len(actions)}")
        for action in actions[:3]:
            line = f"   {action.get('type')} {action.get('ticker')}"
            if action.get("amount"):
                line += f" ({action.get('amount')}%)"
            print(line)
            reason = action.get("reason", "")
            if reason:
                print(f"      reason: {reason[:80]}...")
            if action.get("narrativeReason"):
                print(f"      narrative: {action['narrativeReason'][:80]}...")

        print(f"\nFinal view: {rec.get('finalView', '')[:200]}...")

        signals = rec.get("portfolioSignals") or {}
        if signals:
            print(
                f"\nPortfolio signals: concentration={signals.get('concentrationRisk')}, "
                f"sector={signals.get('sectorExposure')}"
            )

        if report:
            llm_like = _report_is_llm(report)
            print(f"\nPortfolio report ({'LLM' if llm_like else 'deterministic'}):")
            print(f"   {report.get('executiveSummary', '')[:200]}...")
            if report.get("actionNotes"):
                note = report["actionNotes"][0]
                print(
                    f"   Action note: {note.get('type')} {note.get('ticker')} — "
                    f"{note.get('summary', '')[:100]}..."
                )
            if report.get("candidateNotes"):
                cand = report["candidateNotes"][0]
                print(f"   Candidate note: {cand.get('ticker')} — {cand.get('summary', '')[:100]}...")
            if report.get("portfolioSignalsSummary"):
                print(f"   Signals summary: {report['portfolioSignalsSummary'][:120]}...")
        else:
            print("\n⚠️  No portfolioReport in response")

        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"   - {warning}")

        if NARRATIVE_FLAG and report and not _report_is_llm(report):
            print(
                "\n💡 Narrative flag is on locally but response looks deterministic. "
                "Set USE_LLM_PORTFOLIO_NARRATIVE=true (or USE_LLM_PORTFOLIO=true) on "
                "alphalens-portfolio Lambda, terraform apply, then repackage/redeploy "
                "portfolio zip (cd backend/portfolio && uv run package_docker.py)."
            )
            return 1

        return 0

    print(json.dumps(result, indent=2))
    print("\n❌ Portfolio test failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
