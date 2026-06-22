# AGENTS.md — AlphaLens

Guidance for AI coding assistants working on AlphaLens inside the Alex monorepo.

## Project

AlphaLens is an AI-powered portfolio decision-support agent: ecosystem stock pool discovery → metric analysis → opportunity ranking → portfolio-aware action recommendations. It does **not** execute trades or guarantee returns.

**Product spec:** [design-doc.md](./design-doc.md)  
**Architecture:** [architecture.md](./architecture.md)  
**Implementation rules:** [CLAUDE.md](./CLAUDE.md)

## Tech Stack

- Backend: Python 3.12, **uv**, FastAPI, OpenAI Agents SDK, LiteLLM, Bedrock
- Frontend: Next.js, TypeScript, Clerk
- Infra: Terraform (independent modules), Lambda, SQS, Aurora, App Runner (discovery)
- Data: yfinance, Alpha Vantage, Brave/Tavily, curated JSON fallbacks

## Key Locations

```text
backend/api/              FastAPI routes
backend/orchestrator/     SQS workflow coordinator
backend/discovery/        Ecosystem discovery agent + MCP
backend/validator/        Ticker validation agent
backend/analyst/            Ranking / metrics agent
backend/portfolio/        Portfolio advisor agent
backend/metrics/          Deterministic engines (no LLM)
backend/shared/           Schemas, MCP factories, static data
backend/database/         Aurora Data API library
frontend/pages/           Next.js pages
frontend/lib/             API client, types
terraform/                IaC modules
guides/                   Deployment guides
```

## Rules

- Use **uv** for all Python (`uv add`, `uv run`) — never raw `pip` or `python`
- Never invent financial metrics; missing → `Unknown` / `Data unavailable`
- Do not auto-edit `backend/shared/prompts/` or curated JSON in `backend/shared/data/`
- Bedrock via LiteLLM requires `AWS_REGION_NAME` env var
- One agent = structured output **or** tools/MCP, not both (LiteLLM + Bedrock limit)

## Before Deploying

1. Copy `terraform/*/terraform.tfvars.example` → `terraform.tfvars` per module
2. Copy `.env.example` → `.env`
3. Docker required for `package_docker.py` (Lambda linux/amd64)

## Parent Project

AlphaLens lives under the Alex repo. AWS permissions from Alex Guide 1 apply. Reuse patterns from `alex/backend/planner/`, `alex/backend/researcher/`, and `alex/terraform/`.
