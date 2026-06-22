#!/usr/bin/env python3
"""
Reset AlphaLens database: drop tables, re-run migrations, optional test data.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from src.demo_data import populate_demo_data
from src.client import DataAPIClient
from src.models import Database


def drop_all_tables(db: DataAPIClient) -> None:
    print("🗑️  Dropping existing tables...")
    for table in [
        "candidates",
        "analysis_jobs",
        "discovery_runs",
        "holdings",
        "portfolios",
        "users",
    ]:
        try:
            db.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print(f"   ✅ Dropped {table}")
        except Exception as e:
            print(f"   ⚠️  {table}: {e}")

    try:
        db.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE")
        print("   ✅ Dropped update_updated_at_column")
    except Exception as e:
        print(f"   ⚠️  function: {e}")


def create_test_data(db: Database) -> None:
    print("\n👤 Creating test user and portfolio (design-doc demo)...")
    result = populate_demo_data(db, "test_user_001")
    portfolio = result["portfolio"]
    print("   ✅ Demo user and portfolio loaded")
    print(f"   ✅ Holdings: {len(portfolio.get('holdings', []))} positions")
    print(
        f"   ✅ Discovery run {result.get('discoveryRunId')} "
        f"with {result.get('candidatesLoaded', 0)} candidates"
    )


def main():
    parser = argparse.ArgumentParser(description="Reset AlphaLens database")
    parser.add_argument(
        "--with-test-data",
        action="store_true",
        help="Create demo user, portfolio, and NVIDIA discovery run",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Only drop tables (do not re-run migrations)",
    )
    args = parser.parse_args()

    db_client = DataAPIClient()
    db = Database()

    drop_all_tables(db_client)

    if not args.skip_migrations:
        print("\n📦 Re-running migrations...")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "run_migrations.py")],
            check=False,
        )
        if result.returncode != 0:
            sys.exit(result.returncode)

    if args.with_test_data:
        create_test_data(db)

    print("\n✅ Database reset complete!")


if __name__ == "__main__":
    main()
