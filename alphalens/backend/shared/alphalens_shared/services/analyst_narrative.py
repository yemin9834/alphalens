"""
LLM narrative for analyst results — grounded in deterministic rankedPayload.

Uses a slim path (boto3 Bedrock Converse or OpenAI client) on the analyst Lambda zip.
Falls back to openai-agents + LiteLLM on orchestrator when the full SDK is installed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, ConfigDict, Field

from alphalens_shared.services.analyst_report import (
    build_deterministic_report,
    validate_narrative,
)

logger = logging.getLogger(__name__)

AGENT_NAME = "Analyst Narrator"

ANALYST_NARRATIVE_INSTRUCTIONS = """
You are the AlphaLens opportunity analyst narrator. Rankings and scores are ALREADY
computed by a deterministic metrics engine — you must NOT change scores, ranks, or tickers.

Your job: write a clear, investor-friendly report that explains the provided ranking JSON.

Rules:
- Use ONLY facts present in rankedPayload (tickers, opportunityScore, rankReason, metrics)
- Do not invent prices, P/E ratios, earnings, or new tickers
- If a metric is "Unknown", say data is limited — do not guess
- Every topOpportunities and risksToWatch entry must use a ticker from rankedPayload
- Reference opportunityScore or rankReason when explaining why a name stands out
- Match tone to riskProfile (conservative = emphasize volatility; aggressive = note upside)
- methodologyNote must state rankings came from code/metrics, not from you
- Respond with ONLY valid JSON matching AnalystReportOutput (no markdown fences)
"""

NARRATIVE_OUTPUT_HINT = """
JSON shape:
{
  "executiveSummary": "...",
  "marketOverview": "...",
  "topOpportunities": [{"ticker": "TSM", "summary": "..."}],
  "risksToWatch": [{"ticker": "...", "summary": "..."}],
  "methodologyNote": "..."
}
"""


class TickerInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    summary: str


class AnalystReportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executiveSummary: str
    marketOverview: str
    topOpportunities: List[TickerInsight] = Field(default_factory=list)
    risksToWatch: List[TickerInsight] = Field(default_factory=list)
    methodologyNote: str


def narrative_enabled() -> bool:
    return os.getenv("USE_LLM_ANALYST_NARRATIVE", "false").lower() == "true"


def create_narrative_task(risk_profile: str, ranked_payload: Dict[str, Any]) -> str:
    payload_json = json.dumps(ranked_payload, indent=2)[:14000]
    market = ranked_payload.get("marketCondition", "Neutral")
    return f"""
Write an opportunity analysis report for a {risk_profile} investor.

Market condition (from metrics engine): {market}

Deterministic ranking payload (source of truth — do not contradict):
{payload_json}

{NARRATIVE_OUTPUT_HINT}
""".strip()


def _extract_json(text: str) -> Dict[str, Any]:
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    return json.loads(raw)


def _finalize_narrative(
    report: Dict[str, Any],
    payload: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    ranked_payload = result.get("rankedPayload") or {}
    risk_profile = payload.get("riskProfile", "balanced")
    sanitized, guardrail_warnings = validate_narrative(report, ranked_payload)
    if guardrail_warnings:
        logger.warning("Analyst narrative guardrails: %s", "; ".join(guardrail_warnings))
        result.setdefault("warnings", []).extend(guardrail_warnings)
    if not sanitized.get("topOpportunities") and ranked_payload.get("rankedCandidates"):
        logger.warning("LLM narrative empty after guardrails — using deterministic report")
        return build_deterministic_report(result, risk_profile)
    return sanitized


def run_narrative_slim(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Slim narrative — boto3 Bedrock or OpenAI client only (fits analyst Lambda zip)."""
    from alphalens_shared.bedrock_agent import get_llm_provider

    provider = get_llm_provider()
    if provider == "openai":
        report = _narrative_openai_slim(payload, result)
    else:
        report = _narrative_bedrock_slim(payload, result)
    return _finalize_narrative(report, payload, result)


