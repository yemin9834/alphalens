"""Validator Lambda — ticker validation for discovery candidates."""

from agent import run
from alphalens_shared.lambda_response import handle_agent_run


def lambda_handler(event, context):
    return handle_agent_run("alphalens-validator", event, context, run)
