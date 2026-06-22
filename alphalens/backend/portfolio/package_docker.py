#!/usr/bin/env python3
"""
Package the Portfolio Lambda (slim — metrics + deterministic plan + optional LLM narrative).

Includes openai for slim narrative when USE_LLM_PORTFOLIO_NARRATIVE=true (no litellm).
"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent.parent / "scripts" / "package_agent_docker.py"
    sys.exit(subprocess.call(["uv", "run", str(script), "portfolio"], cwd=Path(__file__).parent))
