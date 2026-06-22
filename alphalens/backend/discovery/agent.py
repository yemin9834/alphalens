"""
Discovery agent — ecosystem candidate discovery.

MVP: curated NVIDIA ecosystem fallback via run().
Guide 4: Bedrock + MCP (Playwright + Brave Search) via run_llm().
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, AsyncIterator, Dict, List, Literal, Tuple

from alphalens_shared.services.discovery import run_discovery, to_api_candidates
from alphalens_shared.services.discovery_persist import maybe_persist_discovery
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from templates import DISCOVERY_INSTRUCTIONS, create_discovery_task

load_dotenv(override=True)

logger = logging.getLogger(__name__)

AGENT_NAME = "Discovery"
INSTRUCTIONS = DISCOVERY_INSTRUCTIONS

USE_LIVE_DISCOVERY = os.getenv("USE_LIVE_DISCOVERY", "false").lower() == "true"


class DiscoveryCandidateLLM(BaseModel):
    model_config = ConfigDict(extra="ignore")

    companyName: str
    ticker: str
    relationshipType: str
    relationshipSummary: str
    confidence: Literal["High", "Medium", "Low"] = "Medium"
    evidenceUrl: str = ""


class DiscoveryLLMOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidates: List[DiscoveryCandidateLLM] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Discover candidates — curated fallback unless USE_LIVE_DISCOVERY=true."""
    from alphalens_shared.bedrock_agent import log_agent_mode

    log_agent_mode(AGENT_NAME, llm=USE_LIVE_DISCOVERY)
    if USE_LIVE_DISCOVERY:
        import asyncio

        try:
            return asyncio.run(run_llm(payload))
        except Exception as exc:
            exc_name = type(exc).__name__
            if "RateLimit" in exc_name or "429" in str(exc):
                logger.warning("Live discovery rate-limited by Bedrock: %s", exc)
            else:
                logger.exception("Live discovery failed — falling back to curated data")
            fallback = run_discovery(payload)
            fallback.setdefault("warnings", []).insert(
                0, f"Live discovery failed ({exc}); using curated fallback."
            )
            return maybe_persist_discovery(payload, fallback)
    return maybe_persist_discovery(payload, run_discovery(payload))


def create_agent(
    core_company: str,
    core_ticker: str,
    scope: str = "level-1",
) -> Tuple[Any, List[Any], str]:
    """
    Create Bedrock discovery agent (Alex researcher pattern).

    MCP servers are started in run_llm() via discovery_mcp_stack() — not returned here
    because they require an async context manager.

    Returns:
        (model, tools, task)
    """
    from alphalens_shared.bedrock_agent import get_litellm_model, require_llm_packages
    from alphalens_shared.mcp_servers import discovery_mcp_enabled

    require_llm_packages()

    if os.getenv("DISCOVERY_MCP_CONFIGURED", "false").lower() != "true":
        raise NotImplementedError(
            "Live discovery requires MCP. Set DISCOVERY_MCP_CONFIGURED=true "
            "and USE_LIVE_DISCOVERY=true (see guides/4_discovery.md)."
        )

    if not discovery_mcp_enabled():
        raise NotImplementedError(
            "No MCP runtime available. Install Node.js (npx) for Playwright/Brave MCP, "
            "or set BRAVE_API_KEY / DISCOVERY_PLAYWRIGHT_MCP=true."
        )

    task = create_discovery_task(core_company, core_ticker, scope)
    model = get_litellm_model()
    return model, [], task


