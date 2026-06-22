"""
Analyst agent — deterministic rankings + optional LLM narrative on the same Lambda.

Rankings use yfinance. When USE_LLM_ANALYST_NARRATIVE=true, a slim OpenAI/Bedrock call
summarizes rankedPayload (no litellm — fits the analyst zip).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from alphalens_shared.services.analyst import run_analyst
from alphalens_shared.services.analyst_narrative import maybe_enrich_analyst_narrative
from alphalens_metrics.opportunity_ranking_service import OpportunityRankingService

from templates import ANALYST_INSTRUCTIONS

AGENT_NAME = "Analyst"
INSTRUCTIONS = ANALYST_INSTRUCTIONS

USE_LLM_ANALYST_NARRATIVE = os.getenv("USE_LLM_ANALYST_NARRATIVE", "false").lower() == "true"


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    from alphalens_shared.bedrock_agent import log_agent_mode

    log_agent_mode(AGENT_NAME, llm=USE_LLM_ANALYST_NARRATIVE)
    result = run_analyst(payload)
    return maybe_enrich_analyst_narrative(payload, result)


def create_agent(*_args: Any, **_kwargs: Any):
    raise NotImplementedError(
        "Analyst uses run(payload). LLM narrative is enabled with USE_LLM_ANALYST_NARRATIVE."
    )


def rank(
    candidates: List[Dict[str, Any]],
    risk_profile: str = "balanced",
    market_condition: Optional[str] = None,
) -> Dict[str, Any]:
    return OpportunityRankingService().rank(
        candidates=candidates,
        risk_profile=risk_profile,
        market_condition=market_condition,
    )


__all__ = [
    "AGENT_NAME",
    "INSTRUCTIONS",
    "create_agent",
    "run",
    "rank",
    "OpportunityRankingService",
]
