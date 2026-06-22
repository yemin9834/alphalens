# AlphaLens — Frontend & API (Guide 5)

Deploy the FastAPI backend on Lambda, API Gateway, Next.js static site, and CloudFront.

**Prerequisites:**

- [3_agents.md](./3_agents.md) — agent Lambdas + SQS deployed
- [2_database.md](./2_database.md) — Aurora + Data API (for `/api/jobs/*`)
- Optional: [4_discovery.md](./4_discovery.md) — `discovery_service_url` for live MCP discovery on AWS

## What works today


| Component                | Local (Guide 3)                    | Guide 5 (AWS)                                     |
| ------------------------ | ---------------------------------- | ------------------------------------------------- |
| FastAPI `main.py`        | `uv run main.py`                   | Same code via Mangum on `alphalens-api` Lambda    |
| `lambda_handler.handler` | N/A                                | Deployed when `api_lambda.zip` exists             |
| `package_docker.py`      | —                                  | `backend/api/package_docker.py`                   |
| `terraform/4_frontend/`  | S3 bucket only until API zip built | **`alphalens-api` Lambda** + Lambda Function URL + CloudFront after packaging |

**API timeout note:** HTTP API (API Gateway v2) has a **fixed 30 second** integration limit — it cannot be increased. Production routes `/api/*` through **CloudFront → Lambda Function URL** (up to `api_lambda_timeout`, default 300s). The `api_gateway_url` output remains for quick curls but is not used by CloudFront.

**Important:** The backend API Lambda lives in **`terraform/4_frontend/`** (Guide 5), not `terraform/2_agents/`. Agent Lambdas are in Guide 3; `alphalens-api` does **not** exist in AWS until you package `api_lambda.zip` and run `terraform apply` here.

**Two-phase Terraform apply:**

1. `terraform apply` with only `terraform.tfvars` → creates **S3 bucket** for static files (no `alphalens-api` yet)
2. After `uv run package_docker.py` → `terraform apply` again → creates **`alphalens-api`**, API Gateway, CloudFront

## API code layout


| File                            | Purpose                                             |
| ------------------------------- | --------------------------------------------------- |
| `backend/api/main.py`           | FastAPI routes, shared services, job endpoints      |
| `backend/api/lambda_handler.py` | AWS entry — `handler = Mangum(app, lifespan="off")` |
| `backend/api/discovery_stream.py` | NDJSON stream for progressive discover UI         |
| `backend/api/pipeline_stream.py`  | NDJSON stream for sync analyze (stage-by-stage)    |
| `backend/api/qa_stream.py`        | SSE stream for job Q&A chat                        |
| `backend/api/rank_stream.py`      | NDJSON stream for rank-only analysis             |
| `backend/api/package_docker.py` | Docker build for `api_lambda.zip` (linux/amd64)     |


Agent Lambdas use `lambda_handler.lambda_handler` + `handle_agent_run()`. The API uses `**lambda_handler.handler`** because it is a web app (Alex Guide 7 pattern).

## API endpoints


| Endpoint                            | Method | Notes                                       |
| ----------------------------------- | ------ | ------------------------------------------- |
| `/health`                           | GET    | Health check                                |
| `/api/ecosystem/discover`            | POST   | Curated or live via `DISCOVERY_SERVICE_URL` |
| `/api/ecosystem/discover/stream`    | POST   | NDJSON — LLM `token` chunks (live discovery), then candidates row-by-row |
| `/api/opportunities/rank`           | POST   | yfinance ranking (full response)            |
| `/api/opportunities/rank/stream`    | POST   | NDJSON — validation → ranked rows → report  |
| `/api/portfolio`                    | GET    | Load saved holdings + candidate pool from DB  |
| `/api/portfolio`                    | PUT    | Save holdings to default portfolio            |
| `/api/populate-test-data`           | POST   | Demo portfolio + NVIDIA candidates (Alex-style) |
| `/api/portfolio/analyze`            | POST   | Sync pipeline — requires `candidatePool`    |
| `/api/portfolio/analyze/stream`     | POST   | NDJSON — validation → analysis → portfolio  |
| `/api/jobs/analyze`                 | POST   | Async via SQS                               |
| `/api/jobs/{job_id}`                | GET    | Poll job status                             |
| `/api/jobs/{job_id}/ask`            | POST   | Q&A on completed job (full response)        |
| `/api/jobs/{job_id}/ask/stream`     | POST   | SSE — streaming Q&A chat (UI)               |


