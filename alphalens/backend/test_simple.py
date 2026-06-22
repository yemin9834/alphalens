#!/usr/bin/env python3
"""
Run test_simple.py in each AlphaLens agent directory.
"""

import os
import subprocess
import sys
from pathlib import Path

AGENTS = ["discovery", "validator", "analyst", "portfolio", "orchestrator", "qa"]


def run_agent_test(agent: str) -> bool:
    agent_dir = Path(__file__).parent / agent
    test_file = agent_dir / "test_simple.py"
    if not test_file.exists():
        print(f"  ⚠️  {agent}: no test_simple.py")
        return True

    env = os.environ.copy()
    env["MOCK_LAMBDAS"] = "true"

    result = subprocess.run(
        ["uv", "run", "test_simple.py"],
        cwd=agent_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  ✅ {agent}: passed")
        return True

    print(f"  ❌ {agent}: failed")
    if result.stdout:
        print(result.stdout[-800:])
    if result.stderr:
        print(result.stderr[-400:])
    return False


def main():
    print("=" * 60)
    print("TESTING ALL ALPHALENS AGENTS (local)")
    print("=" * 60)

    results = {agent: run_agent_test(agent) for agent in AGENTS}

    passed = sum(results.values())
    print("\n" + "=" * 60)
    print(f"Passed: {passed}/{len(AGENTS)}")
    print("=" * 60)

    if passed < len(AGENTS):
        print("\n⚠️  SOME TESTS FAILED")
        sys.exit(1)
    print("\n✅ ALL TESTS PASSED!")
    sys.exit(0)


if __name__ == "__main__":
    main()
