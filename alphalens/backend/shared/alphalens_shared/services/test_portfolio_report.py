#!/usr/bin/env python3
"""Unit tests for portfolio narrative guardrails."""

from alphalens_shared.services.portfolio_report import (
    build_deterministic_portfolio_report,
    validate_portfolio_narrative,
)

RECOMMENDATION = {
    "finalView": "Balanced add to TSM while trimming cash.",
    "riskLevel": "Medium",
    "marketCondition": "Neutral",
    "portfolioSignals": {
        "concentrationRisk": "Moderate",
        "sectorExposure": "Technology-heavy",
        "cashBuffer": "Adequate",
        "volatilityRisk": "Medium",
    },
    "actions": [
        {"type": "Add", "ticker": "TSM", "amount": 5.0, "reason": "Top-ranked supplier"},
        {"type": "Trim", "ticker": "CASH", "amount": 5.0, "reason": "Fund new position"},
    ],
    "candidateRecommendations": [
        {
            "ticker": "TSM",
            "view": "Attractive",
            "portfolioFit": "Strong fit — consider adding",
            "positionSizingGuidance": "Add toward 10%",
        }
    ],
}


def test_build_deterministic_portfolio_report():
    report = build_deterministic_portfolio_report({"recommendation": RECOMMENDATION})
    assert "Balanced add" in report["executiveSummary"]
    assert report["actionNotes"][0]["ticker"] == "TSM"
    assert "not from an LLM" in report["methodologyNote"]


def test_validate_narrative_strips_unknown_actions():
    report = {
        "executiveSummary": "Portfolio overview.",
        "actionNotes": [
            {"ticker": "TSM", "type": "Add", "summary": "Supplier exposure improves diversification."},
            {"ticker": "FAKE", "type": "Add", "summary": "Should be removed"},
        ],
        "candidateNotes": [{"ticker": "TSM", "summary": "Strong ranked name."}],
        "methodologyNote": "LLM notes only.",
        "portfolioSignalsSummary": "Moderate concentration.",
    }
    sanitized, warnings = validate_portfolio_narrative(report, RECOMMENDATION)
    assert len(sanitized["actionNotes"]) == 1
    assert sanitized["actionNotes"][0]["ticker"] == "TSM"
    assert any("FAKE" in w for w in warnings)
