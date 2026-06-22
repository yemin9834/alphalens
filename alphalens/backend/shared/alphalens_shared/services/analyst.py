"""Opportunity ranking service."""

from __future__ import annotations

from typing import Any, Dict, List

from alphalens_metrics.opportunity_ranking_service import OpportunityRankingService


def run_analyst(payload: Dict[str, Any]) -> Dict[str, Any]:
    candidates = payload.get("candidates", [])
    risk_profile = payload.get("riskProfile", "balanced")
    market_condition = payload.get("marketCondition")

    ranking = OpportunityRankingService().rank(
        candidates=candidates,
        risk_profile=risk_profile,
        market_condition=market_condition,
    )

    ranked_api = [_to_ranked_candidate(row) for row in ranking["rankedCandidates"]]
    from alphalens_shared.json_utils import sanitize_for_json

    from alphalens_shared.services.analyst_report import attach_analysis_report

    result = sanitize_for_json(
        {
            "success": True,
            "marketCondition": ranking["marketCondition"],
            "rankedCandidates": ranked_api,
            "rankedPayload": ranking,
        }
    )
    return attach_analysis_report(result, risk_profile)


def _to_ranked_candidate(row: Dict[str, Any]) -> Dict[str, Any]:
    metrics = row.get("metrics", {})
    momentum = metrics.get("momentum", "Unknown")
    valuation = metrics.get("valuation", "Unknown")
    vol = metrics.get("volatilityRisk", "Unknown")

    opportunity_view = "Neutral"
    if row.get("opportunityScore", 0) >= 70:
        opportunity_view = "Attractive"
    elif row.get("opportunityScore", 0) < 45:
        opportunity_view = "Unattractive"

    positive = (
        f"Momentum is {momentum.lower()}" if momentum != "Unknown" else "Limited momentum data"
    )
    risk = f"Volatility risk is {vol.lower()}" if vol != "Unknown" else "Risk data limited"

    return {
        "ticker": row.get("ticker", ""),
        "companyName": row.get("companyName", row.get("ticker", "")),
        "opportunityView": opportunity_view,
        "entryAttractiveness": metrics.get("entryAttractiveness", "Unknown"),
        "attractiveEntryReason": row.get("rankReason", ""),
        "downsideRisk": metrics.get("downsideRisk", "Unknown"),
        "confidence": row.get("confidence", "Medium"),
        "positiveSignal": positive if opportunity_view != "Unattractive" else "No strong positive signal",
        "riskSignal": risk,
        "suggestedEntryRange": metrics.get("suggestedEntryRange", "Data unavailable"),
        "riskInvalidationLevel": metrics.get("riskInvalidationLevel", "Data unavailable"),
        "opportunityScore": row.get("opportunityScore"),
        "metrics": metrics,
    }
