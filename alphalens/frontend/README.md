# AlphaLens Frontend

Next.js (Pages Router) static export for AlphaLens.

## Setup

```bash
npm install
cp .env.local.example .env.local
```

Set `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Local dev

Terminal 1 — API:

```bash
cd ../backend/api
set -a && source ../../.env && set +a
MOCK_LAMBDAS=true uv run main.py
```

Terminal 2 — frontend:

```bash
npm run dev
```

Open http://localhost:3000

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Home + API health check |
| `/discover` | `POST /api/ecosystem/discover` — shows `discoveryRunId` when persisted to Aurora |
| `/dashboard` | Rank (table + `analysisReport`) + sync/async portfolio analyze |
| `/job?id=` | Poll job — `discovery_run_id`, `ranked_payload.analysisReport`, recommendations |

### API fields surfaced in the UI

- **Discovery** — `discoveryRunId` after a successful persist (Guide 4 Step 7).
- **Rank** (`POST /api/opportunities/rank`) — `rankedCandidates` (with `opportunityScore`, `attractiveEntryReason`), `analysisReport`, `warnings`.
- **Async jobs** — `ranked_payload` may include the same `analysisReport`; sync analyze returns recommendations only.

Discovery falls back to `mock/discovery.ts` if the API is unreachable.

## Build for S3 / CloudFront

```bash
npm run build
# static files in out/
```

Set `NEXT_PUBLIC_API_URL` to your CloudFront URL before building for production (same origin `/api/*` when using Guide 5 Terraform).

## Clerk (optional)

Set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` in `.env.local` to enable ClerkProvider. Auth is not required for local demo mode.