When `MOCK_LAMBDAS=false`, the API invokes `alphalens-*` agent Lambdas (and optional live discovery HTTP when `DISCOVERY_SERVICE_URL` is set). Q&A streams via **`QA_SERVICE_URL`** → `alphalens-qa` Function URL (`/ask/stream`); sync `/ask` uses `/ask` on the same URL. Set `MOCK_QA=true` locally for offline keyword answers.

`main.py` loads `alphalens/.env` automatically on startup and logs `Agent routing: MOCK_LAMBDAS=… MOCK_QA=…`.

## Backend local dev

```bash
cd alphalens/backend/api
uv sync
uv run main.py
```

| `MOCK_LAMBDAS` in `.env` | Agent behavior from local API |
|--------------------------|-------------------------------|
| `true` | Rank/analyze run agents **in-process** (fast, no Lambda cost) |
| `false` | Rank/analyze **invoke AWS Lambdas** (`[INVOKE]` in logs) |

| `USE_LOCAL_PORTFOLIO` (when `MOCK_LAMBDAS=false`) | Portfolio step only |
|---------------------------------------------------|---------------------|
| `true` | Portfolio in-process — good for `ActionPlanService` / cash allocation changes without redeploying `alphalens-portfolio` |
| `false` | Portfolio via `alphalens-portfolio` Lambda (required for async jobs) |

Discovery with `DISCOVERY_SERVICE_URL` uses HTTP streaming to `{DISCOVERY_SERVICE_URL}/discover/stream` (`[HTTP]` in logs — not the slim discovery Lambda). NDJSON events: `start` → `status` / `token` → `warning` → `candidate` → `done`.

Test:

```bash
curl -s http://localhost:8000/health

curl -s -X POST http://localhost:8000/api/portfolio/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "riskProfile": "balanced",
    "portfolio": [
      {"ticker": "NVDA", "weight": 35},
      {"ticker": "MSFT", "weight": 25},
      {"ticker": "CASH", "weight": 40}
    ],
    "candidatePool": [{"ticker": "TSM", "relationshipType": "supplier"}]
  }' | jq .
```

Live discovery locally: set `DISCOVERY_SERVICE_URL` in `alphalens/.env` (see [4_discovery.md](./4_discovery.md)).

## Frontend local dev

The UI is wired to the API (`lib/api.ts`). Start the backend for live data.

```bash
cd alphalens/frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

| Page | API | UI highlights |
|------|-----|----------------|
| `/discover` | `POST /api/ecosystem/discover/stream` (falls back to mock if API down) | Live research log streams LLM tokens; candidates appear row-by-row; `discoveryRunId` when persisted |
| `/dashboard` | `rank/stream`, `analyze/stream`, async job enqueue | Rank rows + pipeline cards stream in progressively |
| `/job?id=` | Poll job + `ask/stream` | Chat-style Q&A with markdown; progressive results while job runs |

**API response fields surfaced in the UI:**

- **Rank** — `rankedCandidates`, `analysisReport`, `warnings`
- **Sync analyze** — portfolio recommendation + `analysisReport` + `warnings`
- **Async job** — poll `ranked_payload` / `recommendation_payload` on `/job`
- **Recommended actions** — equity Add/Trim/Hold plus optional **Trim CASH** / **Add CASH** when the deterministic plan funds adds or rebalances the cash buffer (see [3_agents.md](./3_agents.md) §2.4)

Requires API running locally or deployed CloudFront/API URL in `frontend/.env.local` (`NEXT_PUBLIC_API_URL`).

## Step 1: Configure Terraform

```bash
cd alphalens/terraform/4_frontend
cp terraform.tfvars.example terraform.tfvars
```

Prerequisites: deploy Guides 1–3 first so these state files exist:

- `terraform/1_database/terraform.tfstate`
- `terraform/2_agents/terraform.tfstate`
- `terraform/3_discovery/terraform.tfstate` (optional — for live discovery URL)

The frontend module reads Aurora, SQS, and discovery URLs from those local state files (same pattern as Alex Guide 7).

Key variables in `terraform.tfvars`:


| Variable                | Source                                              |
| ----------------------- | --------------------------------------------------- |
| `discovery_service_url` | Optional override; else from `terraform/3_discovery` |
| `clerk_jwks_url`        | Clerk dashboard                                     |


```bash
terraform init
terraform apply   # creates S3 bucket; API resources wait for zip
```

## Step 2: Package API for Lambda

Requires **Docker Desktop**.

```bash
cd alphalens/backend/api
uv run package_docker.py
```

Creates `api_lambda.zip` with `main.py`, stream helpers, `lambda_handler.py`, `alphalens_shared`, `alphalens_metrics`, and the database `src` package (installed via Docker — do not copy `src/` twice).

Packaging uses `uv export --no-emit-local` so workspace paths like `./database` are not passed to pip inside Docker.

## Step 3: Deploy API + CloudFront (creates `alphalens-api`)

```bash
cd alphalens/terraform/4_frontend
terraform apply
```

Note outputs:

```bash
terraform output cloudfront_url
terraform output api_gateway_url
```

Add to `alphalens/.env` (for local scripts/tests against deployed API):

```bash
# Use CloudFront so /api/* routes work:
# NEXT_PUBLIC_API_URL=https://xxxx.cloudfront.net
```

### API-only code updates (after first deploy)

Once `alphalens-api` exists, you do **not** need a full terraform apply for code changes:

```bash
cd alphalens/backend/api
uv run package_docker.py

