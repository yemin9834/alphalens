#!/usr/bin/env python3
"""
Deploy all AlphaLens agent Lambda functions via Terraform.

Usage:
    cd alphalens/backend
    uv run deploy_all_lambdas.py [--package]
"""

import subprocess
import sys
from pathlib import Path

import boto3

AGENTS = ["orchestrator", "validator", "analyst", "portfolio", "discovery", "qa"]
TERRAFORM_DIR = Path(__file__).resolve().parent.parent / "terraform" / "2_agents"
BACKEND_DIR = Path(__file__).resolve().parent


def package_agent(name: str) -> bool:
    script = BACKEND_DIR / "scripts" / "package_agent_docker.py"
    result = subprocess.run(
        ["uv", "run", str(script), name],
        cwd=BACKEND_DIR / "scripts",
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        return False
    zip_path = BACKEND_DIR / name / f"{name}_lambda.zip"
    if zip_path.exists():
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"   ✓ {name}: {size_mb:.1f} MB")
        return True
    return False


def taint_and_apply() -> bool:
    for agent in AGENTS:
        resource = f"aws_lambda_function.{agent}"
        subprocess.run(
            ["terraform", "taint", resource],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
        )

    result = subprocess.run(
        ["terraform", "apply", "-auto-approve"],
        cwd=TERRAFORM_DIR,
    )
    return result.returncode == 0


def main():
    force_package = "--package" in sys.argv

    print("🎯 Deploying AlphaLens Agent Lambdas (via Terraform)")
    print("=" * 50)

    try:
        sts = boto3.client("sts")
        print(f"AWS Account: {sts.get_caller_identity()['Account']}")
        print(f"AWS Region: {boto3.Session().region_name}")
    except Exception as exc:
        print(f"❌ AWS credentials error: {exc}")
        sys.exit(1)

    if not TERRAFORM_DIR.exists():
        print(f"❌ Terraform dir not found: {TERRAFORM_DIR}")
        sys.exit(1)

    print("\n📋 Checking packages...")
    to_package = []
    for name in AGENTS:
        zip_path = BACKEND_DIR / name / f"{name}_lambda.zip"
        if force_package or not zip_path.exists():
            to_package.append(name)
            print(f"   ⟳ {name}: will package")
        else:
            size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"   ✓ {name}: {size_mb:.1f} MB")

    if to_package:
        print("\n📦 Packaging (Docker required)...")
        for name in to_package:
            print(f"Packaging {name}...")
            if not package_agent(name):
                print(f"❌ Failed to package {name}")
                sys.exit(1)

    print("\n🚀 Terraform apply (taint + deploy)...")
    if taint_and_apply():
        print("\n🎉 All Lambda functions deployed!")
        print("\nNext steps:")
        print("   cd alphalens/backend && uv run test_full.py")
        sys.exit(0)

    print("\n❌ Terraform apply failed")
    sys.exit(1)


if __name__ == "__main__":
    main()
