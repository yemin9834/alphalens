"""SSE stream generator for Q&A — runs on alphalens-qa (Function URL)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator, Dict, Iterator

from agent import run, stream_llm_tokens

logger = logging.getLogger(__name__)

USE_LLM_QA = os.getenv("USE_LLM_QA", "false").lower() == "true"


def _sse(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, default=str)}\n\n".encode("utf-8")


def _chunk_text(text: str, size: int = 18) -> Iterator[str]:
    if not text:
        return
    i = 0
    while i < len(text):
        yield text[i : i + size]
        i += size


def _heartbeat_seconds() -> float:
    raw = os.getenv("QA_STREAM_HEARTBEAT_SEC", "8").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 8.0


async def _stream_llm_with_heartbeats(
    payload: Dict[str, Any],
) -> AsyncIterator[bytes]:
    """Pump LLM tokens with SSE keepalives while Aurora/LLM work is in progress."""
    token_queue: asyncio.Queue[Any] = asyncio.Queue()
    heartbeat = _heartbeat_seconds()

    async def pump() -> None:
        try:
            async for token in stream_llm_tokens(payload):
                await token_queue.put(token)
        except Exception as exc:
            await token_queue.put(exc)
        finally:
            await token_queue.put(None)

    task = asyncio.create_task(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(token_queue.get(), timeout=heartbeat)
            except asyncio.TimeoutError:
                yield b": keepalive\n\n"
                continue
            if item is None:
                break
            if isinstance(item, Exception):
                yield _sse({"error": str(item)})
                return
            if isinstance(item, str) and item.startswith("Error:"):
                yield _sse({"error": item})
                return
            yield _sse({"token": item})
    finally:
        await task


async def iter_qa_sse_bytes(payload: Dict[str, Any]) -> AsyncIterator[bytes]:
    """Yield SSE bytes for one Q&A request."""
    job_id = payload.get("jobId") or payload.get("job_id")
    logger.info("Q&A stream start job=%s llm=%s", job_id, USE_LLM_QA)
    yield _sse({"token": "Thinking… "})

    if USE_LLM_QA:
        async for event in _stream_llm_with_heartbeats(payload):
            yield event
    else:
        result = await asyncio.to_thread(run, payload)
        if not result.get("success", True):
            yield _sse({"error": result.get("error", "Q&A failed")})
            return
        answer = str(result.get("answer") or "")
        for piece in _chunk_text(answer):
            yield _sse({"token": piece})

    yield _sse({"done": True})
    logger.info("Q&A stream done job=%s", job_id)
