# CLAUDE.md

AlphaLens Portfolio Agent is an AI-powered portfolio decision-support agent built around an ecosystem-based investment workflow. It discovers a candidate stock pool around a core company or investment theme, analyzes those candidates using deterministic market metrics, ranks potential entry opportunities, and generates portfolio-aware action recommendations based on the user's current holdings and risk profile.

It is not a trading bot, autonomous trading system, brokerage execution system, or tool that guarantees investment returns.

This file is for AI coding assistants and contributors. Keep detailed product logic in `design-doc.md`; keep this file focused on implementation rules, project conventions, and guardrails.

## Tech Stack

- Frontend: React.js, TypeScript
- Backend: Python, FastAPI
- Market data: yfinance (primary), Alpha Vantage (fallback)
- Search data: real-time web search API with local curated fallback
- Macro data: FRED API, optional for MVP
- AI: Anthropic Claude API
- Static demo data: local JSON/CSV files for reliable demo fallback

## Recommended Project Structure

```text
backend/
  api/                 FastAPI routes + Lambda handler
  database/            Aurora Data API library
  shared/              Schemas, MCP factories, prompts, curated data
  metrics/             Deterministic market engines
  orchestrator/        SQS workflow coordinator
  discovery/           Ecosystem discovery agent + MCP
  validator/           Ticker validation agent
  analyst/             Opportunity ranking agent
  portfolio/           Portfolio advisor agent
  qa/                  Follow-up Q&A agent
  tests/

frontend/
  pages/
  components/
  lib/
  mock/

guides/
terraform/
scripts/
```

## Backend Rules

- Use FastAPI route handlers only for request validation and HTTP response mapping.
- Put business logic in service modules, not route handlers.
- Keep deterministic financial calculations separate from AI recommendation code.
- Use Pydantic schemas for request and response contracts.
- Use a shared error response format for validation, data, discovery, ticker validation, and AI failures.
- External API clients should live in a dedicated `clients/` module.
- Do not call the AI service until discovery results, ticker validation, and deterministic metrics have already been calculated.
- Missing market data must be represented explicitly as `Unknown` or `Data unavailable`.
- Relationship discovery is candidate generation only. It must not be treated as a final investment recommendation.
- Ticker matching must be validated. If matching is ambiguous, return `Unknown`, `Data unavailable`, or use curated demo fallback data.
- Real-time discovery should have a local curated fallback for the NVIDIA demo scenario.

## Frontend Rules

- Use TypeScript types for all API request and response objects.
- Keep UI components small and data-driven.
- Use mock data first so the demo can work before backend integrations are complete.
- Show missing-data, uncertain ticker, private company, and low-confidence relationship warnings inline instead of blocking the whole page.
- Do not show unsupported certainty, guaranteed returns, or trade execution language.
- The UI should clearly separate candidate discovery, opportunity ranking, and portfolio-aware recommendation.

## Naming Conventions

- Python modules and packages: `snake_case`, for example `ecosystem_discovery_service.py`, `ticker_validation_service.py`, `market_metric_engine.py`.
- Python classes: `PascalCase`, for example `EcosystemDiscoveryService`.
- Python functions and variables: `snake_case`.
- Pydantic schema classes: `PascalCase`, for example `EcosystemDiscoveryRequest`.
- TypeScript components: `PascalCase`.
- TypeScript files: follow the existing frontend convention once created; prefer readable feature names.
- API JSON fields: `camelCase`.
- Constants and enum values: clear names that match API labels when possible.

## API Endpoints

Planned MVP endpoints:

- `GET /health`
- `POST /api/ecosystem/discover` — discover related companies around a core company or theme and map public companies to tickers
- `POST /api/opportunities/rank` — analyze the validated stock pool, rank potential add and watchlist candidates, and include lightweight entry-signal notes when supported
- `POST /api/portfolio/analyze` — evaluate candidate opportunities against the user's current holdings, risk profile, and portfolio constraints

Optional later endpoint:

- `POST /api/opportunities/entry-signals` — standalone entry-signal scan if the feature warrants a separate interface; for MVP, this logic should remain integrated into `/api/opportunities/rank`

All failures should use a consistent response shape:

