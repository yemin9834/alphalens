#!/usr/bin/env python3
"""Tests for discovery run persistence helpers."""

from unittest.mock import MagicMock, patch

from src.discovery_persist import maybe_persist_discovery, persist_discovery_run


def test_maybe_persist_skips_without_clerk_user():
    result = {"success": True, "candidates": [], "warnings": []}
    out = maybe_persist_discovery({"coreTicker": "NVDA"}, result)
    assert out == result
    assert "discoveryRunId" not in out


def test_maybe_persist_skips_when_already_persisted():
    result = {"success": True, "discoveryRunId": "existing-id", "candidates": []}
    payload = {"clerkUserId": "user_123"}
    out = maybe_persist_discovery(payload, result)
    assert out["discoveryRunId"] == "existing-id"


@patch.dict(
    "os.environ",
    {
        "PERSIST_DISCOVERY_RUNS": "true",
        "AURORA_CLUSTER_ARN": "arn:cluster",
        "AURORA_SECRET_ARN": "arn:secret",
    },
    clear=False,
)
@patch("src.discovery_persist.Database")
def test_persist_discovery_run_writes_rows(mock_db_cls):
    mock_db = MagicMock()
    mock_db_cls.return_value = mock_db
    mock_db.users.find_by_clerk_id.return_value = {"clerk_user_id": "user_123"}
    mock_db.discovery_runs.create_run.return_value = "run-uuid-1"

    result = {
        "success": True,
        "coreCompany": "NVIDIA",
        "coreTicker": "NVDA",
        "candidates": [
            {
                "companyName": "TSMC",
                "ticker": "TSM",
                "relationshipType": "supplier",
                "relationshipSummary": "Fab partner",
                "confidence": "High",
                "evidenceUrl": "https://example.com",
                "tickerValidation": "unknown",
            }
        ],
        "warnings": [],
    }

    run_id = persist_discovery_run(
        "user_123",
        {"coreCompany": "NVIDIA", "coreTicker": "NVDA", "scope": "level-1"},
        result,
        db=mock_db,
    )

    assert run_id == "run-uuid-1"
    mock_db.discovery_runs.create_run.assert_called_once()
    mock_db.candidates.bulk_create.assert_called_once()
    mock_db.discovery_runs.update_status.assert_called_once_with(
        "run-uuid-1",
        "completed",
        result_payload=result,
        warnings=[],
    )
