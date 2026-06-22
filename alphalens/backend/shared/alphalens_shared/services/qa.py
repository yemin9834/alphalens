"""Q&A service — deterministic follow-up answers from completed jobs."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def run_qa(payload: Dict[str, Any]) -> Dict[str, Any]:
    job_id = payload.get("jobId") or payload.get("job_id")
    question = (payload.get("question") or "").strip()
    if not job_id:
        return {"success": False, "error": "jobId is required"}
    if not question:
        return {"success": False, "error": "question is required"}

    job = _load_job(job_id, payload.get("clerk_user_id"))
    if not job:
        return {"success": False, "error": f"Job {job_id} not found"}
    if job.get("status") != "completed":
        return {
            "success": False,
            "error": f"Job status is {job.get('status')}; wait for analysis to complete",
        }

    return {
        "success": True,
        "jobId": job_id,
        "question": question,
        "answer": _answer_from_job(job, question),
    }


def _load_job(job_id: str, clerk_user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    from src import Database

    db = Database(
        cluster_arn=os.environ.get("AURORA_CLUSTER_ARN"),
        secret_arn=os.environ.get("AURORA_SECRET_ARN"),
        database=os.environ.get("DATABASE_NAME", "alphalens"),
        region=os.environ.get("DEFAULT_AWS_REGION", os.environ.get("AWS_REGION", "us-east-1")),
    )
    job = db.analysis_jobs.find_by_id(job_id)
    if not job:
        return None
    if clerk_user_id and job.get("clerk_user_id") != clerk_user_id:
        return None
    return job


def _job_context(job: Dict[str, Any]) -> Dict[str, Any]:
    rec = job.get("recommendation_payload") or {}
    ranked = job.get("ranked_payload") or {}
    if isinstance(rec, str):
        rec = json.loads(rec)
    if isinstance(ranked, str):
        ranked = json.loads(ranked)
    return {
        "jobId": job.get("id"),
        "status": job.get("status"),
        "recommendation": rec,
        "ranked": ranked,
    }


def _answer_from_job(job: Dict[str, Any], question: str) -> str:
    rec = _job_context(job)["recommendation"]
    q = question.lower()
    summary = rec.get("summary") or rec.get("finalView") or "No summary available."
    actions: List[Dict[str, Any]] = rec.get("actions") or []
    risk = rec.get("portfolioRisk") or rec.get("portfolioSignals") or {}

    if any(word in q for word in ("risk", "concentration", "exposure")):
        if isinstance(risk, dict) and risk.get("riskLevel"):
            return (
                f"Portfolio risk level is {risk.get('riskLevel')}. "
                f"Concentration: {risk.get('concentrationRisk', 'Unknown')}. "
                f"Sector exposure: {risk.get('sectorExposure', 'Unknown')}."
            )
        signals = rec.get("portfolioSignals") or {}
        return (
            f"Portfolio signals — concentration: {signals.get('concentrationRisk', 'Unknown')}, "
            f"sector exposure: {signals.get('sectorExposure', 'Unknown')}, "
            f"cash buffer: {signals.get('cashBuffer', 'Unknown')}."
        )

    if any(word in q for word in ("action", "buy", "sell", "add", "trim", "hold")):
        if not actions:
            return "No specific actions were recommended for this analysis."
        lines = [
            f"{a.get('action', a.get('type', 'Review'))} {a.get('ticker')}: {a.get('rationale', a.get('reason', ''))}"
            for a in actions[:5]
        ]
        return "Recommended actions:\n" + "\n".join(f"• {line}" for line in lines)

    if any(word in q for word in ("summary", "overview", "view")):
        return summary

    if "market" in q:
        return f"Market condition at analysis time: {rec.get('marketCondition', 'Unknown')}. {summary}"

    return f"{summary}\n\nAsk about risk, recommended actions, or market condition for more detail."
