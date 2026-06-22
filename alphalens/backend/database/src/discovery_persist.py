"""
Persist discovery results to discovery_runs and candidates tables (Guide 4 Step 7).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from . import Database
from .schemas import CandidateCreate, DiscoveryRunCreate, UserCreate

logger = logging.getLogger(__name__)


def _db_configured() -> bool:
    return bool(os.getenv("AURORA_CLUSTER_ARN") and os.getenv("AURORA_SECRET_ARN"))


def _persistence_enabled() -> bool:
    return os.getenv("PERSIST_DISCOVERY_RUNS", "true").lower() != "false"


def _resolve_clerk_user_id(payload: Dict[str, Any]) -> Optional[str]:
    clerk_id = payload.get("clerkUserId") or payload.get("clerk_user_id")
    if clerk_id:
        return str(clerk_id).strip()
    return None


def _candidates_from_result(result: Dict[str, Any]) -> List[CandidateCreate]:
    rows: List[CandidateCreate] = []
    for c in result.get("candidates", []):
        rows.append(
            CandidateCreate(
                company_name=c.get("companyName", c.get("company_name", "")),
                ticker=c.get("ticker") or None,
                relationship_type=c.get("relationshipType", c.get("relationship_type", "")),
                relationship_summary=c.get(
                    "relationshipSummary", c.get("relationship_summary")
                ),
                confidence=c.get("confidence", "Medium"),
                evidence_url=c.get("evidenceUrl", c.get("evidence_url")),
                ticker_validation=c.get("tickerValidation", c.get("ticker_validation")),
                deep_research=c.get("deepResearch") or c.get("deep_research"),
            )
        )
    return rows


def persist_discovery_run(
    clerk_user_id: str,
    payload: Dict[str, Any],
    result: Dict[str, Any],
    *,
    db: Optional[Database] = None,
) -> Optional[str]:
    """
    Save a discovery result to Aurora.

    Returns discovery_run id, or None when persistence is skipped or fails.
    """
    if not clerk_user_id or not _persistence_enabled() or not _db_configured():
        return None

    if not result.get("success", True):
        return None

    database = db or Database()
    core_company = result.get("coreCompany", payload.get("coreCompany", ""))
    core_ticker = result.get("coreTicker", payload.get("coreTicker", ""))
    scope = payload.get("scope", "level-1")

    try:
        if not database.users.find_by_clerk_id(clerk_user_id):
            database.users.create_user(UserCreate(clerk_user_id=clerk_user_id))

        run_id = database.discovery_runs.create_run(
            clerk_user_id,
            DiscoveryRunCreate(
                core_company=core_company,
                core_ticker=str(core_ticker).upper(),
                scope=scope,
            ),
        )

        candidate_rows = _candidates_from_result(result)
        if candidate_rows:
            database.candidates.bulk_create(run_id, candidate_rows)

        database.discovery_runs.update_status(
            run_id,
            "completed",
            result_payload=result,
            warnings=result.get("warnings", []),
        )
        logger.info(
            "Persisted discovery run %s for %s (%s candidates)",
            run_id,
            clerk_user_id,
            len(candidate_rows),
        )
        return run_id
    except Exception:
        logger.exception("Failed to persist discovery run for %s", clerk_user_id)
        return None


def maybe_persist_discovery(
    payload: Dict[str, Any],
    result: Dict[str, Any],
    *,
    db: Optional[Database] = None,
) -> Dict[str, Any]:
    """Persist when clerk user id is present; attach discoveryRunId to result."""
    if result.get("discoveryRunId"):
        return result

    clerk_id = _resolve_clerk_user_id(payload)
    if not clerk_id:
        return result

    run_id = persist_discovery_run(clerk_id, payload, result, db=db)
    if run_id:
        result = dict(result)
        result["discoveryRunId"] = run_id
    return result
