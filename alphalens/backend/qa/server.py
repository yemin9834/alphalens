"""
Q&A service — FastAPI on Lambda (Function URL + Lambda Web Adapter).

POST /ask          — sync JSON (legacy invoke_qa HTTP routing)
POST /ask/stream   — SSE token stream from alphalens-qa LLM
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

_root_env = Path(__file__).resolve().parents[2] / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=True)
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AlphaLens Q&A Service")


class AskRequest(BaseModel):
    model_config = {"extra": "ignore"}

    jobId: str
    question: str
    clerk_user_id: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "alphalens-qa",
        "llm": os.getenv("USE_LLM_QA", "false").lower() == "true",
        "provider": os.getenv("LLM_PROVIDER", "bedrock"),
    }


@app.post("/ask")
async def ask(request: AskRequest):
    from agent import run

    result = await asyncio.to_thread(run, request.model_dump())
    if not result.get("success", True):
        raise HTTPException(status_code=400, detail=result.get("error", "Q&A failed"))
    return result


@app.post("/ask/stream")
async def ask_stream(request: AskRequest):
    from sse_stream import iter_qa_sse_bytes

    return StreamingResponse(
        iter_qa_sse_bytes(request.model_dump()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
