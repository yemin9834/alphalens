#!/usr/bin/env python3
"""
Package the Validator Lambda (slim — yfinance market lookup + optional LLM narrative).

Includes openai for slim narrative when USE_LLM_VALIDATOR_NARRATIVE=true (no litellm).
"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent.parent / "scripts" / "package_agent_docker.py"
    sys.exit(subprocess.call(["uv", "run", str(script), "validator"], cwd=Path(__file__).parent))
