"""NDJSON stream for live discovery — LLM tokens, tools, then candidates."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncIterator, Dict, List

from agent import run, iter_live_llm_events
from alphalens_shared.services.discovery import to_api_candidates

logger = logging.getLogger(__name__)

USE_LIVE_DISCOVERY = os.getenv("USE_LIVE_DISCOVERY", "false").lower() == "true"


def _encode(payload: Dict[str, Any]) -> bytes:
    return (json.dumps(payload, default=str) + "\n").encode("utf-8")


def _stream_delay_seconds() -> float:
    raw = os.getenv("DISCOVERY_STREAM_DELAY_MS", "120").strip()
    try:
        return max(0.0, int(raw) / 1000.0)
    except ValueError:
        return 0.12


async def _emit_result_events(
    result: Dict[str, Any],
    *,
    core_company: str,
    core_ticker: str,
) -> AsyncIterator[Dict[str, Any]]:
    if not result.get("success", True):
        yield {"event": "error", "error": result.get("error", "Discovery failed")}
        return

    warnings = list(result.get("warnings") or [])
    for warning in warnings:
        yield {"event": "warning", "message": warning}

    candidates = to_api_candidates(result.get("candidates") or [])
    total = len(candidates)
    yield {
        "event": "status",
        "message": (
            f"Found {total} candidate{'s' if total != 1 else ''} — loading results…"
            if total
            else "No candidates found for this ecosystem."
        ),
    }

    delay = _stream_delay_seconds()
    for index, candidate in enumerate(candidates):
        if index > 0 and delay:
            await asyncio.sleep(delay)
        yield {
            "event": "candidate",
            "candidate": candidate,
            "index": index + 1,
            "total": total,
        }

    discovery_run_id = result.get("discoveryRunId")
    researched = 0
    research_status = "skipped"

    if discovery_run_id:
        try:
            from deep_research import deep_research_enabled
            from deep_research_phase2 import deep_research_mode
            from alphalens_shared.services.deep_research_queue import enqueue_deep_research_run

            if deep_research_enabled() and deep_research_mode() == "async":
                enqueued = await asyncio.to_thread(
                    enqueue_deep_research_run,
                    discovery_run_id,
                    core_company=result.get("coreCompany", core_company),
                    core_ticker=str(result.get("coreTicker", core_ticker)).upper(),
                )
                research_status = "pending" if enqueued else "failed"
            elif deep_research_enabled():
                async for research_event in _iter_deep_research_batch(
                    candidates,
                    core_company=result.get("coreCompany", core_company),
                    core_ticker=str(result.get("coreTicker", core_ticker)).upper(),
                    discovery_run_id=discovery_run_id,
                ):
                    yield research_event
                    if research_event.get("event") == "research_report":
                        researched += 1
                research_status = "completed" if researched else "pending"
        except ImportError:
            pass

    yield {
        "event": "done",
        "coreCompany": result.get("coreCompany", core_company),
        "coreTicker": result.get("coreTicker", core_ticker),
        "candidateCount": total,
        "deepResearchCount": researched,
        "researchStatus": research_status,
        "warnings": warnings,
        "discoveryRunId": discovery_run_id,
    }


async def _iter_deep_research_batch(
    candidates: List[Dict[str, Any]],
    *,
    core_company: str,
    core_ticker: str,
    discovery_run_id: str | None,
) -> AsyncIterator[Dict[str, Any]]:
    try:
        from deep_research import iter_deep_research_events
    except ImportError:
        return

    async for event in iter_deep_research_events(
        candidates,
        core_company=core_company,
        core_ticker=core_ticker,
        discovery_run_id=discovery_run_id,
    ):
        yield event


async def iter_discovery_ndjson_events(
    payload: Dict[str, Any],
) -> AsyncIterator[Dict[str, Any]]:
    """Yield discovery stream events (dicts) for one run."""
    core_company = payload.get("coreCompany", "")
    core_ticker = str(payload.get("coreTicker", "")).upper()
    scope = payload.get("scope", "level-1")

    yield {
        "event": "start",
        "coreCompany": core_company,
        "coreTicker": core_ticker,
        "scope": scope,
    }
    yield {
        "event": "status",
        "message": f"Researching {core_company or core_ticker} ecosystem…",
    }

    if USE_LIVE_DISCOVERY:
        try:
            async for event in iter_live_llm_events(payload):
                yield event
            return
        except Exception as exc:
            logger.exception("Live discovery stream failed")
            yield {"event": "error", "error": str(exc)}
            return

    yield {"event": "status", "message": "Loading curated ecosystem data…"}
    result = await asyncio.to_thread(run, payload)
    async for event in _emit_result_events(
        result,
        core_company=core_company,
        core_ticker=core_ticker,
    ):
        yield event


async def iter_discovery_ndjson_bytes(payload: Dict[str, Any]) -> AsyncIterator[bytes]:
    """Async byte stream for FastAPI StreamingResponse."""
    async for event in iter_discovery_ndjson_events(payload):
        yield _encode(event)
