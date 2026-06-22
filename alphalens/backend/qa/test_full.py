#!/usr/bin/env python3
"""Full test for Q&A agent via deployed Lambda."""

import json
import os

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

FUNCTION_NAME = os.getenv("QA_FUNCTION", "alphalens-qa")


def main():
    print("Testing Q&A Lambda")
    print("=" * 60)

    if not os.getenv("AURORA_CLUSTER_ARN"):
        print("⚠️  AURORA_CLUSTER_ARN not set — skipping")
        return 0

    from src import Database

    db = Database()
    jobs = db.analysis_jobs.find_by_user("test_user_001", limit=5)
    completed = [j for j in jobs if j.get("status") == "completed"]
    if not completed:
        print("⚠️  No completed jobs — run orchestrator test_full.py first")
        return 0

    job_id = completed[0]["id"]
    payload = {"jobId": job_id, "question": "What is the summary?"}

    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    result = json.loads(response["Payload"].read())

    if isinstance(result, dict) and result.get("statusCode") == 200:
        body = json.loads(result["body"])
        print(f"✅ Q&A OK — {body.get('answer', '')[:120]}")
        return 0

    print(json.dumps(result, indent=2))
    print("\n❌ Q&A test failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
