"""
SQS trigger — POST to discovery-live /deep-research/run.

Package: cd backend/deep_research_trigger && uv run package.py
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    service_url = os.getenv("DISCOVERY_SERVICE_URL", "").strip().rstrip("/")
    if not service_url:
        logger.error("DISCOVERY_SERVICE_URL not configured")
        return {"statusCode": 500, "body": "DISCOVERY_SERVICE_URL not configured"}

    results = []
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            run_id = body.get("discoveryRunId") or body.get("discovery_run_id")
            if not run_id:
                results.append({"success": False, "error": "Missing discoveryRunId"})
                continue

            payload = json.dumps(body).encode("utf-8")
            request = urllib.request.Request(
                f"{service_url}/deep-research/run",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            timeout = int(os.getenv("DEEP_RESEARCH_HTTP_TIMEOUT", "30"))
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8")
                results.append({"success": True, "discoveryRunId": run_id, "response": text})
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.error("HTTP %s from discovery service: %s", exc.code, detail)
            results.append({"success": False, "error": f"HTTP {exc.code}: {detail}"})
        except Exception as exc:
            logger.exception("Deep research trigger failed")
            results.append({"success": False, "error": str(exc)})

    if len(results) == 1:
        item = results[0]
        return {
            "statusCode": 200 if item.get("success") else 500,
            "body": json.dumps(item),
        }
    return {"statusCode": 200, "body": json.dumps({"results": results})}
