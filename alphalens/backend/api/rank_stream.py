"""NDJSON stream generator for progressive rank-only analysis."""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from typing import Any, Callable, Dict, Iterator, List

from alphalens_shared.lambda_invoke import ANALYST_FUNCTION, VALIDATOR_FUNCTION, invoke_agent
from alphalens_shared.services.analyst import run_analyst
from alphalens_shared.services.analyst_narrative import maybe_enrich_analyst_narrative
from alphalens_shared.services.validator import run_validator_agent

logger = logging.getLogger(__name__)

ParseFn = Callable[[object], Any]


def _encode(payload: Dict[str, Any]) -> bytes:
    return (json.dumps(payload, default=str) + "\n").encode("utf-8")


def _mock_lambdas() -> bool:
    return os.getenv("MOCK_LAMBDAS", "false").lower() == "true"


def _invoke_or_local(function_name: str, payload: dict, local_handler):
    if _mock_lambdas():
        return local_handler(payload)
    return invoke_agent(function_name, payload)


def _stream_delay_seconds() -> float:
    raw = os.getenv("RANK_STREAM_DELAY_MS", os.getenv("DISCOVERY_STREAM_DELAY_MS", "120")).strip()
    try:
        return max(0.0, int(raw) / 1000.0)
    except ValueError:
        return 0.12


def _ranked_row_fields(row: Dict[str, Any], allowed_fields: set[str]) -> Dict[str, Any]:
    return {k: v for k, v in row.items() if k in allowed_fields}


def iter_rank_stream(
    request: Dict[str, Any],
    *,
    parse_validation: ParseFn,
    parse_analysis: ParseFn,
    ranked_candidate_fields: set[str],
) -> Iterator[bytes]:
    """Yield NDJSON lines: validation → ranked rows → analysis report → complete."""
    raw_candidates = request.get("candidates") or []
    risk_profile = request.get("riskProfile", "balanced")
    market_condition = request.get("marketCondition", "Neutral")

    yield _encode({"stage": "start"})

    result_queue: queue.SimpleQueue[Any] = queue.SimpleQueue()

    def worker() -> None:
        try:
            validated = _invoke_or_local(
                VALIDATOR_FUNCTION,
                {"candidates": raw_candidates},
                run_validator_agent,
            )
            if not validated.get("success", True):
                result_queue.put(
                    RuntimeError(validated.get("error", "Validation failed"))
                )
                return

            good = [
                c
                for c in validated.get("validatedCandidates", [])
                if c.get("tickerValidation") != "invalid"
            ]
            analyst_payload = {
                "riskProfile": risk_profile,
                "marketCondition": market_condition,
                "candidates": good,
            }
            analysis = _invoke_or_local(ANALYST_FUNCTION, analyst_payload, run_analyst)
            if _mock_lambdas():
                analysis = maybe_enrich_analyst_narrative(analyst_payload, analysis)
            if not analysis.get("success", True):
                result_queue.put(RuntimeError(analysis.get("error", "Ranking failed")))
                return

            result_queue.put(
                {
                    "validated": validated,
                    "analysis": analysis,
                }
            )
        except Exception as exc:
            result_queue.put(exc)
        finally:
            result_queue.put(None)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    yield _encode({"stage": "status", "message": "Validating tickers…"})

    while True:
        item = result_queue.get()
        if item is None:
            break
        if isinstance(item, Exception):
            logger.exception("Rank stream failed")
            yield _encode({"stage": "error", "error": str(item)})
            return

        validated = item["validated"]
        analysis = item["analysis"]
        validation_warnings = list(validated.get("warnings") or [])
        analysis_warnings = list(analysis.get("warnings") or [])
        warnings = validation_warnings + analysis_warnings

        validation_report = parse_validation(validated.get("validationReport"))
        yield _encode(
            {
                "stage": "validation",
                "warnings": warnings,
                "validationReport": (
                    validation_report.model_dump() if validation_report else None
                ),
            }
        )

        ranked_rows = [
            r for r in (analysis.get("rankedCandidates") or []) if isinstance(r, dict)
        ]
        total = len(ranked_rows)
        delay = _stream_delay_seconds()

        yield _encode(
            {
                "stage": "status",
                "message": (
                    f"Ranking {total} opportunit{'ies' if total != 1 else 'y'}…"
                    if total
                    else "No rankable candidates after validation."
                ),
            }
        )

        for index, row in enumerate(ranked_rows):
            if index > 0 and delay:
                time.sleep(delay)
            candidate = _ranked_row_fields(row, ranked_candidate_fields)
            yield _encode(
                {
                    "stage": "ranked",
                    "rankedCandidate": candidate,
                    "index": index + 1,
                    "total": total,
                }
            )

        analysis_report = parse_analysis(analysis.get("analysisReport"))
        ranked_candidates = [
            _ranked_row_fields(row, ranked_candidate_fields) for row in ranked_rows
        ]

        if analysis_report:
            yield _encode(
                {
                    "stage": "analysis",
                    "analysisReport": analysis_report.model_dump(),
                }
            )

        yield _encode(
            {
                "stage": "complete",
                "warnings": warnings,
                "validationReport": (
                    validation_report.model_dump() if validation_report else None
                ),
                "analysisReport": analysis_report.model_dump() if analysis_report else None,
                "rankedCandidates": ranked_candidates,
            }
        )
        return

    thread.join()
    yield _encode({"stage": "error", "error": "Rank stream ended unexpectedly"})
