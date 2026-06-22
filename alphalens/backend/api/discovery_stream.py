"""NDJSON stream generator for progressive ecosystem discovery."""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, Iterator

from alphalens_shared.lambda_invoke import (
    invoke_discovery_for_stream,
    iter_discovery_http_stream,
)
from alphalens_shared.services.discovery import to_api_candidates
from alphalens_shared.services.discovery_persist import persist_discovery_run

logger = logging.getLogger(__name__)


def _encode(payload: Dict[str, Any]) -> bytes:
    return (json.dumps(payload, default=str) + "\n").encode("utf-8")


def _stream_delay_seconds() -> float:
    raw = os.getenv("DISCOVERY_STREAM_DELAY_MS", "120").strip()
    try:
        return max(0.0, int(raw) / 1000.0)
    except ValueError:
        return 0.12


def _discovery_service_url() -> str:
    return os.getenv("DISCOVERY_SERVICE_URL", "").strip().rstrip("/")


def _emit_sync_result_events(
    result: Dict[str, Any],
    *,
    core_company: str,
    core_ticker: str,
) -> Iterator[bytes]:
    if not result.get("success", True):
        yield _encode({"event": "error", "error": result.get("error", "Discovery failed")})
        return

    warnings = list(result.get("warnings") or [])
    for warning in warnings:
        yield _encode({"event": "warning", "message": warning})

    candidates = to_api_candidates(result.get("candidates") or [])
    total = len(candidates)
    yield _encode(
        {
            "event": "status",
            "message": (
                f"Found {total} candidate{'s' if total != 1 else ''} — loading results…"
                if total
                else "No candidates found for this ecosystem."
            ),
        }
    )

    delay = _stream_delay_seconds()
    for index, candidate in enumerate(candidates):
        if index > 0 and delay:
            time.sleep(delay)
        yield _encode(
            {
                "event": "candidate",
                "candidate": candidate,
                "index": index + 1,
                "total": total,
            }
        )

    yield _encode(
        {
            "event": "done",
            "coreCompany": result.get("coreCompany", core_company),
            "coreTicker": result.get("coreTicker", core_ticker),
            "candidateCount": total,
            "warnings": warnings,
            "discoveryRunId": result.get("discoveryRunId"),
        }
    )


def iter_discovery_stream(payload: Dict[str, Any], clerk_user_id: str) -> Iterator[bytes]:
    """Yield NDJSON lines as discovery progresses."""
    core_company = payload.get("coreCompany", "")
    core_ticker = str(payload.get("coreTicker", "")).upper()
    scope = payload.get("scope", "level-1")
    invoke_payload = {**payload, "clerkUserId": clerk_user_id}

    if _discovery_service_url():
        try:
            for event in iter_discovery_http_stream(invoke_payload):
                yield _encode(event)
                if event.get("event") == "error":
                    return
            return
        except Exception as exc:
            logger.exception("Discovery HTTP stream failed")
            yield _encode({"event": "error", "error": str(exc)})
            return

    yield _encode(
        {
            "event": "start",
            "coreCompany": core_company,
            "coreTicker": core_ticker,
            "scope": scope,
        }
    )
    yield _encode(
        {
            "event": "status",
            "message": f"Researching {core_company or core_ticker} ecosystem…",
        }
    )

    result_queue: queue.Queue[Any] = queue.Queue()
    heartbeat_seconds = float(os.getenv("DISCOVERY_STREAM_HEARTBEAT_SEC", "8"))

    def worker() -> None:
        try:
            result = invoke_discovery_for_stream(invoke_payload)
            if not result.get("discoveryRunId"):
                run_id = persist_discovery_run(clerk_user_id, invoke_payload, result)
                if run_id:
                    result["discoveryRunId"] = run_id
            result_queue.put(result)
        except Exception as exc:
            result_queue.put(exc)
        finally:
            result_queue.put(None)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        try:
            item = result_queue.get(timeout=heartbeat_seconds)
        except queue.Empty:
            yield _encode(
                {
                    "event": "status",
                    "message": "Still researching ecosystem…",
                }
            )
            continue
        if item is None:
            break
        if isinstance(item, Exception):
            logger.exception("Discovery stream failed")
            yield _encode({"event": "error", "error": str(item)})
            return

        yield from _emit_sync_result_events(
            item,
            core_company=core_company,
            core_ticker=core_ticker,
        )
        return

    thread.join()
    yield _encode({"event": "error", "error": "Discovery stream ended unexpectedly"})
