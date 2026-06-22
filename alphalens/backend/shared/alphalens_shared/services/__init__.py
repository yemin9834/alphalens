"""Deterministic agent services used by Lambdas and API.

Import from submodules directly to avoid loading heavy deps in slim Lambdas:
  from alphalens_shared.services.discovery import run_discovery
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "run_analyst",
    "run_discovery",
    "run_analysis_pipeline",
    "run_portfolio",
    "run_validator",
]


def __getattr__(name: str) -> Any:
    if name == "run_analyst":
        from .analyst import run_analyst

        return run_analyst
    if name == "run_discovery":
        from .discovery import run_discovery

        return run_discovery
    if name == "run_analysis_pipeline":
        from .pipeline import run_analysis_pipeline

        return run_analysis_pipeline
    if name == "run_portfolio":
        from .portfolio import run_portfolio

        return run_portfolio
    if name == "run_validator":
        from .validator import run_validator

        return run_validator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
