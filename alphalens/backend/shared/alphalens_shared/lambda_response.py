"""Consistent Lambda handler responses for AlphaLens agents."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict

from alphalens_shared.json_utils import dumps_json
from alphalens_shared.lambda_logging import configure_lambda_logging

configure_lambda_logging()

logger = logging.getLogger(__name__)


def parse_event(event: Any) -> Dict[str, Any]:
    if isinstance(event, dict):
        return event
    if isinstance(event, str):
        return json.loads(event)
    raise TypeError(f"Expected dict or JSON string, got {type(event).__name__}")


def response_from_result(
    result: Dict[str, Any],
    *,
    ok_status: int = 200,
    error_status: int = 400,
) -> Dict[str, Any]:
    status = ok_status
    if isinstance(result, dict) and result.get("success") is False:
        status = error_status
    return {"statusCode": status, "body": dumps_json(result)}


def error_response(message: str, *, status: int = 500) -> Dict[str, Any]:
    return {"statusCode": status, "body": dumps_json({"success": False, "error": message})}


def handle_agent_run(
    agent_name: str,
    event: Any,
    context: Any,
    run_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    logger.info("%s invoked", agent_name)
    try:
        payload = parse_event(event)
        return response_from_result(run_fn(payload))
    except Exception as exc:
        logger.exception("%s failed", agent_name)
        return error_response(str(exc))
