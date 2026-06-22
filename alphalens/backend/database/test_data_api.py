#!/usr/bin/env python3
"""Test Aurora Data API connection for AlphaLens."""

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

CLUSTER_ID = "alphalens-aurora-cluster"
DATABASE = os.getenv("DATABASE_NAME") or os.getenv("AURORA_DATABASE", "alphalens")


def get_cluster_details(region: str):
    cluster_arn = os.getenv("AURORA_CLUSTER_ARN")
    secret_arn = os.getenv("AURORA_SECRET_ARN")

    if cluster_arn and secret_arn:
        print("📋 Using configuration from alphalens/.env")
        rds = boto3.client("rds", region_name=region)
        try:
            cluster_id = cluster_arn.split(":")[-1]
            resp = rds.describe_db_clusters(DBClusterIdentifier=cluster_id)
            if resp["DBClusters"] and not resp["DBClusters"][0].get("HttpEndpointEnabled", False):
                print("❌ Data API is not enabled on the cluster")
                return None, None
        except ClientError as e:
            print(f"⚠️  Could not verify cluster: {e}")
        return cluster_arn, secret_arn

    print("⚠️  AURORA_CLUSTER_ARN or AURORA_SECRET_ARN not set in alphalens/.env")
    print("Attempting auto-discovery for alphalens-aurora-cluster...")

    rds = boto3.client("rds", region_name=region)
    secrets = boto3.client("secretsmanager", region_name=region)
    try:
        resp = rds.describe_db_clusters(DBClusterIdentifier=CLUSTER_ID)
        if not resp["DBClusters"]:
            print(f"❌ Cluster '{CLUSTER_ID}' not found")
            return None, None
        cluster = resp["DBClusters"][0]
        if not cluster.get("HttpEndpointEnabled", False):
            print("❌ Data API not enabled")
            return None, None
        cluster_arn = cluster["DBClusterArn"]

        listed = secrets.list_secrets()
        matches = [
            s for s in listed["SecretList"] if "alphalens-aurora-credentials" in s["Name"]
        ]
        if not matches:
            print("❌ No alphalens-aurora-credentials secret found")
            return None, None
        matches.sort(key=lambda x: x.get("CreatedDate", ""), reverse=True)
        secret_arn = matches[0]["ARN"]
        print("\n📝 Add to alphalens/.env:")
        print(f"AURORA_CLUSTER_ARN={cluster_arn}")
        print(f"AURORA_SECRET_ARN={secret_arn}")
        return cluster_arn, secret_arn
    except ClientError as e:
        print(f"❌ Error: {e}")
        return None, None


def test_connection(cluster_arn: str, secret_arn: str, region: str) -> bool:
    client = boto3.client("rds-data", region_name=region)
    print(f"\n🔍 Testing Data API — database: {DATABASE}")
    print("-" * 50)

    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=DATABASE,
            sql="SELECT 1 as test_connection, current_timestamp as server_time",
        )
        if response.get("records"):
            print("   ✅ Connection successful!")
            print(f"   Server time: {response['records'][0][1].get('stringValue')}")
        else:
            print("   ❌ No results returned")
            return False
    except ClientError as e:
        print(f"   ❌ Error: {e.response['Error']['Message']}")
        return False

    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=DATABASE,
            sql="""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' ORDER BY table_name
            """,
        )
        tables = [r[0].get("stringValue") for r in response.get("records", [])]
        if tables:
            print(f"\n   ✅ Found {len(tables)} tables: {', '.join(tables)}")
        else:
            print("\n   ℹ️  No tables yet — run: uv run run_migrations.py")
    except ClientError as e:
        print(f"   ⚠️  Could not list tables: {e}")

    print("\n✅ Data API is working!")
    return True


def main():
    print("🚀 AlphaLens Aurora Data API Connection Test")
    print("=" * 50)
    region = os.getenv("DEFAULT_AWS_REGION", "us-east-1")
    print(f"📍 Region: {region}")

    cluster_arn, secret_arn = get_cluster_details(region)
    if not cluster_arn or not secret_arn:
        sys.exit(1)

    if not test_connection(cluster_arn, secret_arn, region):
        sys.exit(1)


if __name__ == "__main__":
    main()
