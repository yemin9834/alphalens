"""Deterministic validation summaries and LLM narrative guardrails."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _ticker_count_phrase(count: int, kind: str) -> str:
    """Format counts as 'no unknown tickers', '1 unknown ticker', or '2 unknown tickers'."""
    if count == 0:
        return f"no {kind} tickers"
    if count == 1:
        return f"1 {kind} ticker"
    return f"{count} {kind} tickers"


def _issue_sentence(unknown_count: int, invalid_count: int) -> str:
    """Describe unknown/invalid counts with consistent grammar."""
    if unknown_count == 0 and invalid_count == 0:
        return (
            "There were no unknown and no invalid tickers, "
            "so every candidate in this set is usable for further analysis."
        )

    unknown_phrase = _ticker_count_phrase(unknown_count, "unknown")
    invalid_phrase = _ticker_count_phrase(invalid_count, "invalid")
    total_issues = unknown_count + invalid_count

    if total_issues == 1:
        if unknown_count == 1:
            return f"There was 1 unknown ticker and {invalid_phrase}."
        return f"There were {unknown_phrase} and 1 invalid ticker."

    return f"There were {unknown_phrase} and {invalid_phrase}."


def build_validation_executive_summary(rows: List[Dict[str, Any]]) -> str:
    """Single source of truth for validation executive-summary copy."""
    validated = [r for r in rows if r.get("tickerValidation") == "validated"]
    unknown = [r for r in rows if r.get("tickerValidation") == "unknown"]
    invalid = [r for r in rows if r.get("tickerValidation") == "invalid"]
    total = len(rows)
    validated_count = len(validated)
    unknown_count = len(unknown)
    invalid_count = len(invalid)

    if total == 0:
        return "No discovery candidates were submitted for validation."

    if validated_count == total:
        return (
            f"All {total} discovery candidates were validated. "
            f"{_issue_sentence(unknown_count, invalid_count)}"
        )

    return (
        f"{validated_count} of {total} discovery candidates were validated. "
        f"{_issue_sentence(unknown_count, invalid_count)}"
    )


def build_deterministic_validation_report(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a validation report from deterministic candidate rows."""
    rows = result.get("validatedCandidates") or []

    notes = []
    for row in rows[:12]:
        ticker = row.get("ticker", "")
        status = row.get("tickerValidation", "unknown")
        reason = row.get("validationReason") or "No reason recorded."
        if ticker:
            notes.append({"ticker": ticker, "summary": f"{status}: {reason}"})

    return {
        "executiveSummary": build_validation_executive_summary(rows),
        "candidateNotes": notes,
        "methodologyNote": (
            "Deterministic validation — regex, curated symbols, and optional yfinance "
            "market lookup. tickerValidation status is not from an LLM."
        ),
    }


def validate_validation_narrative(
    report: Dict[str, Any],
    validated_candidates: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:
    """Strip hallucinated tickers; never allow LLM to change validation status."""
    warnings: List[str] = []
    allowed = {str(r.get("ticker", "")).upper() for r in validated_candidates if r.get("ticker")}
    status_by_ticker = {
        str(r.get("ticker", "")).upper(): r.get("tickerValidation")
        for r in validated_candidates
        if r.get("ticker")
    }

    sanitized_notes = []
    for item in report.get("candidateNotes") or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).upper().strip()
        summary = str(item.get("summary", "")).strip()
        if not ticker or ticker not in allowed:
            warnings.append(f"Removed narrative note for unknown ticker: {ticker or '?'}")
            continue
        status = status_by_ticker.get(ticker, "unknown")
        sanitized_notes.append(
            {
                "ticker": ticker,
                "summary": summary,
                "tickerValidation": status,
            }
        )

    sanitized = {
        "executiveSummary": build_validation_executive_summary(validated_candidates),
        "candidateNotes": sanitized_notes,
        "methodologyNote": str(report.get("methodologyNote", "")).strip(),
    }
    return sanitized, warnings


def attach_validation_notes(
    result: Dict[str, Any],
    report: Dict[str, Any],
) -> None:
    """Merge per-ticker LLM notes onto validatedCandidates (text only)."""
    by_ticker = {
        str(item.get("ticker", "")).upper(): str(item.get("summary", "")).strip()
        for item in report.get("candidateNotes") or []
        if item.get("ticker")
    }
    for row in result.get("validatedCandidates") or []:
        ticker = str(row.get("ticker", "")).upper()
        note = by_ticker.get(ticker)
        if note:
            row["validationNote"] = note
    result["validationReport"] = report