async def run_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Bedrock discovery agent with Playwright + Brave Search MCP."""
    from alphalens_shared.bedrock_agent import run_bedrock_agent
    from alphalens_shared.mcp_servers import discovery_mcp_stack

    core_company = payload.get("coreCompany", "NVIDIA")
    core_ticker = payload.get("coreTicker", "NVDA")
    scope = payload.get("scope", "level-1")

    _, _, task = create_agent(core_company, core_ticker, scope)
    timeout = int(os.getenv("DISCOVERY_MCP_TIMEOUT", "120"))

    async with discovery_mcp_stack(timeout_seconds=timeout) as mcp_servers:
        response = await run_bedrock_agent(
            name=AGENT_NAME,
            instructions=INSTRUCTIONS,
            task=task,
            tools=[],
            mcp_servers=mcp_servers,
            max_turns=int(os.getenv("DISCOVERY_MAX_TURNS", "15")),
        )

    parsed = _parse_discovery_response(str(response))
    candidates = to_api_candidates(
        [c.model_dump() for c in parsed.candidates]
    )

    warnings = list(parsed.warnings)
    if not candidates:
        warnings.append("LLM discovery returned no candidates — verify MCP tools and Bedrock access.")

    result = {
        "success": True,
        "coreCompany": core_company,
        "coreTicker": core_ticker.upper(),
        "candidates": candidates,
        "warnings": warnings,
    }
    return maybe_persist_discovery(payload, result)


async def iter_live_llm_events(payload: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
    """
    Stream discovery LLM output as NDJSON-ready events (tokens, tool status, candidates).

    Uses Runner.run_streamed() so clients receive chunks during long MCP research runs.
    """
    from agents import Agent, ItemHelpers, Runner, trace
    from alphalens_shared.bedrock_agent import get_litellm_model, require_llm_packages
    from alphalens_shared.mcp_servers import discovery_mcp_stack

    require_llm_packages()

    core_company = payload.get("coreCompany", "NVIDIA")
    core_ticker = payload.get("coreTicker", "NVDA")
    scope = payload.get("scope", "level-1")
    _, _, task = create_agent(core_company, core_ticker, scope)
    timeout = int(os.getenv("DISCOVERY_MCP_TIMEOUT", "120"))
    max_turns = int(os.getenv("DISCOVERY_MAX_TURNS", "15"))
    model = get_litellm_model()

    with trace(AGENT_NAME):
        async with discovery_mcp_stack(timeout_seconds=timeout) as mcp_servers:
            agent = Agent(
                name=AGENT_NAME,
                instructions=INSTRUCTIONS,
                model=model,
                tools=[],
                mcp_servers=mcp_servers,
            )
            result = Runner.run_streamed(agent, input=task, max_turns=max_turns)

            async for event in result.stream_events():
                if event.type == "raw_response_event":
                    delta = getattr(event.data, "delta", None)
                    if delta:
                        yield {"event": "token", "token": delta}
                elif event.type == "run_item_stream_event":
                    item = event.item
                    if item.type == "tool_call_item":
                        yield {
                            "event": "status",
                            "message": "Running research tool…",
                        }
                    elif item.type == "tool_call_output_item":
                        yield {
                            "event": "status",
                            "message": "Processing research results…",
                        }
                    elif item.type == "message_output_item":
                        text = ItemHelpers.text_message_output(item)
                        if text and len(text) > 80:
                            yield {
                                "event": "status",
                                "message": text[:200].strip() + ("…" if len(text) > 200 else ""),
                            }

    parsed = _parse_discovery_response(str(result.final_output or ""))
    candidates = to_api_candidates([c.model_dump() for c in parsed.candidates])
    warnings = list(parsed.warnings)
    if not candidates:
        warnings.append(
            "LLM discovery returned no candidates — verify MCP tools and model access."
        )

    result_dict = {
        "success": True,
        "coreCompany": core_company,
        "coreTicker": str(core_ticker).upper(),
        "candidates": candidates,
        "warnings": warnings,
    }
    persisted = maybe_persist_discovery(payload, result_dict)

    for warning in persisted.get("warnings") or []:
        yield {"event": "warning", "message": warning}

    total = len(candidates)
    yield {
        "event": "status",
        "message": (
            f"Found {total} candidate{'s' if total != 1 else ''} — loading results…"
            if total
            else "No candidates found for this ecosystem."
        ),
    }

    delay_raw = os.getenv("DISCOVERY_STREAM_DELAY_MS", "120").strip()
    try:
        delay = max(0.0, int(delay_raw) / 1000.0)
    except ValueError:
        delay = 0.12

    for index, candidate in enumerate(candidates):
        if index > 0 and delay:
            await asyncio.sleep(delay)
        yield {
            "event": "candidate",
            "candidate": candidate,
            "index": index + 1,
            "total": total,
        }

    discovery_run_id = persisted.get("discoveryRunId")
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
                    core_company=persisted.get("coreCompany", core_company),
                    core_ticker=persisted.get("coreTicker", str(core_ticker).upper()),
                )
                research_status = "pending" if enqueued else "failed"
            elif deep_research_enabled():
                async for research_event in _iter_deep_research_events(
                    candidates,
                    core_company=persisted.get("coreCompany", core_company),
                    core_ticker=persisted.get("coreTicker", str(core_ticker).upper()),
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
        "coreCompany": persisted.get("coreCompany", core_company),
        "coreTicker": persisted.get("coreTicker", str(core_ticker).upper()),
        "candidateCount": total,
        "deepResearchCount": researched,
        "researchStatus": research_status,
        "warnings": list(persisted.get("warnings") or []),
        "discoveryRunId": discovery_run_id,
    }


async def _iter_deep_research_events(
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


def _parse_discovery_response(text: str) -> DiscoveryLLMOutput:
    """Extract and validate JSON from agent final output."""
    raw = text.strip()

    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]

    try:
        data = json.loads(raw)
        return DiscoveryLLMOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Could not parse discovery JSON: %s", exc)
        return DiscoveryLLMOutput(
            candidates=[],
            warnings=[f"Could not parse structured discovery output: {exc}"],
        )


def discover(core_company: str, core_ticker: str, scope: str = "level-1") -> Dict[str, Any]:
    return run({"coreCompany": core_company, "coreTicker": core_ticker, "scope": scope})


def format_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return to_api_candidates(candidates)


__all__ = [
    "AGENT_NAME",
    "INSTRUCTIONS",
    "DiscoveryLLMOutput",
    "create_agent",
    "run",
    "run_llm",
    "iter_live_llm_events",
    "discover",
    "format_candidates",
]
