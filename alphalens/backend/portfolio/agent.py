"""
Portfolio advisor agent — deterministic action plan + optional LLM narrative.

Add/Trim/Hold actions always come from ActionPlanService + PortfolioRiskEngine.
LLM only enriches portfolioReport / narrative text when USE_LLM_PORTFOLIO_NARRATIVE=true
(legacy alias: USE_LLM_PORTFOLIO).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from alphalens_metrics.action_plan_service import ActionPlanService
from alphalens_metrics.portfolio_risk_engine import PortfolioRiskEngine

from alphalens_shared.services.portfolio import run_portfolio
from alphalens_shared.services.portfolio_narrative import maybe_enrich_portfolio_narrative

from templates import PORTFOLIO_INSTRUCTIONS

AGENT_NAME = "Portfolio Advisor"
INSTRUCTIONS = PORTFOLIO_INSTRUCTIONS

USE_LLM_PORTFOLIO_NARRATIVE = (
    os.getenv("USE_LLM_PORTFOLIO_NARRATIVE", "").lower() == "true"
    or os.getenv("USE_LLM_PORTFOLIO", "false").lower() == "true"
)


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    from alphalens_shared.bedrock_agent import log_agent_mode

    log_agent_mode(AGENT_NAME, llm=USE_LLM_PORTFOLIO_NARRATIVE)
    result = run_portfolio(payload)
    return maybe_enrich_portfolio_narrative(payload, result)


def create_agent(*_args: Any, **_kwargs: Any):
    raise NotImplementedError(
        "Portfolio uses run(payload). Optional LLM narrative is enabled with "
        "USE_LLM_PORTFOLIO_NARRATIVE (or legacy USE_LLM_PORTFOLIO)."
    )


def analyze_risk(portfolio: List[Dict[str, Any]], risk_profile: str = "balanced") -> Dict[str, Any]:
    return PortfolioRiskEngine().analyze(portfolio, risk_profile)


def build_action_plan(
    portfolio: List[Dict[str, Any]],
    ranked_candidates: List[Dict[str, Any]],
    risk_profile: str = "balanced",
    market_condition: str = "Neutral",
) -> Dict[str, Any]:
    risk = analyze_risk(portfolio, risk_profile)
    return ActionPlanService().build(
        portfolio=portfolio,
        ranked_candidates=ranked_candidates,
        portfolio_risk=risk,
        risk_profile=risk_profile,
        market_condition=market_condition,
    )


__all__ = [
    "AGENT_NAME",
    "INSTRUCTIONS",
    "create_agent",
    "run",
    "analyze_risk",
    "build_action_plan",
]
