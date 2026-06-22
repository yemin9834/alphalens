#!/usr/bin/env python3
"""Unit tests for analyst narrative guardrails."""

from alphalens_shared.services.analyst_report import (
    allowed_tickers,
    build_deterministic_report,
    validate_narrative,
)

RANKED_PAYLOAD = {
    "marketCondition": "Neutral",
    "rankedCandidates": [
        {
            "ticker": "TSM",
            "opportunityScore": 72.0,
            "rankReason": "Strong opportunity based on valuation cheap (score 72.0)",
        },
        {
            "ticker": "AVGO",
            "opportunityScore": 55.0,
            "rankReason": "Moderate opportunity (score 55.0)",
        },
    ],
}


def test_allowed_tickers():
    assert allowed_tickers(RANKED_PAYLOAD) == {"TSM", "AVGO"}


def test_validate_narrative_strips_unknown_tickers():
    report = {
        "executiveSummary": "Overview",
        "marketOverview": "Neutral market",
        "topOpportunities": [
            {"ticker": "TSM", "summary": "Leader with score 72"},
            {"ticker": "FAKE", "summary": "Should be removed"},
        ],
        "risksToWatch": [{"ticker": "AVGO", "summary": "Moderate score"}],
        "methodologyNote": "Deterministic",
    }
    sanitized, warnings = validate_narrative(report, RANKED_PAYLOAD)
    assert len(sanitized["topOpportunities"]) == 1
    assert sanitized["topOpportunities"][0]["ticker"] == "TSM"
    assert any("FAKE" in w for w in warnings)


def test_build_deterministic_report():
    result = {
        "marketCondition": "Neutral",
        "rankedPayload": RANKED_PAYLOAD,
        "rankedCandidates": [],
    }
    report = build_deterministic_report(result, "balanced")
    assert "Neutral" in report["executiveSummary"]
    assert report["topOpportunities"][0]["ticker"] == "TSM"
