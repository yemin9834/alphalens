#!/bin/bash
# Boot FastAPI via uvicorn — used with AWS Lambda Web Adapter (response_stream mode).
cd "${LAMBDA_TASK_ROOT:-.}"
export PYTHONPATH="${LAMBDA_TASK_ROOT}:${PYTHONPATH:-}"
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
