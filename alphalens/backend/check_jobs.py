#!/usr/bin/env python3
"""List recent analysis_jobs from Aurora."""

import json
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(override=True)

from src import Database


def fmt_time(value) -> str:
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)[:16]


def main():
    db = Database()
    jobs = db.analysis_jobs.find_by_user("test_user_001", limit=10)

    if not jobs:
        jobs = db.query_raw(
            "SELECT * FROM analysis_jobs ORDER BY created_at DESC LIMIT 10"
        )

    print("=" * 70)
    print("RECENT ANALYSIS JOBS")
    print("=" * 70)

    if not jobs:
        print("No jobs found.")
        return

    for job in jobs:
        print(f"\nJob: {job['id']}")
        print(f"  Status:    {job.get('status')}")
        print(f"  User:      {job.get('clerk_user_id')}")
        print(f"  Created:   {fmt_time(job.get('created_at'))}")
        print(f"  Completed: {fmt_time(job.get('completed_at'))}")
        if job.get("error_message"):
            print(f"  Error:     {job['error_message']}")

        rec = job.get("recommendation_payload")
        if rec:
            if isinstance(rec, str):
                rec = json.loads(rec)
            summary = rec.get("summary", "")
            actions = rec.get("actions", [])
            print(f"  Summary:   {summary[:100]}...")
            print(f"  Actions:   {len(actions)}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
