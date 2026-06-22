# AlphaLens Deployment Guides

Step-by-step guides for deploying AlphaLens on AWS. Each guide maps to one Terraform directory with **independent local state**, matching the Alex project pattern.

## Guide Order

| Guide | Terraform | What you deploy |
|-------|-----------|-----------------|
| [1_permissions.md](./1_permissions.md) | — | IAM + RDS/Bedrock permissions |
| [2_database.md](./2_database.md) | `terraform/1_database/` | Aurora Serverless v2, Data API, Lambda DB role |
| [3_agents.md](./3_agents.md) | `terraform/2_agents/` | 6 agent Lambdas, SQS, orchestration (API runs locally until Guide 5) |
| [4_discovery.md](./4_discovery.md) | `terraform/3_discovery/` | Live discovery with Bedrock/OpenAI + MCP; Aurora persistence (Step 7) |
| [5_frontend.md](./5_frontend.md) | `terraform/4_frontend/` | **`alphalens-api` Lambda**, API Gateway, CloudFront, S3 |

## Reference

- [architecture.md](./architecture.md) — system diagrams and data flow
- [agent_architecture.md](./agent_architecture.md) — multi-agent collaboration, `create_agent()` pattern, persistence
- [../design-doc.md](../design-doc.md) — product requirements

## Backend layout (after Guide 3)

```
alphalens/backend/
├── shared/alphalens_shared/
│   ├── services/              # discovery, validator, analyst, portfolio, pipeline, qa
│   │                          # analyst_narrative, analyst_report, discovery_persist
│   ├── lambda_invoke.py       # Mock routing + Lambda invoke
│   ├── lambda_response.py     # Consistent agent handler responses
│   ├── lambda_logging.py      # CloudWatch + local test logging
│   ├── json_utils.py          # NaN-safe JSON for AWS
│   └── bedrock_agent.py       # LLM helpers (Bedrock or OpenAI via LiteLLM)
├── metrics/alphalens_metrics/ # Deterministic engines — ranking, risk, ActionPlanService (cash funding)
├── database/                  # Aurora Data API client + discovery_persist
├── api/
│   ├── main.py                # FastAPI app (local uvicorn)
│   ├── discovery_stream.py    # NDJSON discover stream
│   ├── pipeline_stream.py     # NDJSON sync analyze stream
│   ├── qa_stream.py           # SSE job Q&A stream
│   ├── package_docker.py      # api_lambda.zip (Guide 5)
│   └── lambda_handler.py      # Mangum handler (Guide 5 AWS deploy)
├── scripts/package_agent_docker.py   # Slim MVP zips
├── deploy_all_lambdas.py
├── test_simple.py             # All agents local
├── test_full.py               # All agents on AWS
├── check_jobs.py
└── {orchestrator,discovery,validator,analyst,portfolio,qa}/
    ├── agent.py               # create_agent() + run()  (Alex pattern)
    ├── templates.py
    ├── lambda_handler.py      # handle_agent_run() wrapper
    ├── package_docker.py      # analyst: slim+narrative; orchestrator/portfolio/qa: full LLM zip
    ├── test_simple.py         # Local; configure_test_logging() shows LLM provider
    └── test_full.py           # AWS invoke; discovery routes to live if URL set
```

## Before you start

1. Complete Alex [Guide 1](../../guides/1_permissions.md) (or AlphaLens [1_permissions.md](./1_permissions.md)) if not already done
2. Copy `terraform/*/terraform.tfvars.example` → `terraform.tfvars` in each module you deploy
3. Copy `alphalens/.env.example` → `alphalens/.env`

## Environment variables by guide

| After guide | Add to `alphalens/.env` |
|-------------|-------------------------|
| 2 Database | `AURORA_CLUSTER_ARN`, `AURORA_SECRET_ARN`, `DATABASE_NAME` |
| 3 Agents | `SQS_QUEUE_URL`, `*_FUNCTION` names; `MOCK_LAMBDAS=true` for fast local agents, `false` to hit AWS Lambdas from local API; optional `USE_LOCAL_PORTFOLIO=true` to run portfolio in-process only |
| 3 Agents (Q&A) | `MOCK_QA=false` (default) — invokes `alphalens-qa` Lambda; `MOCK_QA=true` for offline keyword answers |
| 3 Agents (LLM on AWS) | Also set `use_llm_*`, `llm_provider`, `openai_*` in `terraform/2_agents/terraform.tfvars` |
| 3 Agents (analyst narrative) | `use_llm_analyst_narrative = true` in tfvars → narrative on **`alphalens-analyst`** Lambda (slim `openai` client in zip) |
| 4 Discovery | `DISCOVERY_SERVICE_URL` in `.env`; `discovery_service_url` in `terraform/2_agents`; LLM + Aurora in `terraform/3_discovery` |
| 5 Frontend | `CLERK_JWKS_URL`, `CORS_ORIGINS`, deployed API Gateway / CloudFront URL; optional `DISCOVERY_STREAM_DELAY_MS` for discover UI pacing |

For MVP, keep `use_llm_*` false and use slim packages (`package_agent_docker.py all`). For LLM on zip Lambdas, see [3_agents.md](./3_agents.md) Steps 4.2–4.3. **`.env` LLM settings do not automatically reach Lambda** — mirror them in Terraform.

**Analyst packaging note:** use `cd backend/analyst && uv run package_docker.py` — must print `Verified: openai/ present in analyst slim package`. Includes `openai` for slim narrative, **not** litellm (yfinance + litellm exceeds Lambda size limit).

## Local API before Guide 5

Guide 3 endpoints work locally via `uv run main.py` in `backend/api`. `main.py` loads `alphalens/.env` automatically. The API Lambda (`alphalens-api`) is **code-ready** but **not created in AWS** until you run `package_docker.py` and `terraform apply` in [5_frontend.md](./5_frontend.md) — it is **not** part of `terraform/2_agents`.

Frontend (Guide 5) uses streaming endpoints for discover, sync analyze, and job Q&A — see [5_frontend.md](./5_frontend.md).

## Destroy order (reverse)

```bash
cd terraform/4_frontend && terraform destroy
cd terraform/3_discovery && terraform destroy
cd terraform/2_agents && terraform destroy
cd terraform/1_database && terraform destroy
```

Aurora (`1_database`) is the largest ongoing cost.
