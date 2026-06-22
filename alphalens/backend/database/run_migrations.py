#!/usr/bin/env python3
"""Run AlphaLens database migrations via RDS Data API."""

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

if not cluster_arn or not secret_arn:
    print("❌ Missing AURORA_CLUSTER_ARN or AURORA_SECRET_ARN in alphalens/.env")
    sys.exit(1)

client = boto3.client("rds-data", region_name=region)

STATEMENTS = [
    'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"',
    """CREATE TABLE IF NOT EXISTS users (
        clerk_user_id VARCHAR(255) PRIMARY KEY,
        display_name VARCHAR(255),
        risk_profile VARCHAR(50) DEFAULT 'balanced',
        investment_horizon VARCHAR(50) DEFAULT 'medium-term',
        acceptable_loss_pct DECIMAL(5,2),
        target_return DECIMAL(5,2),
        strategy_profile VARCHAR(100) DEFAULT 'default-risk-based',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS portfolios (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        clerk_user_id VARCHAR(255) NOT NULL REFERENCES users(clerk_user_id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL DEFAULT 'Default Portfolio',
        cash_weight DECIMAL(6,2) DEFAULT 0,
        is_default BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS holdings (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
        ticker VARCHAR(20) NOT NULL,
        weight DECIMAL(6,2) NOT NULL,
        cost_basis DECIMAL(12,4),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(portfolio_id, ticker)
    )""",
    """CREATE TABLE IF NOT EXISTS discovery_runs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        clerk_user_id VARCHAR(255) NOT NULL REFERENCES users(clerk_user_id) ON DELETE CASCADE,
        core_company VARCHAR(255) NOT NULL,
        core_ticker VARCHAR(20) NOT NULL,
        scope VARCHAR(50) DEFAULT 'level-1',
        status VARCHAR(20) DEFAULT 'pending',
        result_payload JSONB,
        warnings JSONB DEFAULT '[]',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        completed_at TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS candidates (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        discovery_run_id UUID NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
        company_name VARCHAR(255) NOT NULL,
        ticker VARCHAR(20),
        relationship_type VARCHAR(50),
        relationship_summary TEXT,
        confidence VARCHAR(20),
        evidence_url TEXT,
        ticker_validation VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS analysis_jobs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        clerk_user_id VARCHAR(255) NOT NULL REFERENCES users(clerk_user_id) ON DELETE CASCADE,
        discovery_run_id UUID REFERENCES discovery_runs(id) ON DELETE SET NULL,
        status VARCHAR(20) DEFAULT 'pending',
        strategy_profile VARCHAR(100) DEFAULT 'default-risk-based',
        request_payload JSONB,
        ranked_payload JSONB,
        recommendation_payload JSONB,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(clerk_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id)",
    "CREATE INDEX IF NOT EXISTS idx_discovery_runs_user ON discovery_runs(clerk_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_discovery_runs_status ON discovery_runs(status)",
    "CREATE INDEX IF NOT EXISTS idx_candidates_run ON candidates(discovery_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_analysis_jobs_user ON analysis_jobs(clerk_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status ON analysis_jobs(status)",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS deep_research JSONB",
    "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS research_status VARCHAR(20) DEFAULT 'pending'",
    "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS research_progress JSONB DEFAULT '{}'::jsonb",
    """CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql""",
    """CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
    """CREATE TRIGGER update_portfolios_updated_at BEFORE UPDATE ON portfolios
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
    """CREATE TRIGGER update_holdings_updated_at BEFORE UPDATE ON holdings
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
    """CREATE TRIGGER update_discovery_runs_updated_at BEFORE UPDATE ON discovery_runs
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
    """CREATE TRIGGER update_analysis_jobs_updated_at BEFORE UPDATE ON analysis_jobs
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
]


def main():
    print("🚀 Running AlphaLens database migrations...")
    print(f"   Database: {database}")
    print("=" * 50)

    success = 0
    errors = 0

    for i, stmt in enumerate(STATEMENTS, 1):
        stmt_type = "statement"
        upper = stmt.upper()
        if "CREATE TABLE" in upper:
            stmt_type = "table"
        elif "CREATE INDEX" in upper:
            stmt_type = "index"
        elif "CREATE TRIGGER" in upper:
            stmt_type = "trigger"
        elif "CREATE FUNCTION" in upper or "CREATE OR REPLACE FUNCTION" in upper:
            stmt_type = "function"
        elif "CREATE EXTENSION" in upper:
            stmt_type = "extension"

        preview = next(line for line in stmt.split("\n") if line.strip())[:60]
        print(f"\n[{i}/{len(STATEMENTS)}] Creating {stmt_type}...")
        print(f"    {preview}...")

        try:
            client.execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database=database,
                sql=stmt,
            )
            print("    ✅ Success")
            success += 1
        except ClientError as e:
            msg = e.response["Error"]["Message"]
            if "already exists" in msg.lower():
                print("    ⚠️  Already exists (skipping)")
                success += 1
            else:
                print(f"    ❌ Error: {msg[:120]}")
                errors += 1

    print("\n" + "=" * 50)
    print(f"Migration complete: {success} successful, {errors} errors")

    if errors == 0:
        print("\n✅ All migrations completed successfully!")
        print("\n📝 Next steps:")
        print("  uv run verify_database.py")
        print("  uv run reset_db.py --with-test-data")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
