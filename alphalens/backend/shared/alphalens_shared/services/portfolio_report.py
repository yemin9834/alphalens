"""Deterministic portfolio summaries and LLM narrative guardrails."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


def _recommendation(result: Dict[str, Any]) -> Dict[str, Any]:
    return result.get("recommendation") or {}


def allowed_action_keys(recommendation: Dict[str, Any]) -> Set[tuple[str, str]]:
    keys: Set[tuple[str, str]] = set()
    for action in recommendation.get("actions", []):
        ticker = str(action.get("ticker", "")).upper().strip()
        action_type = str(action.get("type", "")).upper().strip()
        if ticker and action_type:
            keys.add((ticker, action_type))
    return keys


def allowed_candidate_tickers(recommendation: Dict[str, Any]) -> Set[str]:
    tickers: Set[str] = set()
    for row in recommendation.get("candidateRecommendations", []):
        ticker = str(row.get("ticker", "")).upper().strip()
        if ticker:
            tickers.add(ticker)
    return tickers


def build_deterministic_portfolio_report(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a portfolio report from deterministic recommendation rows."""
    rec = _recommendation(result)
    actions = rec.get("actions") or []
    candidates = rec.get("candidateRecommendations") or []

    action_notes = []
    for action in actions[:12]:
        ticker = action.get("ticker", "")
        action_type = action.get("type", "Hold")
        reason = action.get("reason") or "No rationale recorded."
        if ticker:
            action_notes.append(
                {
                    "ticker": ticker,
                    "type": action_type,
                    "summary": f"{action_type} {ticker}: {reason}",
                }
            )

    candidate_notes = []
    for row in candidates[:12]:
        ticker = row.get("ticker", "")
        if not ticker:
            continue
        candidate_notes.append(
            {
                "ticker": ticker,
                "summary": (
                    f"{row.get('view', 'Neutral')} — {row.get('portfolioFit', '')}. "
                    f"{row.get('positionSizingGuidance', '')}"
                ).strip(),
            }
        )

    signals = rec.get("portfolioSignals") or {}
    summary = rec.get("finalView") or "Portfolio recommendation generated from deterministic risk engine."
    risk = rec.get("riskLevel", "Unknown")
    market = rec.get("marketCondition", "Neutral")

    return {
        "executiveSummary": (
            f"{summary} Risk level: {risk}. Market: {market}. "
            f"{len(actions)} action(s) across {len(candidates)} ranked candidate(s)."
        ),
        "actionNotes": action_notes,
        "candidateNotes": candidate_notes,
        "methodologyNote": (
            "Deterministic portfolio plan — ActionPlanService and PortfolioRiskEngine. "
            "Add/Trim/Hold actions and weights are not from an LLM."
        ),
        "portfolioSignalsSummary": (
            f"Concentration: {signals.get('concentrationRisk', 'Unknown')}; "
            f"sector exposure: {signals.get('sectorExposure', 'Unknown')}; "
            f"cash buffer: {signals.get('cashBuffer', 'Unknown')}."
        ),
    }


def validate_portfolio_narrative(
    report: Dict[str, Any],
    recommendation: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Strip hallucinated tickers/actions; never allow LLM to change action types."""
    warnings: List[str] = []
    allowed_actions = allowed_action_keys(recommendation)
    allowed_candidates = allowed_candidate_tickers(recommendation)

    sanitized_actions = []
    for item in report.get("actionNotes") or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).upper().strip()
        action_type = str(item.get("type", "")).upper().strip()
        summary = str(item.get("summary", "")).strip()
        key = (ticker, action_type)
        if not ticker or key not in allowed_actions:
            warnings.append(
                f"Removed narrative action note for unknown action: {ticker or '?'} {action_type or '?'}"
            )
            continue
        sanitized_actions.append(
            {"ticker": ticker, "type": action_type, "summary": summary}
        )

    sanitized_candidates = []
    for item in report.get("candidateNotes") or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).upper().strip()
        summary = str(item.get("summary", "")).strip()
        if not ticker or ticker not in allowed_candidates:
            warnings.append(f"Removed narrative candidate note for unknown ticker: {ticker or '?'}")
            continue
        sanitized_candidates.append({"ticker": ticker, "summary": summary})

    sanitized = {
        "executiveSummary": str(report.get("executiveSummary", "")).strip(),
        "actionNotes": sanitized_actions,
        "candidateNotes": sanitized_candidates,
        "methodologyNote": str(report.get("methodologyNote", "")).strip(),
        "portfolioSignalsSummary": str(report.get("portfolioSignalsSummary", "")).strip(),
    }
    if not sanitized["executiveSummary"]:
        sanitized["executiveSummary"] = build_deterministic_portfolio_report(
            {"recommendation": recommendation}
        )["executiveSummary"]
    if not sanitized["portfolioSignalsSummary"]:
        sanitized["portfolioSignalsSummary"] = build_deterministic_portfolio_report(
            {"recommendation": recommendation}
        )["portfolioSignalsSummary"]
    return sanitized, warnings


def attach_portfolio_narrative(result: Dict[str, Any], report: Dict[str, Any]) -> None:
    """Merge LLM narrative onto recommendation (text only — actions unchanged)."""
    rec = result.get("recommendation") or {}
    if report.get("executiveSummary"):
        rec["finalView"] = report["executiveSummary"]

    action_notes = {
        (str(item.get("ticker", "")).upper(), str(item.get("type", "")).upper()): str(
            item.get("summary", "")
        ).strip()
        for item in report.get("actionNotes") or []
        if item.get("ticker") and item.get("type")
    }
    for action in rec.get("actions") or []:
        key = (str(action.get("ticker", "")).upper(), str(action.get("type", "")).upper())
        note = action_notes.get(key)
        if note:
            action["narrativeReason"] = note

    candidate_notes = {
        str(item.get("ticker", "")).upper(): str(item.get("summary", "")).strip()
        for item in report.get("candidateNotes") or []
        if item.get("ticker")
    }
    for row in rec.get("candidateRecommendations") or []:
        ticker = str(row.get("ticker", "")).upper()
        note = candidate_notes.get(ticker)
        if note:
            row["fitNote"] = note

    result["portfolioReport"] = report
    result["recommendation"] = rec
    payload = result.get("recommendationPayload")
    if isinstance(payload, dict):
        payload["portfolioReport"] = report
