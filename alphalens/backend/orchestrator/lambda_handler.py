"""
Orchestrator Lambda Handler — triggered by SQS analysis jobs.
"""

import json
import logging

from alphalens_shared.lambda_logging import configure_lambda_logging
from alphalens_shared.json_utils import dumps_json
from alphalens_shared.lambda_response import error_response, response_from_result
from pipeline_job import process_job

configure_lambda_logging()
logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    results = []
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            job_id = body.get("jobId") or body.get("job_id")
            if not job_id:
                logger.error("Missing jobId in SQS message: %s", body)
                results.append({"success": False, "error": "Missing jobId"})
                continue

            logger.info("Processing analysis job %s", job_id)
            results.append(process_job(job_id))
        except Exception as exc:
            logger.exception("Failed processing SQS record")
            results.append({"success": False, "error": str(exc)})

    if not results:
        return error_response("No SQS records in event", status=400)

    if len(results) == 1:
        return response_from_result(results[0], error_status=500)

    return {"statusCode": 200, "body": dumps_json({"results": results})}
