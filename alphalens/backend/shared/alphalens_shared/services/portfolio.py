"""Portfolio-aware recommendation service."""

from __future__ import annotations

from typing import Any, Dict, List

from alphalens_metrics.action_plan_service import ActionPlanService
from alphalens_metrics.portfolio_risk_engine import PortfolioRiskEngine

from alphalens_shared.services.portfolio_report import build_deterministic_portfolio_report


def run_portfolio(payload: Dict[str, Any]) -> Dict[str, Any]:
    portfolio = payload.get("portfolio", [])
    ranked = payload.get("rankedCandidates", [])
    risk_profile = payload.get("riskProfile", "balanced")
    market_condition = payload.get("marketCondition", "Neutral")

    risk_engine = PortfolioRiskEngine()
    portfolio_risk = risk_engine.analyze(portfolio, risk_profile)

    ranked_payload = payload.get("rankedPayload")
    if ranked_payload:
        ranked_for_plan = ranked_payload.get("rankedCandidates", ranked)
    else:
        ranked_for_plan = ranked

    plan = ActionPlanService().build(
        portfolio=portfolio,
        ranked_candidates=ranked_for_plan,
        portfolio_risk=portfolio_risk,
        risk_profile=risk_profile,
        market_condition=market_condition,
    )

    recommendation = _to_api_response(plan, ranked, portfolio_risk, market_condition)
    return attach_portfolio_report(
        {
            "success": True,
            "recommendation": recommendation,
            "recommendationPayload": plan,
        }
    )


def attach_portfolio_report(result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach deterministic portfolioReport (default)."""
    result["portfolioReport"] = build_deterministic_portfolio_report(result)
    return result


def run_portfolio_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic portfolio plan + optional LLM narrative (mock / local path)."""
    from alphalens_shared.services.portfolio_narrative import maybe_enrich_portfolio_narrative

    return maybe_enrich_portfolio_narrative(payload, run_portfolio(payload))


def _to_api_response(
    plan: Dict[str, Any],
    ranked: List[Dict[str, Any]],
    portfolio_risk: Dict[str, Any],
    market_condition: str,
) -> Dict[str, Any]:
    holdings = {a["ticker"]: a for a in plan.get("actions", [])}

    candidate_recs = []
    for row in ranked[:8]:
        ticker = row.get("ticker", "")
        action = holdings.get(ticker, {})
        fit = "Moderate fit"
        if action.get("action") == "Add":
            fit = "Strong fit — consider adding"
        elif action.get("action") == "Trim":
            fit = "Weak fit — consider trimming"

        candidate_recs.append(
            {
                "ticker": ticker,
                "view": row.get("opportunityView", "Neutral"),
                "portfolioFit": fit,
                "positiveSignal": row.get("positiveSignal", ""),
                "riskSignal": row.get("riskSignal", ""),
                "suggestedEntryRange": row.get(
                    "suggestedEntryRange", "Data unavailable"
                ),
                "positionSizingGuidance": _sizing_guidance(action),
            }
        )

    actions = []
    for action in plan.get("actions", []):
        delta = action.get("suggestedWeight", 0) - action.get("currentWeight", 0)
        ticker = action.get("ticker", "")
        entry_range = action.get("suggestedEntryRange")
        actions.append(
            {
                "type": action.get("action", "Hold"),
                "ticker": ticker,
                "amount": round(abs(delta), 2),
                "reason": action.get("rationale", ""),
                "suggestedEntryRange": entry_range if entry_range != "N/A" else None,
            }
        )

    return {
        "finalView": plan.get("summary", ""),
        "riskLevel": portfolio_risk.get("riskLevel", "Unknown"),
        "marketCondition": market_condition,
        "portfolioSignals": {
            "concentrationRisk": portfolio_risk.get("concentrationRisk", "Unknown"),
            "sectorExposure": portfolio_risk.get("sectorExposure", "Unknown"),
            "cashBuffer": portfolio_risk.get("cashBuffer", "Unknown"),
            "volatilityRisk": portfolio_risk.get("volatilityRisk", "Unknown"),
        },
        "candidateRecommendations": candidate_recs,
        "actions": actions,
    }


def _sizing_guidance(action: Dict[str, Any]) -> str:
    if not action:
        return "No change suggested"
    current = action.get("currentWeight", 0)
    target = action.get("suggestedWeight", 0)
    verb = action.get("action", "Hold")
    if verb == "Hold":
        return f"Maintain around {current:.1f}%"
    return f"{verb} toward {target:.1f}% (from {current:.1f}%)"
