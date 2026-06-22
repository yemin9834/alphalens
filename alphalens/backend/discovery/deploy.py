#!/usr/bin/env python3
"""
Deploy live discovery service (LLM + MCP) to AWS Lambda container.

Build context: alphalens/backend (workspace with shared + discovery).
Terraform: alphalens/terraform/3_discovery
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, capture_output=False, cwd=None):
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=True,
            cwd=cwd,
        )
        if capture_output:
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        sys.exit(1)


def terraform_apply(terraform_dir: Path, targets: list[str] | None = None):
    command = ["terraform", "apply", "-auto-approve"]
    for target in targets or []:
        command.extend(["-target", target])
    run_command(command, cwd=terraform_dir)


def terraform_output(terraform_dir: Path, output_name: str) -> str:
    return run_command(
        ["terraform", "output", "-raw", output_name],
        capture_output=True,
        cwd=terraform_dir,
    )


def get_paths() -> tuple[Path, Path, Path]:
    """Resolve alphalens paths from alex repo root or alphalens checkout."""
    here = Path(__file__).resolve().parent
    backend_dir = here.parent
    alphalens_root = backend_dir.parent

    if (alphalens_root / "terraform" / "3_discovery").is_dir():
        terraform_dir = alphalens_root / "terraform" / "3_discovery"
    else:
        repo_root = Path(
            run_command(["git", "rev-parse", "--show-toplevel"], capture_output=True)
        )
        terraform_dir = repo_root / "alphalens" / "terraform" / "3_discovery"
        backend_dir = repo_root / "alphalens" / "backend"

    return backend_dir, terraform_dir, here


def write_image_override(terraform_dir: Path, image_uri: str):
    override_path = terraform_dir / "discovery.auto.tfvars.json"
    override_path.write_text(
        json.dumps({"discovery_image_uri": image_uri}, indent=2) + "\n"
    )


def wait_for_lambda_active(region: str, function_name: str):
    print("\nWaiting for Lambda update to complete...")
    for _ in range(60):
        status = run_command(
            [
                "aws",
                "lambda",
                "get-function",
                "--function-name",
                function_name,
                "--region",
                region,
                "--query",
                "Configuration.LastUpdateStatus",
                "--output",
                "text",
            ],
            capture_output=True,
        ).strip()
        state = run_command(
            [
                "aws",
                "lambda",
                "get-function",
                "--function-name",
                function_name,
                "--region",
                region,
                "--query",
                "Configuration.State",
                "--output",
                "text",
            ],
            capture_output=True,
        ).strip()

        if status == "Successful" and state == "Active":
            print("Lambda is active.")
            return
        if status == "Failed":
            print("Lambda update failed. Check AWS Console or CloudWatch logs.")
            sys.exit(1)

        print(".", end="", flush=True)
        time.sleep(5)

    print("\nLambda update is taking longer than expected.")


def main():
    from dotenv import load_dotenv

    load_dotenv(override=True)

    print("AlphaLens Discovery Service - Lambda Deployment")
    print("=" * 50)

    region = os.environ.get("DEFAULT_AWS_REGION") or os.environ.get("AWS_REGION")
    if not region:
        print("Error: DEFAULT_AWS_REGION not found in your .env file.")
        sys.exit(1)

    backend_dir, terraform_dir, discovery_dir = get_paths()

    print("\nGetting AWS account details...")
    account_id = run_command(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        capture_output=True,
    )
    print(f"AWS Account: {account_id}")
    print(f"Region: {region}")

    print("\nEnsuring Terraform ECR prerequisites exist...")
    terraform_apply(
        terraform_dir,
        targets=[
            "aws_ecr_repository.discovery",
            "aws_ecr_repository_policy.discovery_lambda_access",
        ],
    )

    ecr_url = terraform_output(terraform_dir, "ecr_repository_url")
    if not ecr_url:
        print("Error: ECR repository not found.")
        sys.exit(1)
    print(f"ECR Repository: {ecr_url}")

    print("\nLogging in to ECR...")
    password = run_command(
        ["aws", "ecr", "get-login-password", "--region", region],
        capture_output=True,
    )
    login_process = subprocess.Popen(
        ["docker", "login", "--username", "AWS", "--password-stdin", ecr_url],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _, stderr = login_process.communicate(input=password)
    if login_process.returncode != 0:
        print(f"Error logging into ECR: {stderr}")
        sys.exit(1)
    print("Login successful.")

    image_tag = f"deploy-{int(time.time())}"
    local_image = f"alphalens-discovery:{image_tag}"
    remote_image = f"{ecr_url}:{image_tag}"

    print(f"\nBuilding Docker image for linux/amd64 with tag: {image_tag}")
    run_command(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "--provenance=false",
            "--sbom=false",
            "-f",
            "discovery/Dockerfile",
            "-t",
            local_image,
            ".",
        ],
        cwd=backend_dir,
    )

    print("\nTagging image for ECR...")
    run_command(["docker", "tag", local_image, remote_image])

    print("\nPushing image to ECR...")
    run_command(["docker", "push", remote_image])
    print("Docker image pushed successfully.")

    print("\nApplying Terraform with the new image...")
    write_image_override(terraform_dir, remote_image)
    terraform_apply(terraform_dir)

    function_name = terraform_output(terraform_dir, "discovery_function_name")
    service_url = terraform_output(terraform_dir, "discovery_service_url")

    wait_for_lambda_active(region, function_name)

    print("\nYour discovery service is available at:")
    print(f"   {service_url}")
    print("\nAdd to alphalens/.env:")
    print(f"   DISCOVERY_SERVICE_URL={service_url.rstrip('/')}")
    print("\nRe-apply terraform/2_agents with discovery_service_url set, or update")
    print("the orchestrator Lambda DISCOVERY_SERVICE_URL in the AWS console.")
    print("\nTest:")
    print(f"   curl {service_url.rstrip('/')}/health")


if __name__ == "__main__":
    main()
