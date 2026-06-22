"""NDJSON stream generator for progressive sync portfolio analysis."""

from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Any, Callable, Dict, Iterator, List, Optional

from alphalens_shared.services.pipeline import run_analysis_pipeline

logger = logging.getLogger(__name__)

ParseFn = Callable[[object], Any]


def _encode(payload: Dict[str, Any]) -> bytes:
    return (json.dumps(payload, default=str) + "\n").encode("utf-8")


def _ranked_rows(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    ranked = analysis.get("rankedCandidates") or []
    return [r for r in ranked if isinstance(r, dict)]


def format_stage_event(
    stage: str,
    data: Dict[str, Any],
    warnings: List[str],
    *,
    parse_validation: ParseFn,
    parse_analysis: ParseFn,
    parse_portfolio: ParseFn,
) -> Dict[str, Any]:
    base: Dict[str, Any] = {"stage": stage, "warnings": warnings}

    if stage == "discovery":
        base["discoverySkipped"] = bool(data.get("skipped"))
        base["candidateCount"] = data.get("candidateCount")
        if data.get("discoveryRunId"):
            base["discoveryRunId"] = data["discoveryRunId"]
        return base

    if stage == "validation":
        report = parse_validation(data.get("validationReport"))
        base["validationReport"] = report.model_dump() if report else None
        return base

    if stage == "analysis":
        report = parse_analysis(data.get("analysisReport"))
        base["analysisReport"] = report.model_dump() if report else None
        base["rankedCandidates"] = _ranked_rows(data)
        base["marketCondition"] = data.get("marketCondition")
        return base

    if stage == "portfolio":
        recommendation = data.get("recommendation") or data.get("recommendationPayload")
        report = parse_portfolio(data.get("portfolioReport"))
        base["portfolioReport"] = report.model_dump() if report else None
        base["recommendation"] = recommendation
        return base

    return base


def iter_analysis_stream(
    payload: Dict[str, Any],
    *,
    parse_validation: ParseFn,
    parse_analysis: ParseFn,
    parse_portfolio: ParseFn,
) -> Iterator[bytes]:
    """Yield NDJSON lines as each pipeline stage completes."""
    event_queue: queue.SimpleQueue[Optional[bytes]] = queue.SimpleQueue()
    warnings_acc: List[str] = []
    result_holder: Dict[str, Any] = {}
    error_holder: Dict[str, Exception] = {}

    def on_stage(stage: str, data: Dict[str, Any]) -> None:
        nonlocal warnings_acc
        new_warnings = data.get("newWarnings") or []
        if new_warnings:
            warnings_acc = [*warnings_acc, *new_warnings]
        event = format_stage_event(
            stage,
            data,
            warnings_acc,
            parse_validation=parse_validation,
            parse_analysis=parse_analysis,
            parse_portfolio=parse_portfolio,
        )
        event_queue.put(_encode(event))

    def worker() -> None:
        try:
            result_holder["result"] = run_analysis_pipeline(payload, on_stage=on_stage)
        except Exception as exc:
            logger.exception("Streaming pipeline failed")
            error_holder["error"] = exc
        finally:
            event_queue.put(None)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        item = event_queue.get()
        if item is None:
            break
        yield item

    thread.join()

    if error_holder:
        yield _encode({"stage": "error", "error": str(error_holder["error"])})
        return

    result = result_holder.get("result") or {}
    if not result.get("success", True):
        yield _encode(
            {
                "stage": "error",
                "error": result.get("error", "Portfolio analysis failed"),
            }
        )
        return

    recommendation = result.get("recommendation") or {}
    portfolio_report = parse_portfolio(result.get("portfolioReport"))
    validation_report = parse_validation(result.get("validationReport"))
    analysis_report = parse_analysis(result.get("analysisReport"))

    yield _encode(
        {
            "stage": "complete",
            "warnings": result.get("warnings", warnings_acc),
            "validationReport": validation_report.model_dump() if validation_report else None,
            "analysisReport": analysis_report.model_dump() if analysis_report else None,
            "portfolioReport": portfolio_report.model_dump() if portfolio_report else None,
            "rankedCandidates": _ranked_rows(result),
            "recommendation": recommendation,
        }
    )
