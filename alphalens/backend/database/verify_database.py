#!/usr/bin/env python3
"""Verify AlphaLens database schema and optional test data."""

import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(override=True)
_env = Path(__file__).resolve().parent.parent.parent / ".env"
if _env.exists():
    load_dotenv(_env, override=True)

cluster_arn = os.environ.get("AURORA_CLUSTER_ARN")
secret_arn = os.environ.get("AURORA_SECRET_ARN")
database = os.environ.get("DATABASE_NAME") or os.environ.get("AURORA_DATABASE", "alphalens")
region = os.environ.get("DEFAULT_AWS_REGION", "us-east-1")

EXPECTED_TABLES = {
    "users",
    "portfolios",
    "holdings",
    "discovery_runs",
    "candidates",
    "analysis_jobs",
}

if not cluster_arn or not secret_arn:
    print("❌ Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN in alphalens/.env")
    sys.exit(1)

client = boto3.client("rds-data", region_name=region)


def query(sql: str, description: str):
    print(f"\n{description}")
    print("-" * 50)
    try:
        return client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql=sql,
        )
    except ClientError as e:
        print(f"❌ {e.response['Error']['Message']}")
        return None


def main():
    print("🔍 ALPHALENS DATABASE VERIFICATION")
    print("=" * 70)
    print(f"📍 Region: {region}")
    print(f"📦 Database: {database}")

    response = query(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        "📊 TABLES",
    )

    found = set()
    if response and response.get("records"):
        for record in response["records"]:
            name = record[0]["stringValue"]
            found.add(name)
            print(f"   • {name}")

    missing = EXPECTED_TABLES - found
    if missing:
        print(f"\n❌ Missing tables: {', '.join(sorted(missing))}")
        print("   Run: uv run run_migrations.py")
        sys.exit(1)

    print(f"\n✅ All {len(EXPECTED_TABLES)} expected tables exist")

    response = query(
        """
        SELECT 'users' AS t, COUNT(*)::int AS c FROM users
        UNION ALL SELECT 'portfolios', COUNT(*)::int FROM portfolios
        UNION ALL SELECT 'holdings', COUNT(*)::int FROM holdings
        UNION ALL SELECT 'discovery_runs', COUNT(*)::int FROM discovery_runs
        UNION ALL SELECT 'candidates', COUNT(*)::int FROM candidates
        UNION ALL SELECT 'analysis_jobs', COUNT(*)::int FROM analysis_jobs
        ORDER BY t
        """,
        "📈 RECORD COUNTS",
    )

    if response and response.get("records"):
        for record in response["records"]:
            print(f"   {record[0]['stringValue']:<18} {record[1].get('longValue', 0)}")

    response = query(
        """
        SELECT u.clerk_user_id, u.risk_profile, p.name, COUNT(h.id) AS holdings
        FROM users u
        LEFT JOIN portfolios p ON p.clerk_user_id = u.clerk_user_id AND p.is_default = TRUE
        LEFT JOIN holdings h ON h.portfolio_id = p.id
        GROUP BY u.clerk_user_id, u.risk_profile, p.name
        LIMIT 5
        """,
        "👤 SAMPLE USERS",
    )

    if response and response.get("records"):
        for record in response["records"]:
            print(
                f"   {record[0]['stringValue']} | {record[1]['stringValue']} | "
                f"{record[2].get('stringValue', '—')} | {record[3].get('longValue', 0)} holdings"
            )
    else:
        print("   (no users — run: uv run reset_db.py --with-test-data)")

    print("\n" + "=" * 70)
    print("🎉 DATABASE VERIFICATION COMPLETE")
    print("✅ Schema ready for AlphaLens agents and API")


if __name__ == "__main__":
    main()
