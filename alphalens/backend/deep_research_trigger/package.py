#!/usr/bin/env python3
"""Build slim zip for alphalens-deep-research-trigger Lambda (stdlib only)."""

from __future__ import annotations

import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "deep_research_trigger_lambda.zip"


def main() -> None:
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(HERE / "lambda_handler.py", "lambda_handler.py")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
