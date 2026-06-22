"""Phase 1 deep research — deterministic metrics + LLM synthesis per candidate."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

AGENT_NAME = "Deep Research Synthesizer"

DEEP_RESEARCH_INSTRUCTIONS = """
You are the AlphaLens deep research synthesizer. Market metrics are ALREADY computed
by a deterministic engine — you must NOT invent prices, P/E, revenue figures, or entry ranges.

Your job: write investor-friendly insight that explains the candidate's relationship to the
core company and interprets the provided metrics.

Rules:
- Use ONLY facts from the candidate context and marketSnapshot JSON
- Do not invent earnings dates, revenue numbers, or news headlines in Phase 1
- recentNews may be empty — do not fabricate news items
- fundamentals.dataQuality should be "unavailable" unless explicit data was provided
- entryView.opportunityView must align with entryAttractiveness and valuation in marketSnapshot
- suggestedEntryRange in marketSnapshot is authoritative — reference it in rationale, never replace it
- keyRisks: 2-4 concise bullets grounded in metrics or relationship
- executiveSummary: 2-4 sentences, actionable for a portfolio investor
"""


class _EntryViewLLM(BaseModel):
    model_config = ConfigDict(extra="ignore")

    opportunityView: Literal["Attractive", "Watch", "Avoid", "Neutral"] = "Neutral"
    rationale: str = ""
    keyRisks: List[str] = Field(default_factory=list)


class _DeepResearchLLMOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    executiveSummary: str = ""
    entryView: _EntryViewLLM = Field(default_factory=_EntryViewLLM)
    warnings: List[str] = Field(default_factory=list)


def deep_research_enabled() -> bool:
    return os.getenv("DEEP_RESEARCH_ENABLED", "true").lower() == "true"


def deep_research_max_candidates() -> int:
    raw = os.getenv("DEEP_RESEARCH_MAX_CANDIDATES", "5").strip()
    try:
        return max(1, min(int(raw), 12))
    except ValueError:
        return 5


def _metrics_for_ticker(ticker: str) -> Dict[str, Any]:
    from alphalens_metrics.market_metric_engine import MarketMetricEngine

    return MarketMetricEngine().get_stock_metrics(ticker.upper().strip())


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


def _deterministic_entry_view(metrics: Dict[str, Any]) -> Dict[str, Any]:
    attractiveness = str(metrics.get("entryAttractiveness", "Unknown"))
    valuation = str(metrics.get("valuation", "Unknown"))
    momentum = str(metrics.get("momentum", "Unknown"))

    view = "Neutral"
    if attractiveness == "High" and valuation in ("Cheap", "Fair"):
        view = "Attractive"
    elif attractiveness == "Low" or valuation == "Expensive":
        view = "Watch"
    elif momentum == "Negative" and attractiveness == "Low":
        view = "Avoid"

    rationale = (
        f"Entry attractiveness is {attractiveness.lower()} with {valuation.lower()} valuation "
        f"and {momentum.lower()} momentum."
    )
    risks: List[str] = []
    if metrics.get("volatilityRisk") == "High":
        risks.append("Elevated volatility — size positions carefully.")
    if metrics.get("downsideRisk") == "High":
        risks.append("Downside risk metrics are elevated.")
    if not risks:
        risks.append("Monitor relationship catalysts and sector moves vs the core company.")

    return {"opportunityView": view, "rationale": rationale, "keyRisks": risks}


def _deterministic_summary(
    candidate: Dict[str, Any],
    core_company: str,
    metrics: Dict[str, Any],
) -> str:
    ticker = candidate.get("ticker", "")
    name = candidate.get("companyName", ticker)
    rel = candidate.get("relationshipType", "ecosystem")
    summary = candidate.get("relationshipSummary", "")
    entry = metrics.get("suggestedEntryRange", "Data unavailable")
    return (
        f"{name} ({ticker}) is a {rel} in the {core_company} ecosystem. {summary} "
        f"Market signals show {metrics.get('valuation', 'unknown').lower()} valuation "
        f"and {metrics.get('entryAttractiveness', 'unknown').lower()} entry attractiveness. "
        f"Suggested entry range (metrics): {entry}."
    ).strip()


async def _synthesize_narrative(
    candidate: Dict[str, Any],
    core_company: str,
    core_ticker: str,
    market_snapshot: Dict[str, Any],
) -> _DeepResearchLLMOutput:
    from alphalens_shared.bedrock_agent import run_bedrock_agent

    task = f"""
Core ecosystem: {core_company} ({core_ticker})

Candidate:
{{
  "companyName": "{candidate.get("companyName", "")}",
  "ticker": "{candidate.get("ticker", "")}",
  "relationshipType": "{candidate.get("relationshipType", "")}",
  "relationshipSummary": "{candidate.get("relationshipSummary", "")}",
  "confidence": "{candidate.get("confidence", "Medium")}",
  "evidenceUrl": "{candidate.get("evidenceUrl", "")}"
}}

marketSnapshot (from deterministic engine — do not change these values):
{market_snapshot}

