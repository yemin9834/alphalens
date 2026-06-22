#!/usr/bin/env python3
"""Full test for Validator agent via deployed Lambda."""

import json
import os

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

FUNCTION_NAME = os.getenv("VALIDATOR_FUNCTION", "alphalens-validator")


def main():
    print("Testing Validator Lambda")
    print("=" * 60)

    payload = {
        "candidates": [
            {
                "companyName": "Microsoft",
                "ticker": "MSFT",
                "relationshipType": "partner",
                "relationshipSummary": "Azure GPU partnership",
                "confidence": "High",
                "evidenceUrl": "demo",
            }
        ]
    }

    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    result = json.loads(response["Payload"].read())
    print(json.dumps(result, indent=2))

    if isinstance(result, dict) and result.get("statusCode") == 200:
        body = json.loads(result["body"])
        print(f"\n✅ Validator OK — {len(body.get('validatedCandidates', []))} candidates")
        return 0

    print("\n❌ Validator test failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
