"""Logging setup for Lambda and local test scripts."""

from __future__ import annotations

import logging
import os


def _log_level() -> int:
    level_name = os.getenv("ALPHALENS_LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def configure_lambda_logging() -> None:
    """
    Ensure agent INFO logs reach CloudWatch on Lambda.

    Without this, Python's default root level (WARNING) hides
    alphalens_shared.bedrock_agent provider/model lines.
    """
    root = logging.getLogger()
    root.setLevel(_log_level())
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        root.addHandler(handler)


def configure_test_logging() -> None:
    """Show agent mode / LLM logs when running test_simple.py locally."""
    logging.basicConfig(
        level=_log_level(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )
