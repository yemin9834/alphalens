"""
AlphaLens FastAPI backend — design-doc.md §14 API contract.
"""

from pathlib import Path

from dotenv import load_dotenv

# Load alphalens/.env before agent imports read MOCK_LAMBDAS (cwd is backend/api).
_root_env = Path(__file__).resolve().parents[2] / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=True)
load_dotenv(override=True)

import logging
import os

import boto3
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from discovery_stream import iter_discovery_stream
from pipeline_stream import iter_analysis_stream
from qa_stream import iter_qa_sse
from rank_stream import iter_rank_stream

from alphalens_shared import (
    AnalysisReport,
    DiscoveryRunCandidatesResponse,
    DiscoveryRunStatusResponse,
    EcosystemDiscoverRequest,
    EcosystemDiscoverResponse,
    ErrorResponse,
    InstrumentSearchResponse,
    OpportunitiesRankRequest,
    OpportunitiesRankResponse,
    PortfolioAnalyzeRequest,
    PortfolioAnalyzeResponse,
    PortfolioHolding,
    PortfolioReport,
    PopulateTestDataResponse,
    RankedCandidate,
    SavedPortfolioResponse,
    ValidationReport,
)
from src.demo_data import build_portfolio_payload, populate_demo_data, save_user_holdings
from alphalens_shared.lambda_invoke import (
    ANALYST_FUNCTION,
    VALIDATOR_FUNCTION,
    invoke_agent,
    invoke_discovery,
)
from alphalens_shared.services.analyst import run_analyst
from alphalens_shared.services.analyst_narrative import maybe_enrich_analyst_narrative
from alphalens_shared.services.discovery import to_api_candidates
from alphalens_shared.services.discovery_persist import persist_discovery_run
from alphalens_shared.services.pipeline import run_analysis_pipeline
from alphalens_shared.services.instrument_search import search_instruments
from alphalens_shared.services.validator import run_validator_agent
from auth import CLERK_ENABLED, get_current_user_id
from src import Database
from src.schemas import AnalysisJobCreate, HoldingCreate, PortfolioSaveInput, UserCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(
    "Agent routing: MOCK_LAMBDAS=%s MOCK_QA=%s",
    os.getenv("MOCK_LAMBDAS", "false"),
    os.getenv("MOCK_QA", "false"),
)

app = FastAPI(
    title="AlphaLens API",
    description="Ecosystem discovery, opportunity ranking, and portfolio analysis",
    version="0.1.0",
)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sqs_client = boto3.client("sqs")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")


def _db() -> Database:
    return Database(
        cluster_arn=os.environ.get("AURORA_CLUSTER_ARN"),
        secret_arn=os.environ.get("AURORA_SECRET_ARN"),
        database=os.environ.get("DATABASE_NAME", "alphalens"),
        region=os.environ.get("DEFAULT_AWS_REGION", os.environ.get("AWS_REGION", "us-east-1")),
    )


def _ensure_user(db: Database, clerk_user_id: str) -> None:
    if not db.users.find_by_clerk_id(clerk_user_id):
        db.users.create_user(UserCreate(clerk_user_id=clerk_user_id))
        logger.info("Created user record for %s", clerk_user_id)


def _verify_job_owner(job: dict, clerk_user_id: str) -> None:
    if job.get("clerk_user_id") != clerk_user_id:
        raise HTTPException(status_code=403, detail="Job does not belong to this user")


def _mock_lambdas() -> bool:
    return os.getenv("MOCK_LAMBDAS", "false").lower() == "true"


def _invoke_or_local(function_name: str, payload: dict, local_handler):
    """Route to agent Lambda when deployed; run in-process when MOCK_LAMBDAS=true."""
    if _mock_lambdas():
        return local_handler(payload)
    return invoke_agent(function_name, payload)


def _parse_validation_report(raw: object) -> ValidationReport | None:
    if not raw or not isinstance(raw, dict):
        return None
    try:
        return ValidationReport.model_validate(raw)
    except Exception:
        return None


def _parse_portfolio_report(raw: object) -> PortfolioReport | None:
    if not raw or not isinstance(raw, dict):
        return None
    try:
        return PortfolioReport.model_validate(raw)
    except Exception:
        return None


def _parse_analysis_report(raw: object) -> AnalysisReport | None:
    if not raw or not isinstance(raw, dict):
        return None
    try:
        return AnalysisReport(**raw)
    except Exception:
        logger.warning("Invalid analysisReport shape from agent")
        return None


