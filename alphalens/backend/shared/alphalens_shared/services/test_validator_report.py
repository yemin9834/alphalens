#!/usr/bin/env python3
"""Unit tests for validator report and narrative guardrails."""

from alphalens_shared.services.validator_report import (
    build_deterministic_validation_report,
    build_validation_executive_summary,
    validate_validation_narrative,
)

VALIDATED_CANDIDATES = [
    {
        "ticker": "TSM",
        "tickerValidation": "validated",
        "validationReason": "Known symbol in AlphaLens curated/sector data.",
    },
    {
        "ticker": "FAKE2",
        "tickerValidation": "unknown",
        "validationReason": "Well-formed ticker but no reliable market data.",
    },
]


def test_build_deterministic_validation_report():
    result = {"validatedCandidates": VALIDATED_CANDIDATES}
    report = build_deterministic_validation_report(result)
    assert "1 of 2 discovery candidates were validated" in report["executiveSummary"]
    assert "1 unknown ticker" in report["executiveSummary"]
    assert "0 unknown" not in report["executiveSummary"]
    assert report["candidateNotes"][0]["ticker"] == "TSM"
    assert "not from an LLM" in report["methodologyNote"]


def test_all_validated_executive_summary():
    rows = [
        {"ticker": "NVDA", "tickerValidation": "validated"},
        {"ticker": "TSM", "tickerValidation": "validated"},
    ]
    summary = build_validation_executive_summary(rows)
    assert summary.startswith("All 2 discovery candidates were validated.")
    assert "no unknown and no invalid tickers" in summary
    assert "0 unknown" not in summary


def test_validate_narrative_strips_unknown_tickers():
    report = {
        "executiveSummary": "All 2 candidates were validated. There were 0 unknown tickers.",
        "candidateNotes": [
            {"ticker": "TSM", "summary": "Validated supplier name."},
            {"ticker": "HALLUCINATED", "summary": "Should be removed"},
        ],
        "methodologyNote": "LLM notes only.",
    }
    sanitized, warnings = validate_validation_narrative(report, VALIDATED_CANDIDATES)
    assert "0 unknown" not in sanitized["executiveSummary"]
    assert "1 of 2 discovery candidates were validated" in sanitized["executiveSummary"]
    assert len(sanitized["candidateNotes"]) == 1
    assert sanitized["candidateNotes"][0]["ticker"] == "TSM"
    assert sanitized["candidateNotes"][0]["tickerValidation"] == "validated"
    assert any("HALLUCINATED" in w for w in warnings)
