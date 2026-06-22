"""
Validator agent — deterministic ticker checks + optional LLM validation narrative.

Status (validated / unknown / invalid) always comes from code + yfinance.
LLM only adds validationNote text when USE_LLM_VALIDATOR_NARRATIVE=true.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from alphalens_shared.services.validator import run_validator, validate_candidate
from alphalens_shared.services.validator_narrative import maybe_enrich_validator_narrative

from templates import VALIDATOR_INSTRUCTIONS

AGENT_NAME = "Validator"
INSTRUCTIONS = VALIDATOR_INSTRUCTIONS

USE_LLM_VALIDATOR_NARRATIVE = (
    os.getenv("USE_LLM_VALIDATOR_NARRATIVE", "false").lower() == "true"
)


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    from alphalens_shared.bedrock_agent import log_agent_mode

    log_agent_mode(AGENT_NAME, llm=USE_LLM_VALIDATOR_NARRATIVE)
    result = run_validator(payload)
    return maybe_enrich_validator_narrative(payload, result)


def create_agent(*_args: Any, **_kwargs: Any):
    raise NotImplementedError(
        "Validator uses run(payload). Optional LLM narrative is enabled with "
        "USE_LLM_VALIDATOR_NARRATIVE."
    )


def validate_all(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = run({"candidates": candidates})
    return result.get("validatedCandidates", [])


__all__ = [
    "AGENT_NAME",
    "INSTRUCTIONS",
    "create_agent",
    "run",
    "validate_all",
    "validate_candidate",
]
