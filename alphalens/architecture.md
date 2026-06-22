# AlphaLens Architecture

AI-powered portfolio decision-support platform: ecosystem stock pool discovery, deterministic market metrics, opportunity ranking, and portfolio-aware recommendations.

See [design-doc.md](./design-doc.md) for product requirements and [guides/architecture.md](./guides/architecture.md) for deployment diagrams.

## Directory Structure

```text
alphalens/
├── backend/          # Python agents, API, metrics, database library
├── frontend/         # Next.js + Clerk UI
├── guides/           # Step-by-step deployment guides
├── terraform/        # Independent Terraform modules
└── scripts/          # Local dev and deploy helpers
```

## Agent Pipeline

```text
User → API → SQS → Orchestrator
  → Discovery (MCP: Playwright, Search)
  → Validator (structured output)
  → Analyst (metrics tools + ranking)
  → Portfolio Advisor (structured JSON + action plan)
```

## Core Rule

Agents orchestrate and explain. **Metrics and rankings come from deterministic tools** — never from LLM inference. Missing data → `Unknown` or `Data unavailable`.

## Tech Stack

- **Agents:** OpenAI Agents SDK + LiteLLM + AWS Bedrock (Nova Pro)
- **API:** FastAPI + Mangum on Lambda
- **Database:** Aurora Serverless v2 + Data API
- **Frontend:** Next.js + Clerk + CloudFront
- **Market data:** yfinance (primary), Alpha Vantage (fallback)
- **MCP:** Playwright, Brave/Tavily, Filesystem, custom metrics MCP

## Terraform Modules

| Module | Purpose |
|--------|---------|
| `1_database` | Aurora PostgreSQL |
| `2_agents` | Lambdas, SQS, IAM |
| `3_discovery` | App Runner (optional, for Playwright MCP) |
| `4_frontend` | S3, CloudFront, API Gateway |

Each module has independent local state (`terraform.tfvars` required).
