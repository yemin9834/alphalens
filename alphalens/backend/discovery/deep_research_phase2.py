"""Phase 2 deep research — parallel news (MCP) + fundamentals (metrics) + synthesis per candidate."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

NEWS_AGENT_NAME = "Deep Research News"
FUNDAMENTALS_AGENT_NAME = "Deep Research Fundamentals"
SYNTHESIS_AGENT_NAME = "Deep Research Synthesizer"

NEWS_INSTRUCTIONS = """
You are a financial news researcher. Use Brave Search MCP to find recent headlines about
the candidate company and its relationship to the core ecosystem company.

Rules:
- Search for the ticker and company name plus ecosystem context
- Return a concise markdown summary: 3-6 bullets with headline, approximate date if known, and impact (positive/negative/neutral)
- Only include information you found via search tools — do not invent headlines
- If search returns little, say so briefly
"""

FUNDAMENTALS_INSTRUCTIONS = """
You are a fundamentals analyst. Market metrics are ALREADY computed — do not invent numbers.

Interpret the provided metrics JSON for a retail investor:
- revenueTrend: qualitative trend label (Growing / Stable / Unknown / Declining) based on metrics only
- earningsSummary: 2-3 sentences on valuation, momentum, and what metrics imply
- dataQuality: "partial" when metrics exist, "unavailable" when mostly unknown
"""

SYNTHESIS_INSTRUCTIONS = """
You are the AlphaLens deep research synthesizer. Combine news research, fundamentals notes,
and market metrics into a single investor report.

Rules:
- marketSnapshot values are authoritative — do not change suggestedEntryRange or valuation labels
- recentNews must come from the news research section only
- entryView must align with marketSnapshot entryAttractiveness and valuation
- executiveSummary: 3-5 sentences, actionable
"""


class _NewsItemLLM(BaseModel):
    model_config = ConfigDict(extra="ignore")

    headline: str = ""
    date: str = ""
    impact: Literal["positive", "negative", "neutral", "mixed"] = "neutral"
    summary: str = ""
    sourceUrl: str = ""


class _FundamentalsLLM(BaseModel):
    model_config = ConfigDict(extra="ignore")

    revenueTrend: str = ""
    earningsSummary: str = ""
    lastReportDate: str = ""
    dataQuality: Literal["high", "partial", "unavailable"] = "partial"


class _EntryViewLLM(BaseModel):
    model_config = ConfigDict(extra="ignore")

    opportunityView: Literal["Attractive", "Watch", "Avoid", "Neutral"] = "Neutral"
    rationale: str = ""
    keyRisks: List[str] = Field(default_factory=list)


class _Phase2SynthesisOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    executiveSummary: str = ""
    entryView: _EntryViewLLM = Field(default_factory=_EntryViewLLM)
    recentNews: List[_NewsItemLLM] = Field(default_factory=list)
    fundamentals: _FundamentalsLLM = Field(default_factory=_FundamentalsLLM)
    warnings: List[str] = Field(default_factory=list)


def deep_research_mode() -> str:
    """inline = stream on discovery NDJSON; async = SQS/HTTP worker after candidates."""
    return os.getenv("DEEP_RESEARCH_MODE", "inline").strip().lower()


def deep_research_max_candidates() -> int:
    raw = os.getenv("DEEP_RESEARCH_MAX_CANDIDATES", "5").strip()
    try:
        return max(1, min(int(raw), 12))
    except ValueError:
        return 5


def _market_snapshot_from_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    price = metrics.get("lastPrice") or metrics.get("price")
    try:
        price_f = float(price) if price is not None else None
    except (TypeError, ValueError):
        price_f = None

    return {
        "price": price_f,
        "valuation": str(metrics.get("valuation", "Unknown")),
        "momentum": str(metrics.get("momentum", "Unknown")),
        "volatilityRisk": str(metrics.get("volatilityRisk", "Unknown")),
        "entryAttractiveness": str(metrics.get("entryAttractiveness", "Unknown")),
        "suggestedEntryRange": str(metrics.get("suggestedEntryRange", "Data unavailable")),
        "riskInvalidationLevel": str(metrics.get("riskInvalidationLevel", "Data unavailable")),
    }


async def _research_news(
    candidate: Dict[str, Any],
    *,
    core_company: str,
    core_ticker: str,
) -> str:
    from alphalens_shared.bedrock_agent import run_bedrock_agent
    from alphalens_shared.mcp_servers import brave_search_mcp_stack

    ticker = candidate.get("ticker", "")
    name = candidate.get("companyName", ticker)
    task = f"""
