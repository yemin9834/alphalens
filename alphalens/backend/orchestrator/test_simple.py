#!/usr/bin/env python3
"""
Simple test for Orchestrator agent (local, mocked sub-agents).
Creates an analysis_jobs row and processes it via lambda_handler.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)
os.environ["MOCK_LAMBDAS"] = "true"

from alphalens_shared.test_logging import configure_test_logging

configure_test_logging()

from src import Database
from src.schemas import AnalysisJobCreate


def ensure_test_data():
    """Seed demo user only if missing (does not drop existing data)."""
    db = Database()
    if db.users.find_by_clerk_id("test_user_001"):
        print("✓ Test user already exists")
        return

    db_dir = Path(__file__).resolve().parent.parent / "database"
    print("Seeding test data (first run)...")
    result = subprocess.run(
        ["uv", "run", "reset_db.py", "--with-test-data"],
        cwd=db_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        print(
            "\n⚠️  Could not seed test data. Run:\n"
            "   cd alphalens/backend/database && uv run reset_db.py --with-test-data"
        )


def create_test_job() -> str:
    db = Database()
    payload = {
        "riskProfile": "balanced",
        "portfolio": [
            {"ticker": "NVDA", "weight": 35},
            {"ticker": "MSFT", "weight": 25},
            {"ticker": "CASH", "weight": 40},
        ],
        "coreCompany": "NVIDIA",
        "coreTicker": "NVDA",
    }
    return db.analysis_jobs.create_job(
        "test_user_001",
        AnalysisJobCreate(request_payload=payload),
    )


def main():
    print("Testing Orchestrator Agent...")
    print("=" * 60)

    ensure_test_data()
    job_id = create_test_job()
    print(f"Job ID: {job_id}")

    from lambda_handler import lambda_handler

    event = {"Records": [{"body": json.dumps({"jobId": job_id})}]}
    result = lambda_handler(event, None)
    print(f"Status Code: {result['statusCode']}")

    body = json.loads(result["body"])
    print(f"Success: {body.get('success')}")
    if body.get("recommendation"):
        rec = body["recommendation"]
        print(f"Risk level: {rec.get('riskLevel')}")
        print(f"Ranked actions: {len(rec.get('actions', []))}")

    db = Database()
    job = db.analysis_jobs.find_by_id(job_id)
    print(f"DB status: {job.get('status') if job else 'not found'}")

    print("=" * 60)
    return 0 if result["statusCode"] == 200 and body.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
