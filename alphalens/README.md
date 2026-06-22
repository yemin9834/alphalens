# AlphaLens Portfolio Agent

AI-powered portfolio decision-support: ecosystem stock pool discovery → deterministic metrics → opportunity ranking → portfolio-aware action recommendations.

**Not a trading bot.** Does not execute trades or guarantee returns.

## Documentation

| File | Purpose |
|------|---------|
| [design-doc.md](./design-doc.md) | Product requirements, API contract, MVP scope |
| [CLAUDE.md](./CLAUDE.md) | Implementation rules for AI assistants |
| [AGENTS.md](./AGENTS.md) | Quick reference for agents and conventions |
| [architecture.md](./architecture.md) | System architecture overview |
| [guides/](./guides/) | Step-by-step AWS deployment guides |

## Directory structure

```text
alphalens/
├── backend/
│   ├── api/              FastAPI + Lambda handler
│   ├── database/         Aurora Data API library
│   ├── shared/           Schemas, MCP factories, curated data
│   ├── metrics/          Deterministic engines (no LLM)
│   ├── orchestrator/     SQS workflow coordinator
│   ├── discovery/        Ecosystem discovery + MCP
│   ├── validator/        Ticker validation
│   ├── analyst/          Opportunity ranking agent
│   ├── portfolio/        Portfolio advisor agent
│   └── qa/               Follow-up Q&A agent
├── frontend/             Next.js + TypeScript
├── guides/               Deployment guides
├── terraform/            Independent Terraform modules
└── scripts/              Local dev helpers
```

## Quick start (local)

### Database (after Terraform Guide 2)

```bash
cd alphalens/backend/database
uv sync
uv run test_data_api.py
uv run run_migrations.py
uv run reset_db.py --with-test-data   # optional
```

### Backend API

```bash
cd alphalens/backend/api
uv sync
uv run uvicorn main:app --reload --port 8000
curl http://localhost:8000/health
```

### Frontend

```bash
cd alphalens/frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000 — `/discover` uses mock NVIDIA ecosystem data.

### Environment

```bash
cp alphalens/.env.example alphalens/.env
```

## API (MVP)

```text
GET  /health
POST /api/ecosystem/discover
POST /api/opportunities/rank
POST /api/portfolio/analyze
```

## Deployment

Follow guides in order:

1. [guides/1_permissions.md](./guides/1_permissions.md)
2. [guides/2_database.md](./guides/2_database.md) → `terraform/1_database`
3. [guides/3_agents.md](./guides/3_agents.md) → `terraform/2_agents`
4. [guides/4_discovery.md](./guides/4_discovery.md) → `terraform/3_discovery` (optional)
5. [guides/5_frontend.md](./guides/5_frontend.md) → `terraform/4_frontend`

## Parent project

AlphaLens lives inside the [Alex](../) monorepo. Reuse AWS permissions and agent patterns from the Alex course project.