Core ecosystem: {core_company} ({core_ticker})
Candidate: {name} ({ticker})
Relationship: {candidate.get("relationshipType", "")} — {candidate.get("relationshipSummary", "")}

Find recent news and catalysts for this candidate in the {core_company} ecosystem.
""".strip()

    try:
        async with brave_search_mcp_stack(timeout_seconds=90) as servers:
            return str(
                await run_bedrock_agent(
                    name=NEWS_AGENT_NAME,
                    instructions=NEWS_INSTRUCTIONS,
                    task=task,
                    mcp_servers=servers,
                    max_turns=8,
                )
                or ""
            ).strip()
    except Exception as exc:
        logger.warning("News research failed for %s: %s", ticker, exc)
        return f"No news research available: {exc}"


async def _research_fundamentals(
    candidate: Dict[str, Any],
    metrics: Dict[str, Any],
) -> _FundamentalsLLM:
    from alphalens_shared.bedrock_agent import run_bedrock_agent

    ticker = candidate.get("ticker", "")
    if metrics.get("valuation") == "Unknown" and not metrics.get("price"):
        return _FundamentalsLLM(
            revenueTrend="Unknown",
            earningsSummary="Limited market data available for fundamentals interpretation.",
            dataQuality="unavailable",
        )

    task = f"""
Ticker: {ticker}
Company: {candidate.get("companyName", ticker)}

marketMetrics (deterministic — do not invent other figures):
{json.dumps(_market_snapshot_from_metrics(metrics), indent=2)}
""".strip()

    try:
        return await run_bedrock_agent(
            name=FUNDAMENTALS_AGENT_NAME,
            instructions=FUNDAMENTALS_INSTRUCTIONS,
            task=task,
            output_type=_FundamentalsLLM,
            max_turns=4,
        )
    except Exception as exc:
        logger.warning("Fundamentals agent failed for %s: %s", ticker, exc)
        return _FundamentalsLLM(
            revenueTrend="Unknown",
            earningsSummary=f"Metrics: {metrics.get('valuation', 'Unknown')} valuation, {metrics.get('momentum', 'Unknown')} momentum.",
            dataQuality="partial",
        )


async def _synthesize_report(
    candidate: Dict[str, Any],
    *,
    core_company: str,
    core_ticker: str,
    news_text: str,
    fundamentals: _FundamentalsLLM,
    metrics: Dict[str, Any],
) -> _Phase2SynthesisOutput:
    from alphalens_shared.bedrock_agent import run_bedrock_agent

    market_snapshot = _market_snapshot_from_metrics(metrics)
    task = f"""
Core ecosystem: {core_company} ({core_ticker})

Candidate:
{json.dumps({
    "companyName": candidate.get("companyName"),
    "ticker": candidate.get("ticker"),
    "relationshipType": candidate.get("relationshipType"),
    "relationshipSummary": candidate.get("relationshipSummary"),
    "confidence": candidate.get("confidence"),
}, indent=2)}

newsResearch:
{news_text}

fundamentalsNotes:
{fundamentals.model_dump_json(indent=2)}

