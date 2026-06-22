"""
Orchestrator agent — coordinates discovery → validation → ranking → portfolio advice.

MVP: deterministic pipeline via run().
Guide 4+: Bedrock orchestration via create_agent() + run_llm() (Alex planner pattern).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from alphalens_shared.lambda_invoke import (
    ANALYST_FUNCTION,
    PORTFOLIO_FUNCTION,
    VALIDATOR_FUNCTION,
    invoke_agent,
    invoke_discovery,
)
from agents import RunContextWrapper, function_tool
from dotenv import load_dotenv

from templates import ORCHESTRATOR_INSTRUCTIONS, create_orchestrator_task

load_dotenv(override=True)

logger = logging.getLogger(__name__)

AGENT_NAME = "Orchestrator"
INSTRUCTIONS = ORCHESTRATOR_INSTRUCTIONS

USE_LLM_ORCHESTRATION = os.getenv("USE_LLM_ORCHESTRATION", "false").lower() == "true"


@dataclass
class OrchestratorContext:
    """Context passed to orchestrator tools."""

    request: Dict[str, Any]
    discovery: Optional[Dict[str, Any]] = None
    candidates: Optional[List[Dict[str, Any]]] = None
    validation: Optional[Dict[str, Any]] = None
    validated: Optional[List[Dict[str, Any]]] = None
    analysis: Optional[Dict[str, Any]] = None
    portfolio_result: Optional[Dict[str, Any]] = None
    recommendation: Optional[Dict[str, Any]] = None


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run analysis — deterministic pipeline unless USE_LLM_ORCHESTRATION=true."""
    from alphalens_shared.bedrock_agent import log_agent_mode

    log_agent_mode(AGENT_NAME, llm=USE_LLM_ORCHESTRATION)
    if USE_LLM_ORCHESTRATION:
        import asyncio

        return asyncio.run(run_llm(payload))
    from alphalens_shared.services.pipeline import run_analysis_pipeline

    return run_analysis_pipeline(payload)


def create_agent(
    request: Dict[str, Any],
) -> Tuple[Any, List[Any], str, OrchestratorContext]:
    """
    Create Bedrock orchestrator agent with Lambda invoke tools (Alex planner pattern).

    Returns:
        (model, tools, task, context)
    """
    from alphalens_shared.bedrock_agent import get_litellm_model, require_llm_packages

    require_llm_packages()

    context = OrchestratorContext(request=request)
    job_id = request.get("_jobId")
    stage_persister = None
    if job_id:
        from job_stages import JobStagePersister

        stage_persister = JobStagePersister(str(job_id))

    def _persist_stage(stage: str, data: Dict[str, Any]) -> None:
        if stage_persister:
            stage_persister.persist(stage, data)

    @function_tool
    async def run_discovery(wrapper: RunContextWrapper[OrchestratorContext]) -> str:
        """Discover ecosystem candidates for the core company in the request."""
        from alphalens_shared.services.discovery_persist import maybe_persist_discovery

        req = wrapper.context.request
        payload = {
            "coreCompany": req.get("coreCompany", "NVIDIA"),
            "coreTicker": req.get("coreTicker", "NVDA"),
            "scope": req.get("scope", "level-1"),
            "clerkUserId": req.get("clerkUserId") or req.get("clerk_user_id"),
        }
        result = await asyncio.to_thread(invoke_discovery, payload)
        result = maybe_persist_discovery(payload, result)
        wrapper.context.discovery = result
        wrapper.context.candidates = result.get("candidates", [])
        _persist_stage(
            "discovery",
            {
                "discoveryRunId": result.get("discoveryRunId"),
                "candidateCount": len(result.get("candidates", [])),
                "newWarnings": result.get("warnings", []),
            },
        )
        return json.dumps(result)[:4000]

    @function_tool
    async def run_validator(wrapper: RunContextWrapper[OrchestratorContext]) -> str:
        """Validate tickers for discovery candidates."""
        candidates = wrapper.context.candidates or wrapper.context.request.get("candidates", [])
        result = await asyncio.to_thread(invoke_agent, VALIDATOR_FUNCTION, {"candidates": candidates})
        wrapper.context.validation = result
        wrapper.context.validated = [
            c
            for c in result.get("validatedCandidates", [])
            if c.get("tickerValidation") != "invalid"
        ]
        _persist_stage(
            "validation",
            {
                "validationReport": result.get("validationReport"),
                "validatedCandidates": wrapper.context.validated,
                "newWarnings": result.get("warnings", []),
            },
        )
        return json.dumps(result)[:4000]

    @function_tool
    async def run_analyst(wrapper: RunContextWrapper[OrchestratorContext]) -> str:
        """Rank validated candidates using metrics tools."""
        req = wrapper.context.request
        validated = wrapper.context.validated or []
        payload = {
            "riskProfile": req.get("riskProfile", "balanced"),
            "marketCondition": req.get("marketCondition"),
            "candidates": validated,
        }
        result = await asyncio.to_thread(invoke_agent, ANALYST_FUNCTION, payload)
        wrapper.context.analysis = result
        _persist_stage(
            "analysis",
            {
                "analysisReport": result.get("analysisReport"),
                "rankedCandidates": result.get("rankedCandidates", []),
                "rankedPayload": result.get("rankedPayload"),
                "marketCondition": result.get("marketCondition"),
                "newWarnings": result.get("warnings", []),
            },
        )
        return json.dumps(result)[:4000]

    @function_tool
    async def run_portfolio(wrapper: RunContextWrapper[OrchestratorContext]) -> str:
        """Build portfolio-aware recommendations from analyst output."""
        req = wrapper.context.request
        analysis = wrapper.context.analysis or {}
        payload = {
            "riskProfile": req.get("riskProfile", "balanced"),
            "portfolio": req.get("portfolio", []),
            "rankedCandidates": analysis.get("rankedCandidates", []),
            "rankedPayload": analysis.get("rankedPayload"),
            "marketCondition": analysis.get("marketCondition", "Neutral"),
        }
        result = await asyncio.to_thread(invoke_agent, PORTFOLIO_FUNCTION, payload)
        wrapper.context.portfolio_result = result
        wrapper.context.recommendation = result.get("recommendation")
        _persist_stage(
            "portfolio",
            {
                "recommendation": result.get("recommendation"),
                "recommendationPayload": result.get("recommendationPayload"),
                "portfolioReport": result.get("portfolioReport"),
                "newWarnings": result.get("warnings", []),
            },
        )
        return json.dumps(result)[:4000]

    tools = [run_discovery, run_validator, run_analyst, run_portfolio]
    task = create_orchestrator_task(request)
    model = get_litellm_model()

    return model, tools, task, context