Write executiveSummary and entryView only. Leave recentNews empty and fundamentals as unavailable.
""".strip()

    try:
        return await run_bedrock_agent(
            name=AGENT_NAME,
            instructions=DEEP_RESEARCH_INSTRUCTIONS,
            task=task,
            output_type=_DeepResearchLLMOutput,
            max_turns=4,
        )
    except Exception as exc:
        logger.warning("Deep research LLM synthesis failed for %s: %s", candidate.get("ticker"), exc)
        metrics = {
            "valuation": market_snapshot.get("valuation"),
            "entryAttractiveness": market_snapshot.get("entryAttractiveness"),
            "momentum": market_snapshot.get("momentum"),
            "volatilityRisk": market_snapshot.get("volatilityRisk"),
            "downsideRisk": "Unknown",
        }
        entry = _deterministic_entry_view(metrics)
        return _DeepResearchLLMOutput(
            executiveSummary=_deterministic_summary(candidate, core_company, metrics),
            entryView=_EntryViewLLM(**entry),
            warnings=[f"LLM synthesis unavailable: {exc}"],
        )


async def build_deep_research_report(
    candidate: Dict[str, Any],
    *,
    core_company: str,
    core_ticker: str,
) -> Dict[str, Any]:
    """Build a full DeepCompanyReport dict for one ecosystem candidate."""
    ticker = str(candidate.get("ticker", "")).upper().strip()
    if not ticker or ticker == "CASH":
        return {}

    metrics = await asyncio.to_thread(_metrics_for_ticker, ticker)
    market_snapshot = _market_snapshot_from_metrics(metrics)
    narrative = await _synthesize_narrative(
        candidate, core_company, core_ticker, market_snapshot
    )

    evidence_urls: List[str] = []
    url = str(candidate.get("evidenceUrl") or "").strip()
    if url:
        evidence_urls.append(url)

    warnings = list(narrative.warnings)
    if metrics.get("valuation") == "Unknown":
        warnings.append("Limited market data — metrics may be incomplete.")

    return {
        "ticker": ticker,
        "companyName": metrics.get("companyName") or candidate.get("companyName", ticker),
        "executiveSummary": narrative.executiveSummary
        or _deterministic_summary(candidate, core_company, metrics),
        "relationshipToCore": {
            "type": str(candidate.get("relationshipType", "")),
            "summary": str(candidate.get("relationshipSummary", "")),
            "confidence": str(candidate.get("confidence", "Medium")),
        },
        "recentNews": [],
        "fundamentals": {
            "revenueTrend": "",
            "earningsSummary": "",
            "lastReportDate": "",
            "dataQuality": "unavailable",
        },
        "marketSnapshot": market_snapshot,
        "entryView": narrative.entryView.model_dump(),
        "evidenceUrls": evidence_urls,
        "warnings": warnings,
    }


async def iter_deep_research_events(
    candidates: List[Dict[str, Any]],
    *,
    core_company: str,
    core_ticker: str,
    discovery_run_id: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Yield NDJSON-style events while researching each candidate."""
    if not deep_research_enabled():
        return

    eligible = [
        c
        for c in candidates
        if str(c.get("ticker", "")).strip()
        and str(c.get("ticker", "")).upper() != "CASH"
        and c.get("tickerValidation") != "invalid"
    ][: deep_research_max_candidates()]

    if not eligible:
        return

    total = len(eligible)
    yield {
        "event": "research_phase",
        "message": f"Deep research on {total} candidate{'s' if total != 1 else ''}…",
        "total": total,
    }

    async def _research_one(
        index: int, candidate: Dict[str, Any]
    ) -> tuple[int, Dict[str, Any], Dict[str, Any] | None, str | None]:
        ticker = str(candidate.get("ticker", "")).upper()
        try:
            report = await build_deep_research_report(
                candidate,
                core_company=core_company,
                core_ticker=core_ticker,
            )
            return index, candidate, report or None, None
        except Exception as exc:
            logger.exception("Deep research failed for %s", ticker)
            return index, candidate, None, str(exc)

    tasks = [
        asyncio.create_task(_research_one(index, candidate))
        for index, candidate in enumerate(eligible, start=1)
    ]
    completed = 0
    for finished in asyncio.as_completed(tasks):
        index, candidate, report, error = await finished
        ticker = str(candidate.get("ticker", "")).upper()
        completed += 1

        yield {
            "event": "research_start",
            "ticker": ticker,
            "index": completed,
            "total": total,
            "message": f"Researching {ticker} ({completed}/{total})…",
        }

        if error:
            yield {
                "event": "research_error",
                "ticker": ticker,
                "error": error,
            }
            continue

        if not report:
            continue

        candidate["deepResearch"] = report

        if discovery_run_id:
            await asyncio.to_thread(
                _persist_deep_research,
                discovery_run_id,
                ticker,
                report,
            )

        yield {
            "event": "research_report",
            "ticker": ticker,
            "index": completed,
            "total": total,
            "report": report,
        }


def _persist_deep_research(run_id: str, ticker: str, report: Dict[str, Any]) -> None:
    try:
        from src import Database
    except ImportError:
        return

    try:
        Database().candidates.update_deep_research(run_id, ticker, report)
    except Exception:
        logger.exception("Failed to persist deep research for %s", ticker)


def attach_deep_research_to_candidates(
    candidates: List[Dict[str, Any]],
    reports_by_ticker: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    updated: List[Dict[str, Any]] = []
    for candidate in candidates:
        row = dict(candidate)
        ticker = str(row.get("ticker", "")).upper()
        if ticker in reports_by_ticker:
            row["deepResearch"] = reports_by_ticker[ticker]
        updated.append(row)
    return updated