@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "alphalens-api",
        "clerkAuth": CLERK_ENABLED,
    }


@app.get("/api/me")
def get_me(clerk_user_id: str = Depends(get_current_user_id)):
    """Bootstrap user row on first authenticated request."""
    db = _db()
    _ensure_user(db, clerk_user_id)
    user = db.users.find_by_clerk_id(clerk_user_id)
    return {"user": user, "clerk_user_id": clerk_user_id}


def _saved_portfolio_response(raw: dict) -> SavedPortfolioResponse:
    return SavedPortfolioResponse(
        name=raw.get("name", "Default Portfolio"),
        holdings=[PortfolioHolding(**h) for h in raw.get("holdings", [])],
        discoveryRunId=raw.get("discoveryRunId"),
        candidatePool=raw.get("candidatePool", []),
    )


@app.get("/api/instruments/search", response_model=InstrumentSearchResponse)
def instruments_search(
    q: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(8, ge=1, le=20),
):
    """Search tickers and company names for portfolio autocomplete (public read)."""
    return search_instruments(q, limit=limit)


@app.get("/api/portfolio", response_model=SavedPortfolioResponse)
def get_portfolio(clerk_user_id: str = Depends(get_current_user_id)):
    """Load the current user's default portfolio and latest discovery candidate pool."""
    db = _db()
    _ensure_user(db, clerk_user_id)
    return _saved_portfolio_response(build_portfolio_payload(db, clerk_user_id))