def _narrative_openai_slim(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

    ranked_payload = result.get("rankedPayload") or {}
    risk_profile = payload.get("riskProfile", "balanced")
    task = create_narrative_task(risk_profile, ranked_payload)
    model = os.getenv("OPENAI_MODEL_ID", "gpt-4.1-mini")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": ANALYST_NARRATIVE_INSTRUCTIONS},
            {"role": "user", "content": task},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    parsed = AnalystReportOutput.model_validate(_extract_json(content))
    return parsed.model_dump()


def _narrative_bedrock_slim(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    import boto3

    ranked_payload = result.get("rankedPayload") or {}
    risk_profile = payload.get("riskProfile", "balanced")
    task = create_narrative_task(risk_profile, ranked_payload)
    region = os.getenv("BEDROCK_REGION", "us-west-2")
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")

    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model_id,
        system=[{"text": ANALYST_NARRATIVE_INSTRUCTIONS}],
        messages=[{"role": "user", "content": [{"text": task}]}],
        inferenceConfig={"maxTokens": 2048, "temperature": 0.2},
    )
    parts = response.get("output", {}).get("message", {}).get("content", [])
    text = next((p.get("text", "") for p in parts if "text" in p), "")
    parsed = AnalystReportOutput.model_validate(_extract_json(text))
    return parsed.model_dump()


def create_narrative_agent(
    risk_profile: str,
    ranked_payload: Dict[str, Any],
) -> Tuple[Any, str, type[AnalystReportOutput]]:
    from alphalens_shared.bedrock_agent import get_litellm_model, require_llm_packages

    require_llm_packages()
    task = create_narrative_task(risk_profile, ranked_payload)
    model = get_litellm_model()
    return model, task, AnalystReportOutput


async def run_llm_narrative(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Full openai-agents + LiteLLM path (orchestrator zip)."""
    from alphalens_shared.bedrock_agent import run_bedrock_agent

    ranked_payload = result.get("rankedPayload") or {}
    risk_profile = payload.get("riskProfile", "balanced")

    _, task, output_type = create_narrative_agent(risk_profile, ranked_payload)
    llm_output = await run_bedrock_agent(
        name=AGENT_NAME,
        instructions=ANALYST_NARRATIVE_INSTRUCTIONS,
        task=task,
        output_type=output_type,
        max_turns=6,
    )
    return _finalize_narrative(llm_output.model_dump(), payload, result)


def _attach_report(result: Dict[str, Any], report: Dict[str, Any]) -> None:
    result["analysisReport"] = report
    ranked_payload = result.get("rankedPayload")
    if isinstance(ranked_payload, dict):
        ranked_payload["analysisReport"] = report


def maybe_enrich_analyst_narrative(
    payload: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach LLM narrative when USE_LLM_ANALYST_NARRATIVE=true."""
    if not narrative_enabled():
        return result
    if not result.get("success", True):
        return result

    slim_error: str | None = None
    try:
        report = run_narrative_slim(payload, result)
        _attach_report(result, report)
        return result
    except ImportError as exc:
        slim_error = f"slim narrative import failed: {exc}"
        logger.info("%s — trying openai-agents path", slim_error)
    except Exception as exc:
        slim_error = f"slim narrative failed: {exc}"
        logger.exception("Slim analyst narrative failed — trying openai-agents path")

    try:
        report = asyncio.run(run_llm_narrative(payload, result))
        _attach_report(result, report)
    except ImportError:
        logger.warning("USE_LLM_ANALYST_NARRATIVE=true but no LLM runtime available")
        detail = slim_error or "openai client not available in this runtime"
        result.setdefault("warnings", []).append(
            f"LLM narrative unavailable ({detail}). "
            "Repackage analyst: cd backend/analyst && uv run package_docker.py"
        )
    except Exception as exc:
        logger.exception("Analyst LLM narrative failed — keeping deterministic report")
        result.setdefault("warnings", []).append(
            f"LLM narrative failed ({exc}); using deterministic analysis report."
        )

    return result
