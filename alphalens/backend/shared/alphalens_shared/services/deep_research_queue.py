"""Enqueue Phase 2 deep research jobs (SQS or local HTTP fallback)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def deep_research_queue_url() -> str:
    return os.getenv("DEEP_RESEARCH_QUEUE_URL", "").strip()


def discovery_service_url() -> str:
    return os.getenv("DISCOVERY_SERVICE_URL", "").strip().rstrip("/")


def enqueue_deep_research_run(
    discovery_run_id: str,
    *,
    core_company: str = "",
    core_ticker: str = "",
) -> bool:
    """
    Queue async deep research for a discovery run.

    Returns True when a queue message was sent or HTTP kickoff succeeded.
    """
    if not discovery_run_id:
        return False

    body = {
        "discoveryRunId": discovery_run_id,
        "coreCompany": core_company,
        "coreTicker": core_ticker,
    }
    queue_url = deep_research_queue_url()
    if queue_url:
        try:
            import boto3

            boto3.client("sqs").send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(body),
            )
            logger.info("Enqueued deep research for run %s", discovery_run_id)
            return True
        except Exception:
            logger.exception("Failed to enqueue deep research SQS message")
            return False

    service_url = discovery_service_url()
    if not service_url:
        logger.warning("No DEEP_RESEARCH_QUEUE_URL or DISCOVERY_SERVICE_URL — async research skipped")
        return False

    return _post_deep_research_run(service_url, body)


def _post_deep_research_run(service_url: str, body: Dict[str, Any]) -> bool:
    endpoint = f"{service_url}/deep-research/run"
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = int(os.getenv("DEEP_RESEARCH_HTTP_TIMEOUT", "15"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        logger.error("Deep research kickoff HTTP %s: %s", exc.code, exc.read())
        return False
    except Exception:
        logger.exception("Deep research HTTP kickoff failed")
        return False
