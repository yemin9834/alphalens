"""
Run AlphaLens API locally for development.

Usage:
    cd alphalens/scripts
    uv run run_local.py
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "backend" / "api"


def main():
    print("Starting AlphaLens API at http://localhost:8000")
    subprocess.run(
        ["uv", "run", "uvicorn", "main:app", "--reload", "--port", "8000"],
        cwd=API_DIR,
        check=False,
    )


if __name__ == "__main__":
    main()
