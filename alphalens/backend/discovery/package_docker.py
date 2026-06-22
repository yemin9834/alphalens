#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent.parent / "scripts" / "package_agent_docker.py"
    sys.exit(subprocess.call(["uv", "run", str(script), "discovery"], cwd=Path(__file__).parent))
