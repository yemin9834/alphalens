"""Process analysis_jobs rows from the database."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv

from agent import run as run_pipeline
from alphalens_shared.services.pipeline import run_analysis_pipeline
from job_stages import JobStagePersister, get_job_database, make_stage_callback, merge_ranked

load_dotenv(override=True)
logger = logging.getLogger(__name__)


def _run_staged_pipeline(request: Dict[str, Any], job_id: str, db) -> Dict[str, Any]:
    """Run pipeline with per-stage DB persistence (async job progressive results)."""
    persister = JobStagePersister(job_id, db)
    return run_analysis_pipeline(request, on_stage=make_stage_callback(persister))


def process_job(job_id: str) -> Dict[str, Any]:
    db = get_job_database()

    job = db.analysis_jobs.find_by_id(job_id)
    if not job:
        return {"success": False, "error": f"Job {job_id} not found"}

    db.analysis_jobs.update_status(job_id, "running")
    request = dict(job.get("request_payload") or {})
    if job.get("clerk_user_id"):
        request.setdefault("clerkUserId", job["clerk_user_id"])

    # Async jobs persist incrementally via _jobId (deterministic pipeline + LLM tools).
    request["_jobId"] = job_id

    candidates = request.get("candidates")
    if candidates:
        JobStagePersister(job_id, db).persist(
            "discovery",
            {"skipped": True, "candidateCount": len(candidates)},
        )

    use_llm_orchestration = os.getenv("USE_LLM_ORCHESTRATION", "false").lower() == "true"

    try:
        if use_llm_orchestration:
            result = run_pipeline(request)
        else:
            result = _run_staged_pipeline(request, job_id, db)

        if not result.get("success", True):
            db.analysis_jobs.update_status(
                job_id, "failed", error_message=result.get("error", "Pipeline failed")
            )
            return result

        # Finalize — incremental stages already written; fill any gaps for LLM path.
        if use_llm_orchestration:
            persister = JobStagePersister(job_id, db)
            if result.get("discoveryRunId"):
                db.analysis_jobs.update_discovery_run(job_id, result["discoveryRunId"])
            if result.get("validationReport"):
                persister.persist(
                    "validation",
                    {
                        "validationReport": result.get("validationReport"),
                        "validatedCandidates": result.get("validatedCandidates", []),
                        "warnings": result.get("warnings", []),
                    },
                )
            if result.get("analysisReport") or result.get("rankedCandidates"):
                persister.persist(
                    "analysis",
                    {
                        "analysisReport": result.get("analysisReport"),
                        "rankedCandidates": result.get("rankedCandidates", []),
                        "rankedPayload": result.get("rankedPayload"),
                        "marketCondition": (result.get("rankedPayload") or {}).get(
                            "marketCondition"
                        ),
                        "warnings": result.get("warnings", []),
                    },
                )
            recommendation_record = result.get("recommendation") or result.get(
                "recommendationPayload"
            )
            if recommendation_record:
                persister.persist(
                    "portfolio",
                    {
                        "recommendation": recommendation_record,
                        "portfolioReport": result.get("portfolioReport"),
                        "warnings": result.get("warnings", []),
                    },
                )

        merge_ranked(db, job_id, {"pipelineStage": "completed"})
        db.analysis_jobs.update_status(job_id, "completed")
        return {"success": True, "jobId": job_id, "recommendation": result.get("recommendation")}
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        db.analysis_jobs.update_status(job_id, "failed", error_message=str(exc))
        return {"success": False, "error": str(exc)}
