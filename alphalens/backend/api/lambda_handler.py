"""AWS Lambda entry point for AlphaLens API (Guide 4 frontend)."""

from pathlib import Path

from dotenv import load_dotenv
from mangum import Mangum

_root_env = Path(__file__).resolve().parents[2] / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=True)
load_dotenv(override=True)

from main import app

# Production Lambda uses run.sh + Lambda Web Adapter (RESPONSE_STREAM). Mangum buffers SSE.
handler = Mangum(app, lifespan="off")