# api_lambda.zip is often >70MB (LLM deps) — upload via S3, not --zip-file
BUCKET=alphalens-lambda-packages-$(aws sts get-caller-identity --query Account --output text)
aws s3 cp api_lambda.zip s3://${BUCKET}/api/api_lambda.zip
aws lambda update-function-code \
  --function-name alphalens-api \
  --s3-bucket ${BUCKET} \
  --s3-key api/api_lambda.zip
```

Or run `terraform apply` in `4_frontend` after packaging — it uploads the zip to the same S3 bucket and updates the Lambda.

Use `terraform apply` in `4_frontend` when IAM, env vars, or API Gateway / CloudFront settings change.

## Step 4: Deploy static frontend

**Before build** — set in `frontend/.env.local` (Next.js bakes this into the static export):

```bash
NEXT_PUBLIC_API_URL=https://<your-cloudfront-domain>
```

Then build, upload, and **invalidate CloudFront** (otherwise the edge may serve old `index.html` with `localhost:8000` for up to an hour):

```bash
cd alphalens/frontend
npm run build   # must finish with no errors — creates out/

BUCKET=$(cd ../terraform/4_frontend && terraform output -raw frontend_bucket)
aws s3 sync out/ "s3://${BUCKET}/" --delete

# Confirm upload (should list index.html with recent timestamp)
aws s3 ls "s3://${BUCKET}/" | head

