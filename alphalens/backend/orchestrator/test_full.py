#!/usr/bin/env python3
"""
Full end-to-end test: create analysis_jobs row, enqueue SQS, poll until complete.
"""

import json
import os
import time
from datetime import datetime, timezone

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

from src import Database
from src.schemas import AnalysisJobCreate

QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")
TIMEOUT_SECONDS = 180


def main():
    print("=" * 70)
    print("AlphaLens Agent Orchestra — Full Test")
    print("=" * 70)

    sts = boto3.client("sts")
    account = sts.get_caller_identity()["Account"]
    region = boto3.Session().region_name or os.getenv("DEFAULT_AWS_REGION", "us-east-1")
    print(f"AWS Account: {account}")
    print(f"AWS Region: {region}")
    print()

    if not QUEUE_URL:
        print("❌ SQS_QUEUE_URL not set in alphalens/.env")
        print("   Run: cd alphalens/terraform/2_agents && terraform output sqs_queue_url")
        return 1

    db = Database()
    user = db.users.find_by_clerk_id("test_user_001")
    if not user:
        print("❌ test_user_001 not found. Run:")
        print("   cd alphalens/backend/database && uv run reset_db.py --with-test-data")
        return 1

    print(f"✓ Test user: {user.get('display_name', 'test_user_001')}")

    payload = {
        "riskProfile": "balanced",
        "portfolio": [
            {"ticker": "NVDA", "weight": 30},
            {"ticker": "AAPL", "weight": 30},
            {"ticker": "CASH", "weight": 40},
        ],
        "coreCompany": "NVIDIA",
        "coreTicker": "NVDA",
        "test_run": True,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }

    print("\n🚀 Creating analysis job...")
    job_id = db.analysis_jobs.create_job(
        "test_user_001",
        AnalysisJobCreate(request_payload=payload),
    )
    print(f"✓ Job ID: {job_id}")

    print("\n📤 Sending to SQS...")
    sqs = boto3.client("sqs")
    sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps({"jobId": job_id}))
    print("✓ Message sent")

    print(f"\n⏳ Polling job status (timeout {TIMEOUT_SECONDS}s)...")
    print("-" * 50)
    start = time.time()
    last_status = None

    while time.time() - start < TIMEOUT_SECONDS:
        job = db.analysis_jobs.find_by_id(job_id)
        status = job["status"] if job else "missing"
        if status != last_status:
            print(f"[{int(time.time() - start):3d}s] Status: {status}")
            last_status = status

        if status == "completed":
            break
        if status == "failed":
            print(f"❌ Failed: {job.get('error_message')}")
            return 1
        time.sleep(3)
    else:
        print("❌ Timed out waiting for job completion")
        return 1

    print("-" * 50)
    job = db.analysis_jobs.find_by_id(job_id)
    rec = job.get("recommendation_payload") or {}
    summary = rec.get("summary") or job.get("recommendation_payload", {}).get("summary", "")
    print("\n📋 Results")
    print(f"Summary: {str(summary)[:200]}")
    if rec.get("actions"):
        print(f"Actions: {len(rec['actions'])}")
        for action in rec["actions"][:3]:
            print(f"  • {action.get('action')} {action.get('ticker')}")

    print("\n✅ Full test completed successfully!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
