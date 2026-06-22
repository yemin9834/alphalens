"""Analyst narrative guardrails and deterministic report (no LLM)."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


def allowed_tickers(ranked_payload: Dict[str, Any]) -> Set[str]:
    tickers: Set[str] = set()
    for row in ranked_payload.get("rankedCandidates", []):
        ticker = (row.get("ticker") or "").strip().upper()
        if ticker:
            tickers.add(ticker)
    return tickers


def _score_by_ticker(ranked_payload: Dict[str, Any]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for row in ranked_payload.get("rankedCandidates", []):
        ticker = (row.get("ticker") or "").strip().upper()
        score = row.get("opportunityScore")
        if ticker and score is not None:
            scores[ticker] = float(score)
    return scores


def _filter_insights(
    insights: List[Dict[str, Any]],
    allowed: Set[str],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    kept: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for item in insights:
        ticker = (item.get("ticker") or "").strip().upper()
        if ticker in allowed:
            kept.append({**item, "ticker": ticker})
        elif ticker:
            warnings.append(f"Removed narrative mention of unknown ticker {ticker}")
    return kept, warnings


def validate_narrative(
    report: Dict[str, Any],
    ranked_payload: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Sanitize LLM narrative against deterministic rankedPayload."""
    allowed = allowed_tickers(ranked_payload)
    scores = _score_by_ticker(ranked_payload)
    warnings: List[str] = []

    if not allowed:
        warnings.append("No ranked candidates available for narrative validation")
        return report, warnings

    sanitized = dict(report)
    for field in ("topOpportunities", "risksToWatch"):
        filtered, field_warnings = _filter_insights(sanitized.get(field, []), allowed)
        sanitized[field] = filtered
        warnings.extend(field_warnings)

    for item in sanitized.get("topOpportunities", []):
        ticker = item.get("ticker", "")
        summary = (item.get("summary") or "").lower()
        score = scores.get(ticker)
        if score is not None and str(int(score)) not in summary and str(score) not in summary:
            item["summary"] = f"{item['summary']} (opportunity score {score} from metrics engine.)"

    sanitized.setdefault(
        "methodologyNote",
        "Rankings and scores are produced by deterministic metrics; this narrative summarizes that output only.",
    )
    return sanitized, warnings


def build_deterministic_report(
    result: Dict[str, Any],
    risk_profile: str = "balanced",
) -> Dict[str, Any]:
    """Fallback report from rankedPayload only."""
    ranked_payload = result.get("rankedPayload") or {}
    ranked = ranked_payload.get("rankedCandidates") or result.get("rankedCandidates") or []
    market = ranked_payload.get("marketCondition") or result.get("marketCondition", "Neutral")

    top = []
    risks = []
    for row in ranked[:3]:
        ticker = row.get("ticker", "")
        top.append(
            {
                "ticker": ticker,
                "summary": row.get("rankReason")
                or row.get("attractiveEntryReason")
                or f"{ticker} ranked with opportunity score {row.get('opportunityScore', 'N/A')}.",
            }
        )
    for row in ranked[-2:]:
        if row.get("opportunityScore", 100) < 50:
            risks.append(
                {
                    "ticker": row.get("ticker", ""),
                    "summary": row.get("rankReason") or "Lower opportunity score versus peers.",
                }
            )

    summary_parts = [
        f"Market condition: {market}.",
        f"Risk profile: {risk_profile}.",
        f"Ranked {len(ranked)} candidates using deterministic valuation, momentum, and volatility metrics.",
    ]
    if top:
        leaders = ", ".join(f"{i['ticker']}" for i in top[:3])
        summary_parts.append(f"Top names by score: {leaders}.")

    return {
        "executiveSummary": " ".join(summary_parts),
        "marketOverview": f"Current regime assessed as {market} for a {risk_profile} investor.",
        "topOpportunities": top,
        "risksToWatch": risks,
        "methodologyNote": "Deterministic summary from OpportunityRankingService — no LLM narrative.",
    }


def attach_analysis_report(result: Dict[str, Any], risk_profile: str = "balanced") -> Dict[str, Any]:
    """Attach deterministic analysisReport to an analyst result dict."""
    report = build_deterministic_report(result, risk_profile)
    result["analysisReport"] = report
    ranked_payload = result.get("rankedPayload")
    if isinstance(ranked_payload, dict):
        ranked_payload["analysisReport"] = report
    return result