# Invalidate cached HTML/JS at CloudFront (replace with your distribution id)
DIST_ID=$(aws cloudfront list-distributions --query \
  "DistributionList.Items[?DomainName=='d2lv2rvo6a5fs2.cloudfront.net'].Id" --output text)
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
```

**Verify the build picked up the right API URL** before uploading (use `-r` — env vars live in `chunks/pages/`, not only top-level `chunks/*.js`):

```bash
grep -rl "d2lv2rvo6a5fs2.cloudfront.net" out/_next/static/chunks/
# Good: prints one or more .js paths (often chunks/pages/_app-*.js)

grep -rl "localhost:8000" out/_next/static/chunks/ || echo "OK: no localhost in build"
# Good: "OK: no localhost in build"
```

Hard-refresh the browser (Cmd+Shift+R). Footer should read `API · https://<cloudfront-domain>`.

**Health check:** the UI calls `GET /api/health` through CloudFront (not `/health` — that path is served by S3).

| Dev mode | `NEXT_PUBLIC_API_URL` |
|----------|------------------------|
| Local API + `npm run dev` | `http://localhost:8000` |
| Deployed API + local `npm run dev` | `https://<cloudfront-domain>` (needs `cors_origins` to include `http://localhost:3000` in tfvars) |
| Production (static site on CloudFront) | Set before `npm run build` — same CloudFront URL (same-origin `/api/*`) |

## Environment variables (API Lambda)


| Variable                    | Purpose                                                   |
| --------------------------- | --------------------------------------------------------- |
| `AURORA_*`, `DATABASE_NAME` | Jobs + Q&A database access                                |
| `SQS_QUEUE_URL`             | Async `/api/jobs/analyze`                                 |
| `DISCOVERY_SERVICE_URL`     | Live MCP discovery (Guide 4); empty = slim curated Lambda |
| `QA_SERVICE_URL`            | `alphalens-qa` Function URL from `terraform/2_agents` — SSE proxy for `/ask/stream` |
| `QA_FUNCTION`               | Legacy name; Q&A HTTP uses `QA_SERVICE_URL` |
| `*_FUNCTION`                | Agent Lambda names for sync pipeline                      |
| `MOCK_LAMBDAS`              | `false` on AWS and when testing Lambdas locally           |
| `USE_LOCAL_PORTFOLIO`       | `true` locally to test portfolio/metrics in-process; `false` on deployed API Lambda |
| `MOCK_QA`                   | `false` by default — Q&A invokes `alphalens-qa` Lambda    |
| `USE_LLM_ANALYST_NARRATIVE` | Local only; on AWS set `use_llm_analyst_narrative` in tfvars |
| `CORS_ORIGINS`              | Frontend origins                                          |
| `CLERK_JWKS_URL`            | JWT validation (when enabled)                             |


## Troubleshooting


| Symptom                                          | Fix                                                                                   |
| ------------------------------------------------ | ------------------------------------------------------------------------------------- |
| `alphalens-api` not in AWS Lambda console        | Package `api_lambda.zip` first, then `terraform apply` in `4_frontend` (not `2_agents`) |
| `terraform apply` — only S3, no API              | Run `package_docker.py` first, then `terraform apply` again                           |
| `api_lambda.zip` not found                       | `cd backend/api && uv run package_docker.py`                                          |
| `RequestEntityTooLargeException` on API deploy   | Zip exceeds ~70MB — use S3 upload (see redeploy commands above) or `terraform apply` in `4_frontend` |
| `No module named 'templates'` / `./database` pip error | Update `package_docker.py` — uses `--no-emit-local` and filters editable paths   |
| `FileExistsError: package/src` during packaging  | Fixed — `src/` comes from `pip install /database`; no manual `copytree`             |
| `/api/health` → `Internal Server Error` on CloudFront | Lambda import crash — repackage API (`auth.py` must be in zip); `aws logs tail /aws/lambda/alphalens-api --follow` |
| Docker build fails                               | Start Docker Desktop                                                                  |
| Streaming works locally but not on AWS           | Repackage + deploy API zip; API Gateway may buffer chunks (batchier than localhost) |
| Q&A cursor stuck, no stream chunks on CloudFront | CloudFront `/api/*` only matched one path segment — run `terraform apply` in `4_frontend` (multi-depth patterns). Repackage API; set `use_llm_qa` + LLM keys in `4_frontend/terraform.tfvars` so stream runs in `alphalens-api` (API Gateway max 30s per request — no nested QA invoke) |
| `ask/stream` stuck cursor, no tokens until timeout | Mangum buffers SSE on Lambda. Redeploy with **Lambda Web Adapter** (`run.sh` handler + `RESPONSE_STREAM` on Function URL — `terraform apply` in `4_frontend`). Repackage `api_lambda.zip` first. |
| `ask/stream` pending ~30s then fails              | API Gateway integration timeout is 30s — use CloudFront (Function URL origin), not `api_gateway_url` |
| `ModuleNotFoundError: alphalens_metrics` (local) | `cd backend/api && uv sync`                                                           |
| CORS errors from CloudFront                      | Add CloudFront URL to `cors_origins` in tfvars; re-apply                              |
| Discovery returns curated on AWS                 | Set `discovery_service_url` in `terraform/4_frontend/terraform.tfvars`                |
| Discovery 504 on CloudFront → mock data          | HTTP API v2 cannot exceed **30s** (not configurable). CloudFront `/api/*` must use **Lambda Function URL** origin (`terraform apply` in `4_frontend`). Stream `token` / `status` heartbeats keep the connection alive; `api_lambda_timeout` / `discovery_http_timeout` default 300s. Direct `api_gateway_url` still 30s — use CloudFront in production |
| No LLM tokens on Discover (only row-by-row)      | Redeploy live discovery container: `cd backend/discovery && uv run deploy.py`. Repackage API zip if `lambda_invoke.py` changed. `USE_LIVE_DISCOVERY=true` on `alphalens-discovery-live` |
| `candidatePool` required                         | `/api/portfolio/analyze` needs tickers — discover first via `/api/ecosystem/discover` |
| Warnings banner: “LLM narrative unavailable”     | Analyst Lambda zip missing `openai` — repackage per [3_agents.md](./3_agents.md) §4.2 |
| Q&A returns instantly (no LLM)                   | `USE_LLM_QA=true` on **`alphalens-qa`** (`terraform/2_agents`); not on alphalens-api |
| No logs on `alphalens-qa` during job Q&A       | Check `QA_SERVICE_URL` on alphalens-api; stream must hit QA Function URL `/ask/stream` |
| Q&A `HTTP Error 403: Forbidden` (CloudWatch on **alphalens-api**) | `alphalens-api` cannot call `QA_SERVICE_URL`. Confirm URL is `https://….lambda-url….on.aws` (not CloudFront). Run `cd scripts && uv run fix_qa_function_url_permissions.py`, then `terraform init -upgrade && terraform apply` in `2_agents` (provider >= 6.28 adds `invoked_via_function_url` permission) |
| `Q&A templates not found` on `/ask/stream`       | Repackage **`alphalens-qa`** zip (`backend/qa/package_docker.py`) after server/sse_stream changes |
| `[MOCK]` in logs but `MOCK_LAMBDAS=false`        | Restart API after `.env` change; confirm startup log shows `MOCK_LAMBDAS=false`       |
| Cash actions missing on async job page           | Redeploy `alphalens-portfolio` only — [3_agents.md](./3_agents.md) §7.1; run a **new** job |
| Cash actions on sync but not async               | `USE_LOCAL_PORTFOLIO=true` affects local API only — async uses AWS portfolio Lambda   |
| CloudFront UI still shows `API · localhost:8000` | Old static build in edge cache or S3 never updated | `npm run build` → `aws s3 sync` → `aws cloudfront create-invalidation --paths "/*"` |
| `npm run build` — no `out/` folder               | Build failed or not run                            | Fix build errors; re-run `npm run build` until `out/` exists                        |


## Pattern reference

- Alex Guide 7: [../../guides/7_frontend.md](../../guides/7_frontend.md)
- Alex `terraform/7_frontend/` — same CloudFront + API Gateway split (`/api/*` → API GW, rest → S3)

## Clerk authentication (optional)

AlphaLens works in **demo mode** without Clerk: leave `CLERK_JWKS_URL` empty and omit Clerk keys from `frontend/.env.local`. All API calls use `DEMO_USER_ID` (`demo-user`).

To enable per-user jobs and sign-in:

### 1. Create a Clerk application

1. Sign up at [clerk.com](https://clerk.com) and create an application.
2. In **Configure → API Keys**, copy the **Publishable key** and **Secret key**.
3. In **Configure → JWT templates** (or **API keys → Advanced**), note the **JWKS URL** — typically:
   `https://<your-clerk-domain>/.well-known/jwks.json`
4. Note the **Issuer** URL (e.g. `https://<your-clerk-domain>`).

### 2. Frontend `.env.local`

```bash
cd alphalens/frontend
cp .env.local.example .env.local
```

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

Restart `npm run dev` after changing env vars.

### 3. API (local)

Add to `alphalens/.env`:

```bash
CLERK_JWKS_URL=https://<your-clerk-domain>/.well-known/jwks.json
CLERK_ISSUER=https://<your-clerk-domain>
```

Restart the API. `GET /health` should report `"clerkAuth": true`.

### 4. Deployed API (Terraform)

In `terraform/4_frontend/terraform.tfvars`:

```hcl
clerk_jwks_url = "https://<your-clerk-domain>/.well-known/jwks.json"
clerk_issuer   = "https://<your-clerk-domain>"
```

Re-run `terraform apply` after packaging the API zip.

### 5. Deployed frontend

Set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` in `frontend/.env.local` **before** `npm run build`, then sync `out/` to S3. CloudFront serves the static site; API calls go to the same origin (`NEXT_PUBLIC_API_URL` = CloudFront URL).

Signed-in users get a `UserButton` on Discover / Analyze / Job pages. The frontend calls `GET /api/me` once after sign-in to create the user row in Aurora.

## Next steps

- Optional: [4_discovery.md](./4_discovery.md) — wire `discovery_service_url` for live ecosystem research on AWS
- Destroy when not in use: `cd terraform/4_frontend && terraform destroy`

