"""Analyst Lambda — metrics and opportunity ranking."""

from alphalens_shared.lambda_logging import configure_lambda_logging

configure_lambda_logging()

from agent import run
from alphalens_shared.lambda_response import handle_agent_run


def lambda_handler(event, context):
    return handle_agent_run("alphalens-analyst", event, context, run)
