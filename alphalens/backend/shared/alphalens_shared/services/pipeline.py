"""End-to-end analysis pipeline for orchestrator and API."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from alphalens_shared.lambda_invoke import (
    ANALYST_FUNCTION,
    VALIDATOR_FUNCTION,
    invoke_agent,
    invoke_discovery,
    invoke_portfolio,
)
from alphalens_shared.services.analyst import run_analyst
from alphalens_shared.services.analyst_narrative import maybe_enrich_analyst_narrative
from alphalens_shared.services.discovery_persist import maybe_persist_discovery
from alphalens_shared.services.validator import run_validator_agent

logger = logging.getLogger(__name__)

StageCallback = Callable[[str, Dict[str, Any]], None]


def run_analysis_pipeline(
    payload: Dict[str, Any],
    on_stage: Optional[StageCallback] = None,
) -> Dict[str, Any]:
    """
    Run discovery (optional) → validation → ranking → portfolio recommendation.

    When ``on_stage`` is provided, it is called after each major step with
    ``(stage_name, partial_data)`` so async jobs can persist incremental results.

    Payload keys:
      - riskProfile
      - portfolio (list of {ticker, weight})
      - candidates (optional — skips discovery)
      - coreCompany / coreTicker (for discovery)
      - marketCondition (optional)
    """
    risk_profile = payload.get("riskProfile", "balanced")
    portfolio = payload.get("portfolio", [])
    market_condition = payload.get("marketCondition")

    candidates = payload.get("candidates")
    warnings: List[str] = []
    discovery_run_id = payload.get("discoveryRunId")

    if not candidates:
        discovery_payload = {
            "coreCompany": payload.get("coreCompany", "NVIDIA"),
            "coreTicker": payload.get("coreTicker", "NVDA"),
            "scope": payload.get("scope", "level-1"),
            "clerkUserId": payload.get("clerkUserId") or payload.get("clerk_user_id"),
        }
        discovery = invoke_discovery(discovery_payload)
        if not discovery.get("success", True):
            return discovery
        discovery = maybe_persist_discovery(discovery_payload, discovery)
        candidates = discovery.get("candidates", [])
        new_warnings = discovery.get("warnings", [])
        warnings.extend(new_warnings)
        discovery_run_id = discovery.get("discoveryRunId")
        if on_stage:
            on_stage(
                "discovery",
                {
                    "discoveryRunId": discovery_run_id,
                    "newWarnings": new_warnings,
                    "candidateCount": len(candidates),
                },
            )
    elif on_stage:
        on_stage("discovery", {"skipped": True, "candidateCount": len(candidates)})

    validation = _call(
        VALIDATOR_FUNCTION,
        {"candidates": candidates},
        run_validator_agent,
    )
    if not validation.get("success", True):
        return validation

    validated = [
        c
        for c in validation.get("validatedCandidates", [])
        if c.get("tickerValidation") != "invalid"
    ]
    new_warnings = validation.get("warnings", [])
    warnings.extend(new_warnings)
    if on_stage:
        on_stage(
            "validation",
            {
                "validationReport": validation.get("validationReport"),
                "validatedCandidates": validated,
                "newWarnings": new_warnings,
            },
        )

    analyst_payload = {
        "riskProfile": risk_profile,
        "marketCondition": market_condition,
        "candidates": validated,
    }
    analysis = _call(ANALYST_FUNCTION, analyst_payload, run_analyst)
    if not analysis.get("success", True):
        return analysis

    if os.getenv("MOCK_LAMBDAS", "false").lower() == "true":
        analysis = maybe_enrich_analyst_narrative(analyst_payload, analysis)

    market_condition = analysis.get("marketCondition", market_condition or "Neutral")
    ranked = analysis.get("rankedCandidates", [])
    new_warnings = analysis.get("warnings", [])
    warnings.extend(new_warnings)
    if on_stage:
        on_stage(
            "analysis",
            {
                "analysisReport": analysis.get("analysisReport"),
                "rankedCandidates": ranked,
                "rankedPayload": analysis.get("rankedPayload"),
                "marketCondition": market_condition,
                "newWarnings": new_warnings,
            },
        )

    portfolio_payload = {
        "riskProfile": risk_profile,
        "portfolio": portfolio,
        "rankedCandidates": ranked,
        "rankedPayload": analysis.get("rankedPayload"),
        "marketCondition": market_condition,
    }
    recommendation = invoke_portfolio(portfolio_payload)
    if not recommendation.get("success", True):
        return recommendation
    new_warnings = recommendation.get("warnings", [])
    warnings.extend(new_warnings)
    if on_stage:
        on_stage(
            "portfolio",
            {
                "recommendation": recommendation.get("recommendation"),
                "recommendationPayload": recommendation.get("recommendationPayload"),
                "portfolioReport": recommendation.get("portfolioReport"),
                "newWarnings": new_warnings,
            },
        )

    result = {
        "success": True,
        "warnings": warnings,
        "validatedCandidates": validated,
        "validationReport": validation.get("validationReport"),
        "rankedCandidates": ranked,
        "rankedPayload": analysis.get("rankedPayload"),
        "analysisReport": analysis.get("analysisReport"),
        "recommendation": recommendation.get("recommendation"),
        "recommendationPayload": recommendation.get("recommendationPayload"),
        "portfolioReport": recommendation.get("portfolioReport"),
    }
    if discovery_run_id:
        result["discoveryRunId"] = discovery_run_id
    return result


def _call(function_name: str, payload: Dict[str, Any], local_handler) -> Dict[str, Any]:
    if os.getenv("MOCK_LAMBDAS", "false").lower() == "true":
        return local_handler(payload)
    return invoke_agent(function_name, payload)