marketSnapshot (authoritative):
{json.dumps(market_snapshot, indent=2)}
""".strip()

    try:
        return await run_bedrock_agent(
            name=SYNTHESIS_AGENT_NAME,
            instructions=SYNTHESIS_INSTRUCTIONS,
            task=task,
            output_type=_Phase2SynthesisOutput,
            max_turns=6,
        )
    except Exception as exc:
        logger.warning("Synthesis failed for %s: %s", candidate.get("ticker"), exc)
        return _Phase2SynthesisOutput(
            executiveSummary=(
                f"{candidate.get('companyName', candidate.get('ticker'))} — synthesis unavailable. "
                f"See news and metrics notes."
            ),
            warnings=[f"Synthesis unavailable: {exc}"],
        )


async def build_phase2_report(
    candidate: Dict[str, Any],
    *,
    core_company: str,
    core_ticker: str,
) -> Dict[str, Any]:
    """Run news + fundamentals agents in parallel, then synthesize."""
    ticker = str(candidate.get("ticker", "")).upper().strip()
    if not ticker or ticker == "CASH":
        return {}

    from alphalens_metrics.market_metric_engine import MarketMetricEngine

    metrics_task = asyncio.create_task(
        asyncio.to_thread(MarketMetricEngine().get_stock_metrics, ticker)
    )
    news_task = asyncio.create_task(
        _research_news(candidate, core_company=core_company, core_ticker=core_ticker)
    )

    metrics = await metrics_task
    news_text = await news_task
    fundamentals = await _research_fundamentals(candidate, metrics)
    narrative = await _synthesize_report(
        candidate,
        core_company=core_company,
        core_ticker=core_ticker,
        news_text=news_text,
        fundamentals=fundamentals,
        metrics=metrics,
    )

    evidence_urls: List[str] = []
    url = str(candidate.get("evidenceUrl") or "").strip()
    if url:
        evidence_urls.append(url)
    for item in narrative.recentNews:
        if item.sourceUrl:
            evidence_urls.append(item.sourceUrl)

    warnings = list(narrative.warnings)
    if "No news research available" in news_text:
        warnings.append("News research returned limited results.")

    return {
        "ticker": ticker,
        "companyName": metrics.get("companyName") or candidate.get("companyName", ticker),
        "executiveSummary": narrative.executiveSummary,
        "relationshipToCore": {
            "type": str(candidate.get("relationshipType", "")),
            "summary": str(candidate.get("relationshipSummary", "")),
            "confidence": str(candidate.get("confidence", "Medium")),
        },
        "recentNews": [item.model_dump() for item in narrative.recentNews],
        "fundamentals": narrative.fundamentals.model_dump(),
        "marketSnapshot": _market_snapshot_from_metrics(metrics),
        "entryView": narrative.entryView.model_dump(),
        "evidenceUrls": evidence_urls,
        "warnings": warnings,
        "researchPhase": 2,
    }


async def process_discovery_run(discovery_run_id: str) -> Dict[str, Any]:
    """Process all eligible candidates for a persisted discovery run."""
    from src import Database

    logger.info("Phase 2 deep research starting for run %s", discovery_run_id)
    db = Database()
    run = db.discovery_runs.find_by_id(discovery_run_id)
    if not run:
        return {"success": False, "error": f"Discovery run not found: {discovery_run_id}"}

    core_company = run.get("core_company", "")
    core_ticker = str(run.get("core_ticker", "")).upper()
    rows = db.candidates.find_by_run(discovery_run_id)

    eligible = [
        {
            "companyName": row.get("company_name", ""),
            "ticker": row.get("ticker", ""),
            "relationshipType": row.get("relationship_type", ""),
            "relationshipSummary": row.get("relationship_summary", ""),
            "confidence": row.get("confidence", "Medium"),
            "evidenceUrl": row.get("evidence_url", ""),
            "tickerValidation": row.get("ticker_validation", ""),
        }
        for row in rows
        if row.get("ticker")
        and str(row.get("ticker", "")).upper() != "CASH"
        and row.get("ticker_validation") != "invalid"
    ][: deep_research_max_candidates()]

    total = len(eligible)
    progress = {"total": total, "completed": 0, "failed": 0, "tickers": {}}
    db.discovery_runs.update_research_status(discovery_run_id, "researching", progress)

    async def _one(candidate: Dict[str, Any]) -> tuple[str, bool]:
        ticker = str(candidate.get("ticker", "")).upper()
        try:
            report = await build_phase2_report(
                candidate,
                core_company=core_company,
                core_ticker=core_ticker,
            )
            if report:
                await asyncio.to_thread(
                    db.candidates.update_deep_research,
                    discovery_run_id,
                    ticker,
                    report,
                )
                progress["tickers"][ticker] = "completed"
                return ticker, True
            progress["tickers"][ticker] = "empty"
            return ticker, False
        except Exception as exc:
            logger.exception("Phase 2 research failed for %s", ticker)
            progress["tickers"][ticker] = f"failed: {exc}"
            return ticker, False

    tasks = [asyncio.create_task(_one(c)) for c in eligible]
    for finished in asyncio.as_completed(tasks):
        ticker, ok = await finished
        if ok:
            progress["completed"] += 1
        else:
            progress["failed"] += 1
        db.discovery_runs.update_research_status(discovery_run_id, "researching", dict(progress))

    final_status = "completed" if progress["completed"] > 0 else "failed"
    db.discovery_runs.update_research_status(discovery_run_id, final_status, dict(progress))
    return {
        "success": True,
        "discoveryRunId": discovery_run_id,
        "researchStatus": final_status,
        "progress": progress,
    }
