#!/usr/bin/env python3
"""
Run test_full.py for each deployed agent, then orchestrator SQS end-to-end test.

Discovery: live (alphalens-discovery-live) when DISCOVERY_SERVICE_URL is in .env,
otherwise slim curated alphalens-discovery Lambda. See discovery/test_service.py.
"""

import subprocess
import sys
from pathlib import Path

AGENTS = ["discovery", "validator", "analyst", "portfolio", "qa"]


def run_test(agent_dir: Path, test_file: str) -> bool:
    result = subprocess.run(
        ["uv", "run", test_file],
        cwd=agent_dir,
        capture_output=False,
        text=True,
    )
    return result.returncode == 0


def main():
    print("=" * 60)
    print("TESTING ALL ALPHALENS AGENTS (AWS Lambda)")
    print("=" * 60)

    backend = Path(__file__).parent
    failed = []

    for agent in AGENTS:
        print(f"\n{agent.upper()}:")
        if not run_test(backend / agent, "test_full.py"):
            failed.append(agent)

    print("\nORCHESTRATOR (SQS end-to-end):")
    if not run_test(backend / "orchestrator", "test_full.py"):
        failed.append("orchestrator")

    print("\n" + "=" * 60)
    if failed:
        print(f"❌ Failed: {', '.join(failed)}")
        sys.exit(1)
    print("✅ ALL FULL TESTS PASSED!")
    sys.exit(0)


if __name__ == "__main__":
    main()