@app.put("/api/portfolio", response_model=SavedPortfolioResponse)
def put_portfolio(
    body: PortfolioSaveInput,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Save holdings on the user's default portfolio."""
    db = _db()
    _ensure_user(db, clerk_user_id)
    holdings = [HoldingCreate(**h.model_dump()) for h in body.holdings]
    payload = save_user_holdings(db, clerk_user_id, holdings)
    return _saved_portfolio_response(payload)


@app.post("/api/populate-test-data", response_model=PopulateTestDataResponse)
def populate_test_data(clerk_user_id: str = Depends(get_current_user_id)):
    """
    Populate demo portfolio and NVIDIA ecosystem candidates for the current user.

    Alex-style one-click test data — holdings, discovery run, and candidate pool.
    """
    db = _db()
    try:
        result = populate_demo_data(db, clerk_user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PopulateTestDataResponse(
        message=result["message"],
        portfolio=_saved_portfolio_response(result["portfolio"]),
        discoveryRunId=result.get("discoveryRunId"),
        candidatesLoaded=result.get("candidatesLoaded", 0),
    )


@app.post("/api/ecosystem/discover", response_model=EcosystemDiscoverResponse)
def ecosystem_discover(
    request: EcosystemDiscoverRequest,
    clerk_user_id: str = Depends(get_current_user_id),
):
    db = _db()
    _ensure_user(db, clerk_user_id)
    payload = {**request.model_dump(), "clerkUserId": clerk_user_id}
    result = invoke_discovery(payload)
    if not result.get("success", True):
        raise HTTPException(status_code=500, detail=result.get("error", "Discovery failed"))

    if not result.get("discoveryRunId"):
        run_id = persist_discovery_run(clerk_user_id, payload, result)
        if run_id:
            result["discoveryRunId"] = run_id

    candidates = to_api_candidates(result.get("candidates", []))
    return EcosystemDiscoverResponse(
        coreCompany=result.get("coreCompany", request.coreCompany),
        coreTicker=result.get("coreTicker", request.coreTicker),
        candidates=candidates,
        warnings=result.get("warnings", []),
        discoveryRunId=result.get("discoveryRunId"),
    )


@app.post("/api/ecosystem/discover/stream")
def ecosystem_discover_stream(
    request: EcosystemDiscoverRequest,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Stream discovery candidates progressively as NDJSON."""
    db = _db()
    _ensure_user(db, clerk_user_id)
    payload = request.model_dump()
    return StreamingResponse(
        iter_discovery_stream(payload, clerk_user_id),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _verify_discovery_run_owner(run: dict, clerk_user_id: str) -> None:
    if run.get("clerk_user_id") != clerk_user_id:
        raise HTTPException(status_code=404, detail="Discovery run not found")


def _candidate_row_to_api(row: dict) -> dict:
    import json

    deep = row.get("deep_research")
    if isinstance(deep, str):
        try:
            deep = json.loads(deep)
        except json.JSONDecodeError:
            deep = None
    return {
        "companyName": row.get("company_name", ""),
        "ticker": row.get("ticker", ""),
        "relationshipType": row.get("relationship_type", ""),
        "relationshipSummary": row.get("relationship_summary", "") or "",
        "confidence": row.get("confidence", "Medium"),
        "evidenceUrl": row.get("evidence_url", "") or "",
        "tickerValidation": row.get("ticker_validation", "") or "",
        "deepResearch": deep,
    }


def _research_progress(run: dict) -> dict:
    import json

    progress = run.get("research_progress") or {}
    if isinstance(progress, str):
        try:
            progress = json.loads(progress)
        except json.JSONDecodeError:
            progress = {}
    return progress if isinstance(progress, dict) else {}


@app.get("/api/discovery-runs/{run_id}", response_model=DiscoveryRunStatusResponse)
def get_discovery_run(run_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    db = _db()
    run = db.discovery_runs.find_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")
    _verify_discovery_run_owner(run, clerk_user_id)

    rows = db.candidates.find_by_run(run_id)
    progress = _research_progress(run)
    researched = sum(1 for row in rows if row.get("deep_research"))

    return DiscoveryRunStatusResponse(
        discoveryRunId=run_id,
        coreCompany=run.get("core_company", ""),
        coreTicker=run.get("core_ticker", ""),
        status=run.get("status", "completed"),
        researchStatus=run.get("research_status") or "pending",
        researchProgress=progress,
        candidateCount=len(rows),
        researchedCount=researched,
    )


@app.get(
    "/api/discovery-runs/{run_id}/candidates",
    response_model=DiscoveryRunCandidatesResponse,
)
def get_discovery_run_candidates(
    run_id: str, clerk_user_id: str = Depends(get_current_user_id)
):
    db = _db()
    run = db.discovery_runs.find_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")
    _verify_discovery_run_owner(run, clerk_user_id)

    rows = db.candidates.find_by_run(run_id)
    candidates = [_candidate_row_to_api(row) for row in rows if row.get("ticker")]
    return DiscoveryRunCandidatesResponse(
        discoveryRunId=run_id,
        researchStatus=run.get("research_status") or "pending",
        candidates=to_api_candidates(candidates),
    )


@app.post("/api/opportunities/rank", response_model=OpportunitiesRankResponse)
def opportunities_rank(
    request: OpportunitiesRankRequest,
    clerk_user_id: str = Depends(get_current_user_id),
):
    _ensure_user(_db(), clerk_user_id)
    raw_candidates = [c.model_dump() for c in request.candidates]
    validated = _invoke_or_local(
        VALIDATOR_FUNCTION,
        {"candidates": raw_candidates},
        run_validator_agent,
    )
    if not validated.get("success", True):
        raise HTTPException(status_code=500, detail=validated.get("error", "Validation failed"))

    good = [
        c
        for c in validated.get("validatedCandidates", [])
        if c.get("tickerValidation") != "invalid"
    ]

    analyst_payload = {
        "riskProfile": request.riskProfile,
        "marketCondition": request.marketCondition,
        "candidates": good,
    }
    analysis = _invoke_or_local(ANALYST_FUNCTION, analyst_payload, run_analyst)
    if _mock_lambdas():
        analysis = maybe_enrich_analyst_narrative(analyst_payload, analysis)
    if not analysis.get("success", True):
        raise HTTPException(status_code=500, detail=analysis.get("error", "Ranking failed"))

    ranked = []
    for row in analysis.get("rankedCandidates", []):
        fields = {k: v for k, v in row.items() if k in RankedCandidate.model_fields}
        ranked.append(RankedCandidate(**fields))

    validation_warnings = validated.get("warnings", [])
    analysis_warnings = analysis.get("warnings", [])

    return OpportunitiesRankResponse(
        rankedCandidates=ranked,
        validationReport=_parse_validation_report(validated.get("validationReport")),
        analysisReport=_parse_analysis_report(analysis.get("analysisReport")),
        warnings=validation_warnings + analysis_warnings,
    )


@app.post("/api/opportunities/rank/stream")
def opportunities_rank_stream(
    request: OpportunitiesRankRequest,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Stream rank-only analysis progressively as NDJSON."""
    _ensure_user(_db(), clerk_user_id)
    payload = request.model_dump()
    ranked_fields = set(RankedCandidate.model_fields.keys())
    return StreamingResponse(
        iter_rank_stream(
            payload,
            parse_validation=_parse_validation_report,
            parse_analysis=_parse_analysis_report,
            ranked_candidate_fields=ranked_fields,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/portfolio/analyze", response_model=PortfolioAnalyzeResponse)
def portfolio_analyze(
    request: PortfolioAnalyzeRequest,
    clerk_user_id: str = Depends(get_current_user_id),
):
    _ensure_user(_db(), clerk_user_id)
    payload = _analyze_payload(request, clerk_user_id)

    result = run_analysis_pipeline(payload)
    if not result.get("success", True):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                code="DATA_UNAVAILABLE",
                message=result.get("error", "Portfolio analysis failed"),
            ).model_dump(),
        )

    recommendation = result["recommendation"]
    return PortfolioAnalyzeResponse(
        **recommendation,
        portfolioReport=_parse_portfolio_report(result.get("portfolioReport")),
        validationReport=_parse_validation_report(result.get("validationReport")),
        analysisReport=_parse_analysis_report(result.get("analysisReport")),
        warnings=result.get("warnings", []),
    )


def _analyze_payload(request: PortfolioAnalyzeRequest, clerk_user_id: str) -> dict:
    return {
        "riskProfile": request.riskProfile,
        "investmentHorizon": request.investmentHorizon,
        "marketCondition": request.marketCondition,
        "portfolio": [h.model_dump() for h in request.portfolio],
        "candidates": [c.model_dump() for c in request.candidatePool],
        "strategyProfile": request.strategyProfile,
        "clerkUserId": clerk_user_id,
    }


@app.post("/api/portfolio/analyze/stream")
def portfolio_analyze_stream(
    request: PortfolioAnalyzeRequest,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Stream pipeline stages as NDJSON (one JSON object per line)."""
    _ensure_user(_db(), clerk_user_id)
    payload = _analyze_payload(request, clerk_user_id)

    return StreamingResponse(
        iter_analysis_stream(
            payload,
            parse_validation=_parse_validation_report,
            parse_analysis=_parse_analysis_report,
            parse_portfolio=_parse_portfolio_report,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/jobs/analyze")
def enqueue_analysis_job(
    request: PortfolioAnalyzeRequest,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Create an analysis_jobs row and enqueue SQS for async orchestration."""
    if not SQS_QUEUE_URL:
        raise HTTPException(
            status_code=501,
            detail=ErrorResponse(
                code="QUEUE_UNAVAILABLE",
                message="SQS_QUEUE_URL not configured. Use /api/portfolio/analyze for sync analysis.",
            ).model_dump(),
        )

    db = _db()
    _ensure_user(db, clerk_user_id)
    job_id = db.analysis_jobs.create_job(
        clerk_user_id,
        AnalysisJobCreate(
            request_payload={
                "riskProfile": request.riskProfile,
                "investmentHorizon": request.investmentHorizon,
                "strategyProfile": request.strategyProfile,
                "marketCondition": request.marketCondition,
                "portfolio": [h.model_dump() for h in request.portfolio],
                "candidates": [c.model_dump() for c in request.candidatePool],
            }
        ),
    )

    sqs_client.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=f'{{"jobId":"{job_id}"}}',
    )
    return {"jobId": job_id, "status": "pending"}


@app.get("/api/jobs/{job_id}")
def get_analysis_job(job_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    job = _db().analysis_jobs.find_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _verify_job_owner(job, clerk_user_id)
    return job


@app.post("/api/jobs/{job_id}/ask")
def ask_about_job(
    job_id: str,
    body: dict,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Follow-up Q&A on a completed analysis job."""
    from alphalens_shared.lambda_invoke import invoke_qa

    db = _db()
    job = db.analysis_jobs.find_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _verify_job_owner(job, clerk_user_id)

    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    result = invoke_qa(
        {"jobId": job_id, "question": question, "clerk_user_id": clerk_user_id}
    )
    if not result.get("success", True):
        raise HTTPException(status_code=400, detail=result.get("error", "Q&A failed"))
    return result


@app.post("/api/jobs/{job_id}/ask/stream")
def ask_about_job_stream(
    job_id: str,
    body: dict,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Stream Q&A answer tokens via Server-Sent Events."""
    db = _db()
    job = db.analysis_jobs.find_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _verify_job_owner(job, clerk_user_id)

    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    if job.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job status is {job.get('status')}; wait for analysis to complete",
        )

    return StreamingResponse(
        iter_qa_sse(job_id, question, clerk_user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
