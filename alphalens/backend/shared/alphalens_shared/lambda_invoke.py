"""Invoke AlphaLens agent Lambdas with local mock routing."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator

import boto3

from alphalens_shared.json_utils import dumps_json

logger = logging.getLogger(__name__)

lambda_client = boto3.client("lambda")

VALIDATOR_FUNCTION = os.getenv("VALIDATOR_FUNCTION", "alphalens-validator")
ANALYST_FUNCTION = os.getenv("ANALYST_FUNCTION", "alphalens-analyst")
PORTFOLIO_FUNCTION = os.getenv("PORTFOLIO_FUNCTION", "alphalens-portfolio")
DISCOVERY_FUNCTION = os.getenv("DISCOVERY_FUNCTION", "alphalens-discovery")
QA_FUNCTION = os.getenv("QA_FUNCTION", "alphalens-qa")


def _mock_lambdas() -> bool:
    """Read at call time — do not cache at import (dotenv may load later)."""
    return os.getenv("MOCK_LAMBDAS", "false").lower() == "true"


def _mock_dispatch(function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    from alphalens_shared.services.analyst import run_analyst
    from alphalens_shared.services.discovery import run_discovery
    from alphalens_shared.services.portfolio import run_portfolio_agent
    from alphalens_shared.services.validator import run_validator_agent

    handlers = {
        VALIDATOR_FUNCTION: run_validator_agent,
        ANALYST_FUNCTION: run_analyst,
        PORTFOLIO_FUNCTION: run_portfolio_agent,
        DISCOVERY_FUNCTION: run_discovery,
        "alphalens-validator": run_validator_agent,
        "alphalens-analyst": run_analyst,
        "alphalens-portfolio": run_portfolio_agent,
        "alphalens-discovery": run_discovery,
    }
    handler = handlers.get(function_name)
    if not handler:
        return {"success": False, "error": f"No mock handler for {function_name}"}
    return handler(payload)


def _post_json(url: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    data = dumps_json(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def invoke_discovery(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route discovery to live HTTP service, mock handler, or slim Lambda.

    When DISCOVERY_SERVICE_URL is set, POST /discover on that service (local or AWS).
    """
    service_url = os.getenv("DISCOVERY_SERVICE_URL", "").strip().rstrip("/")
    timeout = int(os.getenv("DISCOVERY_HTTP_TIMEOUT", "300"))

    if service_url:
        endpoint = f"{service_url}/discover"
        label = "[MOCK->HTTP]" if _mock_lambdas() else "[HTTP]"
        logger.info("%s %s", label, endpoint)
        try:
            return _post_json(endpoint, payload, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.exception("Discovery HTTP %s: %s", exc.code, detail)
            return {"success": False, "error": f"HTTP {exc.code}: {detail}"}
        except Exception as exc:
            logger.exception("Discovery HTTP failed")
            return {"success": False, "error": str(exc)}

    if _mock_lambdas():
        logger.info("[MOCK] %s", DISCOVERY_FUNCTION)
        return _mock_dispatch(DISCOVERY_FUNCTION, payload)

    return invoke_agent(DISCOVERY_FUNCTION, payload)


def iter_discovery_http_stream(payload: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """
    POST /discover/stream on the live discovery service and yield NDJSON events.

    Keeps the HTTP connection active while the discovery agent streams LLM tokens.
    """
    service_url = os.getenv("DISCOVERY_SERVICE_URL", "").strip().rstrip("/")
    if not service_url:
        raise RuntimeError("DISCOVERY_SERVICE_URL is not configured")

    stream_timeout = int(
        os.getenv(
            "DISCOVERY_STREAM_HTTP_TIMEOUT",
            os.getenv("DISCOVERY_HTTP_TIMEOUT", "300"),
        )
    )
    endpoint = f"{service_url}/discover/stream"
    label = "[MOCK->HTTP]" if _mock_lambdas() else "[HTTP]"
    logger.info("%s %s (stream timeout=%ss)", label, endpoint, stream_timeout)

    data = dumps_json(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/x-ndjson",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=stream_timeout) as response:
        buffer = b""
        while True:
            chunk = response.read(8192)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if line:
                    yield json.loads(line.decode("utf-8"))
        tail = buffer.strip()
        if tail:
            yield json.loads(tail.decode("utf-8"))


def invoke_discovery_for_stream(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Discovery for NDJSON stream endpoints.

    Uses the same routing as invoke_discovery with a stream-specific timeout
    (DISCOVERY_STREAM_HTTP_TIMEOUT, defaulting to DISCOVERY_HTTP_TIMEOUT).
    CloudFront proxies /api/* to the API Lambda Function URL (no 30s API GW cap).
    """
    stream_timeout = int(
        os.getenv(
            "DISCOVERY_STREAM_HTTP_TIMEOUT",
            os.getenv("DISCOVERY_HTTP_TIMEOUT", "300"),
        )
    )
    service_url = os.getenv("DISCOVERY_SERVICE_URL", "").strip().rstrip("/")

    if service_url:
        endpoint = f"{service_url}/discover"
        label = "[MOCK->HTTP]" if _mock_lambdas() else "[HTTP]"
        logger.info("%s %s (stream timeout=%ss)", label, endpoint, stream_timeout)
        try:
            return _post_json(endpoint, payload, timeout=stream_timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.exception("Discovery stream HTTP %s: %s", exc.code, detail)
            return {"success": False, "error": f"HTTP {exc.code}: {detail}"}
        except Exception as exc:
            logger.exception("Discovery stream HTTP failed")
            return {"success": False, "error": str(exc)}

    if _mock_lambdas():
        logger.info("[MOCK] %s", DISCOVERY_FUNCTION)
        return _mock_dispatch(DISCOVERY_FUNCTION, payload)

    return invoke_agent(DISCOVERY_FUNCTION, payload)


def _invoke_lambda_direct(function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        logger.info("[INVOKE] %s", function_name)
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=dumps_json(payload),
        )
        result = json.loads(response["Payload"].read())
        if isinstance(result, dict) and "statusCode" in result and "body" in result:
            body = result["body"]
            if isinstance(body, str):
                return json.loads(body)
            return body
        return result
    except Exception as exc:
        logger.exception("Lambda invoke failed for %s", function_name)
        return {"success": False, "error": str(exc)}


def invoke_qa(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Q&A via alphalens-qa Lambda invoke.

    Set MOCK_QA=true for offline deterministic keyword answers.
    """
    if os.getenv("MOCK_QA", "false").lower() == "true":
        from alphalens_shared.services.qa import run_qa

        logger.info("[MOCK] %s (MOCK_QA=true)", QA_FUNCTION)
        return run_qa(payload)

    return _invoke_lambda_direct(QA_FUNCTION, payload)


def invoke_portfolio(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Portfolio agent — optional in-process routing for local metric changes."""
    if _mock_lambdas():
        logger.info("[MOCK] %s", PORTFOLIO_FUNCTION)
        return _mock_dispatch(PORTFOLIO_FUNCTION, payload)
    if os.getenv("USE_LOCAL_PORTFOLIO", "false").lower() == "true":
        logger.info("[LOCAL] %s (USE_LOCAL_PORTFOLIO=true)", PORTFOLIO_FUNCTION)
        return _mock_dispatch(PORTFOLIO_FUNCTION, payload)
    return _invoke_lambda_direct(PORTFOLIO_FUNCTION, payload)


def invoke_agent(function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if function_name == PORTFOLIO_FUNCTION:
        return invoke_portfolio(payload)
    if _mock_lambdas():
        logger.info("[MOCK] %s", function_name)
        return _mock_dispatch(function_name, payload)
    return _invoke_lambda_direct(function_name, payload)
