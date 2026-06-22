"""SSE stream generator for job Q&A — invokes alphalens-qa then chunks the answer."""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from typing import Iterator

from alphalens_shared.lambda_invoke import invoke_qa
from alphalens_shared.services.qa import run_qa

logger = logging.getLogger(__name__)


def _sse(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, default=str)}\n\n".encode("utf-8")


def _chunk_text(text: str, size: int = 18) -> Iterator[str]:
    if not text:
        return
    i = 0
    while i < len(text):
        yield text[i : i + size]
        i += size


def _stream_delay_seconds() -> float:
    raw = os.getenv("QA_STREAM_DELAY_MS", os.getenv("DISCOVERY_STREAM_DELAY_MS", "40")).strip()
    try:
        return max(0.0, int(raw) / 1000.0)
    except ValueError:
        return 0.04


def _mock_qa() -> bool:
    return os.getenv("MOCK_QA", "false").lower() == "true"


def _resolve_answer(job_id: str, question: str, clerk_user_id: str) -> str:
    payload = {
        "jobId": job_id,
        "question": question,
        "clerk_user_id": clerk_user_id,
    }
    if _mock_qa():
        result = run_qa(payload)
    else:
        result = invoke_qa(payload)

    if not result.get("success", True):
        raise RuntimeError(result.get("error", "Q&A failed"))
    return str(result.get("answer") or "")


def iter_qa_sse(job_id: str, question: str, clerk_user_id: str) -> Iterator[bytes]:
    """Yield Server-Sent Events for a Q&A answer."""
    yield _sse({"token": "Thinking… "})

    out_queue: queue.SimpleQueue = queue.SimpleQueue()
    heartbeat = float(os.getenv("QA_STREAM_HEARTBEAT_SEC", "8"))

    def worker() -> None:
        try:
            out_queue.put(_resolve_answer(job_id, question, clerk_user_id))
        except Exception as exc:
            logger.exception("Q&A stream worker failed")
            out_queue.put(exc)
        finally:
            out_queue.put(None)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    answer: str | BaseException | None = None
    while answer is None:
        try:
            item = out_queue.get(timeout=heartbeat)
        except queue.Empty:
            yield b": keepalive\n\n"
            continue
        if item is None:
            yield _sse({"error": "Q&A ended unexpectedly"})
            return
        answer = item

    if isinstance(answer, BaseException):
        yield _sse({"error": str(answer)})
        return

    delay = _stream_delay_seconds()
    for index, piece in enumerate(_chunk_text(answer)):
        if index > 0 and delay:
            time.sleep(delay)
        yield _sse({"token": piece})

    yield _sse({"done": True})