def _build_pipeline_result(
    context: OrchestratorContext,
    *,
    summary: str = "",
    success: bool = True,
    error: str = "",
) -> Dict[str, Any]:
    """Match run_analysis_pipeline shape so jobs and API consumers stay consistent."""
    analysis = context.analysis or {}
    validation = context.validation or {}
    discovery = context.discovery or {}
    portfolio = context.portfolio_result or {}

    warnings: List[str] = []
    for step in (discovery, validation, analysis, portfolio):
        warnings.extend(step.get("warnings", []))

    result: Dict[str, Any] = {
        "success": success,
        "warnings": warnings,
        "validatedCandidates": context.validated or [],
        "validationReport": validation.get("validationReport"),
        "rankedCandidates": analysis.get("rankedCandidates", []),
        "rankedPayload": analysis.get("rankedPayload"),
        "analysisReport": analysis.get("analysisReport"),
        "recommendation": context.recommendation,
        "recommendationPayload": portfolio.get("recommendationPayload"),
        "portfolioReport": portfolio.get("portfolioReport"),
    }
    if summary:
        result["summary"] = summary
    if error:
        result["error"] = error
    if discovery.get("discoveryRunId"):
        result["discoveryRunId"] = discovery["discoveryRunId"]
    return result


async def run_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Bedrock orchestrator with tool calls to other agent Lambdas."""
    from alphalens_shared.bedrock_agent import run_bedrock_agent

    model, tools, task, context = create_agent(payload)
    summary = await run_bedrock_agent(
        name=AGENT_NAME,
        instructions=INSTRUCTIONS,
        task=task,
        tools=tools,
        context=context,
        context_type=OrchestratorContext,
        max_turns=20,
    )

    if context.recommendation:
        return _build_pipeline_result(context, summary=str(summary))

    return _build_pipeline_result(
        context,
        summary=str(summary),
        success=False,
        error="Orchestrator finished without portfolio recommendation",
    )


def process_job(job_id: str) -> Dict[str, Any]:
    """Load an analysis_jobs row and run the pipeline (SQS / direct invoke)."""
    from pipeline_job import process_job as _process_job

    return _process_job(job_id)


__all__ = [
    "AGENT_NAME",
    "INSTRUCTIONS",
    "OrchestratorContext",
    "create_agent",
    "run",
    "run_llm",
    "process_job",
]
