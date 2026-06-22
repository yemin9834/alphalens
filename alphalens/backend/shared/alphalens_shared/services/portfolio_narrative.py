"""
Optional LLM narrative for portfolio results — grounded in deterministic recommendationPayload.

Slim OpenAI/Bedrock path (same pattern as analyst_narrative). Never changes actions or weights.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from alphalens_shared.services.portfolio_report import (
    attach_portfolio_narrative,
    build_deterministic_portfolio_report,
    validate_portfolio_narrative,
)

logger = logging.getLogger(__name__)

AGENT_NAME = "Portfolio Narrator"

PORTFOLIO_NARRATIVE_INSTRUCTIONS = """
You are the AlphaLens portfolio narrator. Add/Trim/Hold actions and sizing are ALREADY
computed by deterministic risk and action-plan engines — you must NOT change action types,
tickers, or amount fields.

Your job: explain the portfolio recommendation clearly for an investor.

Rules:
- Use ONLY facts in recommendationPayload and recommendation (actions, signals, ranked context)
- Do not invent new tickers, prices, or actions not in the deterministic plan
- Every actionNotes entry must match an existing (ticker, type) pair exactly
- Every candidateNotes ticker must appear in candidateRecommendations
- methodologyNote must state actions came from code/metrics, not from you
- Respond with ONLY valid JSON (no markdown fences)
"""

OUTPUT_HINT = """
JSON shape:
{
  "executiveSummary": "...",
  "actionNotes": [{"ticker": "TSM", "type": "Add", "summary": "..."}],
  "candidateNotes": [{"ticker": "TSM", "summary": "..."}],
  "portfolioSignalsSummary": "...",
  "methodologyNote": "..."
}
"""


class ActionNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    type: str
    summary: str


class CandidateNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    summary: str


class PortfolioReportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executiveSummary: str
    actionNotes: List[ActionNote] = Field(default_factory=list)
    candidateNotes: List[CandidateNote] = Field(default_factory=list)
    portfolioSignalsSummary: str = ""
    methodologyNote: str


def narrative_enabled() -> bool:
    if os.getenv("USE_LLM_PORTFOLIO_NARRATIVE", "").lower() == "true":
        return True
    # Legacy flag — previously full LLM; now narrative-only hybrid.
    return os.getenv("USE_LLM_PORTFOLIO", "false").lower() == "true"


def create_narrative_task(recommendation_payload: Dict[str, Any], recommendation: Dict[str, Any]) -> str:
    payload_json = json.dumps(
        {
            "recommendationPayload": recommendation_payload,
            "recommendation": recommendation,
        },
        indent=2,
    )[:14000]
    return f"""
Explain this portfolio recommendation for the user.

Deterministic recommendation (source of truth — do not contradict actions or tickers):
{payload_json}

{OUTPUT_HINT}
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


def run_narrative_slim(_payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    from alphalens_shared.bedrock_agent import get_llm_provider

    recommendation = result.get("recommendation") or {}
    recommendation_payload = result.get("recommendationPayload") or recommendation
    task = create_narrative_task(recommendation_payload, recommendation)
    provider = get_llm_provider()

    if provider == "openai":
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        model = os.getenv("OPENAI_MODEL_ID", "gpt-4.1-mini")
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PORTFOLIO_NARRATIVE_INSTRUCTIONS},
                {"role": "user", "content": task},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
    else:
        import boto3

        region = os.getenv("BEDROCK_REGION", "us-west-2")
        model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.converse(
            modelId=model_id,
            system=[{"text": PORTFOLIO_NARRATIVE_INSTRUCTIONS}],
            messages=[{"role": "user", "content": [{"text": task}]}],
            inferenceConfig={"maxTokens": 2048, "temperature": 0.2},
        )
        parts = response.get("output", {}).get("message", {}).get("content", [])
        content = next((p.get("text", "") for p in parts if "text" in p), "{}")

    parsed = PortfolioReportOutput.model_validate(_extract_json(content))
    return _finalize(parsed.model_dump(), result)


def _finalize(report: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    recommendation = result.get("recommendation") or {}
    sanitized, guardrail_warnings = validate_portfolio_narrative(report, recommendation)
    if guardrail_warnings:
        logger.warning("Portfolio narrative guardrails: %s", "; ".join(guardrail_warnings))
        result.setdefault("warnings", []).extend(guardrail_warnings)
    if not sanitized.get("actionNotes") and not sanitized.get("executiveSummary"):
        return build_deterministic_portfolio_report(result)
    return sanitized


def maybe_enrich_portfolio_narrative(
    payload: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach LLM portfolio narrative when USE_LLM_PORTFOLIO_NARRATIVE=true."""
    if not narrative_enabled():
        return result
    if not result.get("success", True):
        return result

    try:
        report = run_narrative_slim(payload, result)
        attach_portfolio_narrative(result, report)
        return result
    except ImportError:
        logger.warning("Portfolio LLM deps missing")
    except Exception:
        logger.exception("Portfolio LLM narrative failed — keeping deterministic report")

    result.setdefault("warnings", []).append(
        "LLM portfolio narrative unavailable; using deterministic portfolio report."
    )
    return result
