"""Incremental analysis_jobs persistence for progressive async job UI."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from src import Database

load_dotenv(override=True)
logger = logging.getLogger(__name__)


def get_job_database() -> Database:
    return Database(
        cluster_arn=os.environ.get("AURORA_CLUSTER_ARN"),
        secret_arn=os.environ.get("AURORA_SECRET_ARN"),
        database=os.environ.get("DATABASE_NAME", "alphalens"),
        region=os.environ.get("DEFAULT_AWS_REGION", os.environ.get("AWS_REGION", "us-east-1")),
    )


def merge_ranked(db: Database, job_id: str, patch: Dict[str, Any]) -> None:
    job = db.analysis_jobs.find_by_id(job_id)
    existing = dict(job.get("ranked_payload") or {}) if job else {}
    existing.update(patch)
    db.analysis_jobs.update_ranked(job_id, existing)


class JobStagePersister:
    """Write partial pipeline output after each stage (async jobs)."""

    def __init__(self, job_id: str, db: Optional[Database] = None) -> None:
        self.job_id = job_id
        self.db = db or get_job_database()
        self.warnings_acc: List[str] = []

    def persist(self, stage: str, data: Dict[str, Any]) -> None:
        new_warnings = data.get("newWarnings") or data.get("warnings") or []
        if new_warnings:
            self.warnings_acc = [*self.warnings_acc, *new_warnings]

        if stage == "discovery":
            if data.get("discoveryRunId"):
                self.db.analysis_jobs.update_discovery_run(self.job_id, data["discoveryRunId"])
            merge_ranked(
                self.db,
                self.job_id,
                {
                    "pipelineStage": "discovery",
                    "warnings": self.warnings_acc,
                    "discoverySkipped": bool(data.get("skipped")),
                    "candidateCount": data.get("candidateCount"),
                },
            )
        elif stage == "validation":
            merge_ranked(
                self.db,
                self.job_id,
                {
                    "pipelineStage": "validation",
                    "validationReport": data.get("validationReport"),
                    "validatedCandidates": data.get("validatedCandidates"),
                    "warnings": self.warnings_acc,
                },
            )
        elif stage == "analysis":
            patch: Dict[str, Any] = {
                "pipelineStage": "analysis",
                "warnings": self.warnings_acc,
            }
            if data.get("analysisReport"):
                patch["analysisReport"] = data["analysisReport"]
            if data.get("rankedCandidates"):
                patch["rankedCandidates"] = data["rankedCandidates"]
            if data.get("marketCondition"):
                patch["marketCondition"] = data["marketCondition"]
            inner = data.get("rankedPayload")
            if isinstance(inner, dict):
                patch["rankedPayload"] = inner
            merge_ranked(self.db, self.job_id, patch)
        elif stage == "portfolio":
            recommendation_record = data.get("recommendation") or data.get(
                "recommendationPayload"
            )
            if recommendation_record:
                record = dict(recommendation_record)
                if data.get("portfolioReport"):
                    record["portfolioReport"] = data["portfolioReport"]
                self.db.analysis_jobs.update_recommendation(self.job_id, record)
            merge_ranked(
                self.db,
                self.job_id,
                {
                    "pipelineStage": "portfolio",
                    "warnings": self.warnings_acc,
                },
            )
        else:
            logger.warning("Unknown job stage %s for job %s", stage, self.job_id)
            return

        logger.info("Job %s persisted stage=%s", self.job_id, stage)


def make_stage_callback(persister: JobStagePersister):
    """Adapter for run_analysis_pipeline(on_stage=...)."""

    def on_stage(stage: str, data: Dict[str, Any]) -> None:
        persister.persist(stage, data)

    return on_stage
