"""Optional discovery persistence when alphalens-database is available."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def maybe_persist_discovery(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persist discovery_runs + candidates when clerk user id and Aurora are configured.

    No-op when the database package is not installed (slim discovery Lambda zip).
    """
    try:
        from src.discovery_persist import maybe_persist_discovery as _persist
    except ImportError:
        return result

    try:
        return _persist(payload, result)
    except Exception:
        logger.exception("Discovery persistence failed")
        return result


def persist_discovery_run(
    clerk_user_id: str,
    payload: Dict[str, Any],
    result: Dict[str, Any],
) -> Optional[str]:
    """Persist explicitly for API handlers that already know the clerk user id."""
    enriched = dict(payload)
    enriched.setdefault("clerkUserId", clerk_user_id)
    out = maybe_persist_discovery(enriched, result)
    return out.get("discoveryRunId")
