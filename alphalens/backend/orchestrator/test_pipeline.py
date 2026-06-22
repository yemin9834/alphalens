"""Pytest suite for orchestrator pipeline (no AWS)."""

import os

import pytest

os.environ["MOCK_LAMBDAS"] = "true"

from alphalens_shared.services.pipeline import run_analysis_pipeline


@pytest.fixture
def sample_portfolio():
    return [
        {"ticker": "NVDA", "weight": 35},
        {"ticker": "MSFT", "weight": 25},
        {"ticker": "CASH", "weight": 40},
    ]


def test_full_pipeline(sample_portfolio):
    result = run_analysis_pipeline(
        {
            "riskProfile": "balanced",
            "portfolio": sample_portfolio,
            "coreTicker": "NVDA",
            "coreCompany": "NVIDIA",
        }
    )
    assert result["success"] is True
    assert result["rankedCandidates"]
    assert result["recommendation"]["riskLevel"] in ("Low", "Medium", "High", "Unknown")


def test_pipeline_with_explicit_candidates(sample_portfolio):
    candidates = [
        {
            "companyName": "Taiwan Semiconductor",
            "ticker": "TSM",
            "relationshipType": "supplier",
            "relationshipSummary": "Chip manufacturing partner",
            "confidence": "High",
            "evidenceUrl": "demo",
            "tickerValidation": "validated",
        }
    ]
    result = run_analysis_pipeline(
        {
            "riskProfile": "balanced",
            "portfolio": sample_portfolio,
            "candidates": candidates,
        }
    )
    assert result["success"] is True
    assert any(c["ticker"] == "TSM" for c in result["rankedCandidates"])
