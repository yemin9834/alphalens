"""Portfolio Lambda — portfolio-aware recommendations."""

from alphalens_shared.lambda_logging import configure_lambda_logging

configure_lambda_logging()

from agent import run
from alphalens_shared.lambda_response import handle_agent_run


def lambda_handler(event, context):
    return handle_agent_run("alphalens-portfolio", event, context, run)
