"""Discovery Lambda — curated ecosystem fallback (live research in Guide 4)."""

from agent import run
from alphalens_shared.lambda_response import handle_agent_run


def lambda_handler(event, context):
    return handle_agent_run("alphalens-discovery", event, context, run)
