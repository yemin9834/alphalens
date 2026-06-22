"""Orchestrator prompt templates — used when Bedrock planning is enabled (Guide 4+)."""

from __future__ import annotations

import json
from typing import Any, Dict

ORCHESTRATOR_INSTRUCTIONS = """
You are the AlphaLens orchestrator. Coordinate ecosystem discovery, validation,
opportunity ranking, and portfolio recommendations by calling the specialist tools.

Rules:
- Call tools in order: discovery (if needed) → validator → analyst → portfolio
- Never invent market data — tools return metrics and rankings
- If a tool fails, stop and report the error clearly
- Discovery produces candidates only; portfolio tool produces final recommendations
"""


def create_orchestrator_task(request: Dict[str, Any]) -> str:
    """Build the orchestrator task from an analysis request payload."""
    return f"""
Run a full AlphaLens analysis for this request:

{json.dumps(request, indent=2)}

Steps:
1. If candidates are missing, call run_discovery with the core company/ticker
2. Call run_validator on the candidate list
3. Call run_analyst with validated candidates and risk profile
4. Call run_portfolio with portfolio holdings and analyst output

Return a brief completion summary when all steps succeed.
""".strip()