```json
{
  "error": true,
  "code": "DATA_UNAVAILABLE",
  "message": "string",
  "affectedFields": ["fieldName"],
  "fallback": "string"
}
```

Expected error codes:

- `DATA_UNAVAILABLE`
- `DATA_PARTIAL`
- `FORMAT_ERROR`
- `VALIDATION_ERROR`
- `AI_PARSE_ERROR`
- `DISCOVERY_UNAVAILABLE`
- `TICKER_VALIDATION_ERROR`

## Financial and Discovery Data Rules

- Never invent financial metrics, price targets, entry prices, exit prices, or stop-loss levels.
- If data is missing, return `Unknown` or `Data unavailable`.
- AI must not calculate metrics. It can only explain metrics already provided by backend services.
- Suggested entry, exit, trim, or invalidation levels must come from deterministic market-data logic.
- News headlines must not directly trigger Buy or Sell. News must pass valuation, momentum, market, and portfolio-fit checks.
- A partnership, supplier relationship, customer relationship, or analyst upgrade must not directly trigger an Add recommendation.
- A price drop alone must not elevate a candidate's ranking. The drop must be supported by intact valuation, growth, financial health, and risk signals before it is treated as an entry signal.
- Personal trading history is a warning layer only. It must not blindly override current market and stock analysis.
- The product must not execute trades or imply that it can execute trades.

## Prompt Rules

- Keep prompt files under `backend/app/prompts/`.
- Do not merge all prompts into one file.
- Prompt files require careful review; do not auto-edit them unless the task explicitly asks for prompt changes.
- Recommended prompt files:
  - `ecosystem_discovery_prompt.md`
  - `opportunity_ranking_prompt.md`
  - `portfolio_summary_prompt.md`
  - `candidate_recommendation_prompt.md`
  - `action_plan_prompt.md`
  - `guardrail_explanation_prompt.md`
- Every AI prompt should include anti-hallucination language:

```text
Use only provided metrics and evidence.
Do not invent missing numbers.
If data is missing, write "Unknown" or "Data unavailable."
Do not promise returns.
Do not recommend real trade execution.
Do not generate price targets or entry/exit prices unless they are provided by deterministic backend logic.
Do not treat relationship discovery, partnership news, analyst upgrades, or positive headlines as direct Buy signals.
```

## Static Data Rules

Local fallback files should be treated as curated data:

- `sector_mapping.json`
- `demo_news.json`
- `curated_nvidia_ecosystem.json`
- `sample_trading_history.csv`
- frontend mock portfolio data
- frontend mock stock pool and opportunity ranking data

Do not rewrite curated data files casually. If values need to change, explain why in the commit or pull request.

## Do Not Build

- Real brokerage trade execution
- Autonomous trading
- Full options strategy engine
- Full backtesting engine
- Arbitrary custom strategy parser
- Full brokerage CSV compatibility
- Full SEC XBRL parsing in the MVP workflow
- AI-generated price targets without supporting market data
- Unlimited graph expansion across all related companies
- Fully automated ticker matching without validation
- A standalone daily scanner unless the MVP is already complete

## Test Commands

These commands should be updated once the actual scaffold is created.

Backend:

```bash
cd backend
pytest app/tests/
```

Frontend:

```bash
cd frontend
npm test
```

## Development Priority

1. Create the Python FastAPI backend scaffold.
2. Create the React TypeScript frontend scaffold.
3. Define shared Pydantic schemas and mock responses for ecosystem discovery, opportunity ranking, and portfolio analysis.
4. Build frontend demo flow with mock data for stock pool discovery, opportunity ranking, portfolio dashboard, and action plan.
5. Implement ecosystem discovery service with NVIDIA demo scenario.
6. Add ticker validation and curated NVIDIA ecosystem fallback data.
7. Implement market-data clients and deterministic metric engine for stock pool candidates.
8. Build opportunity ranking service using deterministic signals, including lightweight entry-signal check.
9. Implement portfolio parsing and portfolio risk engine.
10. Connect candidate opportunities to portfolio-aware recommendation logic.
11. Add AI recommendation generation after discovery, validation, metrics, and ranking are stable.
12. Add action plan output and error handling.
13. Add optional strategy template selection.
14. Add news / FRED / trading history only if time allows.
15. Polish UI and prepare demo script.
