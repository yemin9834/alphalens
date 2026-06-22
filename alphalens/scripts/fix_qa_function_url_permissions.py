#!/usr/bin/env python3
"""
Ensure alphalens-qa Function URL allows public HTTP access.

AWS now requires BOTH:
  - lambda:InvokeFunctionUrl (auth type NONE)
  - lambda:InvokeFunction with lambda:InvokedViaFunctionUrl=true

Run after terraform/2_agents apply if Q&A returns HTTP 403 from alphalens-api.

  cd alphalens/scripts
  uv run fix_qa_function_url_permissions.py
"""

from __future__ import annotations

import json
import os
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

FUNCTION_NAME = "alphalens-qa"
DEFAULT_REGION = (
    os.getenv("DEFAULT_AWS_REGION")
    or os.getenv("AWS_REGION")
    or os.getenv("AWS_DEFAULT_REGION")
    or "us-east-1"
)


def _policy_has_sid(policy: dict, sid: str) -> bool:
    for stmt in policy.get("Statement", []):
        if stmt.get("Sid") == sid:
            return True
    return False


def main() -> None:
    print(f"Region: {DEFAULT_REGION}  Function: {FUNCTION_NAME}")
    client = boto3.client("lambda", region_name=DEFAULT_REGION)

    try:
        url_cfg = client.get_function_url_config(FunctionName=FUNCTION_NAME)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        message = exc.response.get("Error", {}).get("Message", str(exc))
        if code == "ResourceNotFoundException":
            print(
                f"Error: no Function URL on {FUNCTION_NAME} in {DEFAULT_REGION}.\n"
                "Run: cd alphalens/terraform/2_agents && terraform apply"
            )
        else:
            print(f"AWS error ({code}): {message}")
        sys.exit(1)
    except BotoCoreError as exc:
        print(f"Network/AWS SDK error: {exc}\nCheck internet, VPN, and aws configure region.")
        sys.exit(1)

    print(f"Function URL: {url_cfg.get('FunctionUrl')}")
    print(f"Auth: {url_cfg.get('AuthType')}  InvokeMode: {url_cfg.get('InvokeMode')}")

    try:
        raw = client.get_policy(FunctionName=FUNCTION_NAME)["Policy"]
        policy = json.loads(raw)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        policy = {"Statement": []}

    grants = [
        {
            "sid": "AllowPublicQaFunctionUrlInvoke",
            "action": "lambda:InvokeFunctionUrl",
            "kwargs": {"FunctionUrlAuthType": "NONE"},
        },
        {
            "sid": "AllowPublicQaInvokeViaFunctionUrl",
            "action": "lambda:InvokeFunction",
            "kwargs": {"InvokedViaFunctionUrl": True},
        },
    ]

    for grant in grants:
        if _policy_has_sid(policy, grant["sid"]):
            print(f"OK: {grant['sid']} already present")
            continue
        try:
            client.add_permission(
                FunctionName=FUNCTION_NAME,
                StatementId=grant["sid"],
                Action=grant["action"],
                Principal="*",
                **grant["kwargs"],
            )
            print(f"Added: {grant['sid']}")
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceConflictException":
                print(f"OK: {grant['sid']} already exists")
            else:
                raise

    print("\nTest (replace job id and clerk user id):")
    print(
        f'  curl -N -X POST "{url_cfg["FunctionUrl"].rstrip("/")}/ask/stream" '
        '-H "Content-Type: application/json" '
        '-d \'{"jobId":"<JOB_ID>","question":"test","clerk_user_id":"<USER_ID>"}\''
    )


if __name__ == "__main__":
    main()
