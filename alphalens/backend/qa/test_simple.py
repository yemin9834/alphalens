#!/usr/bin/env python3
"""Simple local test for Q&A agent via lambda_handler."""

import json
import os

from dotenv import load_dotenv

load_dotenv(override=True)

from alphalens_shared.test_logging import configure_test_logging

configure_test_logging()

from lambda_handler import lambda_handler


def main():
    print("Testing Q&A Agent...")
    print("=" * 60)

    if not os.getenv("AURORA_CLUSTER_ARN"):
        result = lambda_handler(
            {"jobId": "00000000-0000-0000-0000-000000000001", "question": "summary?"},
            None,
        )
        print(f"Status Code: {result['statusCode']}")
        body = json.loads(result["body"])
        print(f"Expected failure without DB: {body.get('error', body)}")
        return 0 if result["statusCode"] == 400 else 1

    from src import Database

    db = Database()
    jobs = db.analysis_jobs.find_by_user("test_user_001", limit=5)
    completed = [j for j in jobs if j.get("status") == "completed"]
    if not completed:
        print("⚠️  No completed jobs — run orchestrator test_simple.py first")
        return 0

    job_id = completed[0]["id"]
    for question in ("What is the summary?", "What actions do you recommend?", "What is the risk?"):
        result = lambda_handler({"jobId": job_id, "question": question}, None)
        body = json.loads(result["body"])
        print(f"\nQ: {question}")
        print(f"Status: {result['statusCode']}")
        print(f"A: {body.get('answer', body.get('error', ''))[:200]}")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
