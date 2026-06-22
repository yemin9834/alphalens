"""
Discovery service — FastAPI on Lambda (container + Function URL) or local uvicorn.

POST /discover runs Bedrock/OpenAI + MCP (Playwright + Brave Search).
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AlphaLens Discovery Service")


class DiscoverRequest(BaseModel):
    coreCompany: str = "NVIDIA"
    coreTicker: str = "NVDA"
    scope: str = "level-1"
    clerkUserId: str | None = None


class DeepResearchRunRequest(BaseModel):
    discoveryRunId: str
    coreCompany: str = ""
    coreTicker: str = ""


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "alphalens-discovery",
        "live": os.getenv("USE_LIVE_DISCOVERY", "false").lower() == "true",
        "llmProvider": os.getenv("LLM_PROVIDER", "bedrock"),
        "mcpConfigured": os.getenv("DISCOVERY_MCP_CONFIGURED", "false").lower() == "true",
    }


@app.post("/discover")
async def discover(request: DiscoverRequest):
    from agent import run_llm

    try:
        result = await run_llm(request.model_dump())
    except Exception as exc:
        logger.exception("Discovery failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not result.get("success", True):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Discovery failed"),
        )
    return result


@app.post("/deep-research/run")
async def deep_research_run(request: DeepResearchRunRequest):
    """Run Phase 2 deep research to completion (Lambda must await — no background tasks)."""
    from deep_research_phase2 import process_discovery_run

    run_id = request.discoveryRunId.strip()
    if not run_id:
        raise HTTPException(status_code=400, detail="discoveryRunId is required")

    logger.info("Starting deep research for run %s", run_id)
    try:
        result = await process_discovery_run(run_id)
    except Exception as exc:
        logger.exception("Deep research failed for %s", run_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "Deep research finished for run %s status=%s",
        run_id,
        result.get("researchStatus"),
    )
    return {
        "status": "completed",
        "discoveryRunId": run_id,
        "researchStatus": result.get("researchStatus"),
        "progress": result.get("progress"),
    }


@app.post("/discover/stream")
async def discover_stream(request: DiscoverRequest):
    """Stream discovery as NDJSON: tokens during LLM/MCP, then candidates."""
    from ndjson_stream import iter_discovery_ndjson_bytes

    return StreamingResponse(
        iter_discovery_ndjson_bytes(request.model_dump()),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
