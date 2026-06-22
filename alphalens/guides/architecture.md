# AlphaLens System Architecture

Full architecture reference for deployment and development.

## Layers

| Layer | Components | Guide |
|-------|------------|-------|
| Frontend | Next.js, Clerk, CloudFront, S3 | 5_frontend |
| API | FastAPI (`backend/api/main.py`), Mangum Lambda (`lambda_handler.handler`) | 5_frontend |
| Orchestration | SQS, Orchestrator Lambda | 3_agents |
| Agents | Discovery, Validator, Analyst, Portfolio, Q&A | 3_agents |
| Metrics | `alphalens-metrics` — yfinance, ranking, risk | 3_agents (code) |
| MCP | Playwright, Brave/Tavily (Guide 4) | 4_discovery |
| Data | Aurora PostgreSQL, curated JSON fallbacks | 2_database |

## MVP data flow (Guide 3)

```text
User + Profile + Portfolio + Core Company (e.g. NVDA)
  │
  ├─► POST /api/portfolio/analyze  (sync — full JSON response)
  │       └─► pipeline: discover → validate → rank → recommend
  ├─► POST /api/portfolio/analyze/stream  (sync — NDJSON per stage)
  │
  ├─► POST /api/ecosystem/discover  (full response)
  ├─► POST /api/ecosystem/discover/stream  (NDJSON — one candidate per event)
  ├─► POST /api/opportunities/rank  (rank only — full response)
  ├─► POST /api/opportunities/rank/stream  (NDJSON — validation → ranked rows)
  │
  ├─► POST /api/jobs/analyze  (async)
  │       └─► analysis_jobs row → SQS → orchestrator Lambda
  │               └─► same pipeline → updates analysis_jobs
  │
  ├─► POST /api/jobs/{id}/ask  (follow-up — full response)
  └─► POST /api/jobs/{id}/ask/stream  (SSE — streaming chat UI)
          └─► alphalens-qa Lambda, or in-process LLM when USE_LLM_QA=true locally
```

```text
Discovery (curated or live)  →  candidate pool
Validator                  →  drop invalid tickers
Analyst (yfinance)           →  ranked opportunities + analysisReport
Portfolio (risk + sizing)    →  actions (equity + CASH funding) + API JSON
Q&A                          →  answers from recommendation_payload

Discovery (authenticated)    →  discovery_runs + candidates (Guide 4 Step 7)
Orchestrator (async jobs)    →  analysis_jobs updates + discovery_run_id link
```

## API: local vs deployed

| Mode | Entry point | When |
|------|-------------|------|
| Local dev | `uv run main.py` → uvicorn | Guide 3 testing |
| AWS Lambda | `alphalens-api` — `lambda_handler.handler` (Mangum) | Guide 5 — `terraform/4_frontend` after `api_lambda.zip` |

`main.py` loads `alphalens/.env` at startup (path relative to `backend/api`). `lambda_invoke.py` reads `MOCK_LAMBDAS` at **request time** so `.env` changes take effect after restart.

| `MOCK_LAMBDAS` | Rank / analyze from local API |
|----------------|-------------------------------|
| `true` | In-process shared services (`[MOCK]` in logs) |
| `false` | Invoke `alphalens-*` Lambdas (`[INVOKE]` in logs) |

| `USE_LOCAL_PORTFOLIO` | Portfolio step only (when `MOCK_LAMBDAS=false`) |
|-----------------------|--------------------------------------------------|
| `true` | In-process `run_portfolio_agent()` (`[LOCAL] alphalens-portfolio` in logs) |
| `false` | Invoke `alphalens-portfolio` Lambda (required for async SQS jobs) |

Q&A invokes `alphalens-qa` by default unless `MOCK_QA=true`. Analyst LLM narrative runs on `alphalens-analyst` when not mocking — the API does not re-run `maybe_enrich_analyst_narrative()` after a Lambda invoke.

Agent Lambdas use `lambda_handler.lambda_handler` with `handle_agent_run()` — a different pattern because they are single-purpose functions, not HTTP apps.

## LLM data flow (Guide 4, optional)

| Agent | How LLM is enabled | Where it runs |
|-------|-------------------|---------------|
| **Discovery (live)** | `DISCOVERY_SERVICE_URL` → HTTP | Container `alphalens-discovery-live` (Guide 4) |
| **Orchestrator** | `USE_LLM_ORCHESTRATION=true` | Zip Lambda — Alex-style `package_docker.py` |
| **Portfolio narrative** | `USE_LLM_PORTFOLIO_NARRATIVE=true` (legacy `USE_LLM_PORTFOLIO`) | Zip `alphalens-portfolio` — slim OpenAI/Bedrock (not litellm) |
| **Q&A** | `USE_LLM_QA=true` | Zip Lambda — Alex-style `package_docker.py` |
| **Analyst narrative** | `USE_LLM_ANALYST_NARRATIVE=true` | Zip `alphalens-analyst` — slim OpenAI client or Bedrock Converse (**not** litellm) |

Validator and analyst **never** use an LLM for scores — rankings stay deterministic. Optional analyst LLM only writes the `analysisReport` narrative from `rankedPayload` (with guardrails in `analyst_report.py`).

**Config:** `LLM_PROVIDER` (`bedrock` or `openai`) in `alphalens/.env` for local runs; on AWS set `llm_provider` / `openai_*` in `terraform/2_agents/terraform.tfvars` (zip Lambdas) and `terraform/3_discovery/terraform.tfvars` (discovery-live).

**Not used in AlphaLens:** SageMaker embeddings, S3 Vectors, or Polygon (Alex Week 3 ingest path). Market data comes from **yfinance** in the analyst Lambda.

**Async jobs:** SQS decouples the user from long runs (same idea as Alex). The agent pipeline itself is **sequential** (discovery → validate → rank → portfolio) because each step depends on the previous output.

## Repository layout

```
alphalens/
├── backend/
│   ├── shared/          # Schemas, services, lambda_response, json_utils
│   ├── metrics/         # Deterministic engines
│   ├── database/        # Aurora Data API
│   ├── api/
│   │   ├── main.py              # FastAPI routes
│   │   ├── discovery_stream.py  # Discover NDJSON
│   │   ├── pipeline_stream.py   # Analyze NDJSON
│   │   ├── qa_stream.py         # Q&A SSE
│   │   ├── rank_stream.py       # Rank-only NDJSON
│   │   ├── package_docker.py    # api_lambda.zip
│   │   └── lambda_handler.py    # Mangum (Guide 5)
│   └── {agents}/        # agent.py, templates.py, lambda_handler.py
├── frontend/
├── guides/              # You are here
├── terraform/
│   ├── 1_database/
│   ├── 2_agents/        # 6 agent Lambdas + SQS
│   ├── 3_discovery/
│   └── 4_frontend/      # S3 + API Lambda + API Gateway + CloudFront (Guide 5)
└── design-doc.md
```

## Terraform modules (independent state)

Each `terraform/N_*` directory has its own `terraform.tfstate`. Outputs from earlier guides feed into later `terraform.tfvars` files (e.g. Aurora ARNs from Guide 2 → Guide 3 agents).

## Coexistence with Alex

AlphaLens uses the `alphalens-*` resource prefix. Alex uses `alex-*`. Both can run in the same AWS account without naming conflicts.

## Further reading

- [agent_architecture.md](./agent_architecture.md) — agent roles and `create_agent()` pattern
- [../architecture.md](../architecture.md) — product-level architecture
- [../../guides/architecture.md](../../guides/architecture.md) — parent Alex architecture
