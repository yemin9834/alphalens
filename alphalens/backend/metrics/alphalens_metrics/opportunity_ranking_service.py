"""Opportunity ranking — design-doc.md §Step 12."""

from __future__ import annotations

from typing import Any, Dict, List

from alphalens_metrics.market_metric_engine import MarketMetricEngine
from alphalens_metrics.market_regime_service import MarketRegimeService


class OpportunityRankingService:
    """Rank validated candidates by opportunity score."""

    def __init__(self) -> None:
        self.metrics = MarketMetricEngine()
        self.regime = MarketRegimeService()

    def rank(
        self,
        candidates: List[Dict[str, Any]],
        risk_profile: str = "balanced",
        market_condition: str | None = None,
    ) -> Dict[str, Any]:
        condition = market_condition or self.regime.get_market_condition()
        scored: List[Dict[str, Any]] = []

        for candidate in candidates:
            ticker = candidate.get("ticker", "").upper()
            if not ticker or ticker == "CASH":
                continue

            metrics = self.metrics.get_stock_metrics(ticker)
            score = self._score(metrics, risk_profile, condition)
            scored.append(
                {
                    **candidate,
                    "companyName": metrics.get("companyName", candidate.get("companyName", ticker)),
                    "metrics": metrics,
                    "opportunityScore": score,
                    "rankReason": self._reason(metrics, score),
                }
            )

        scored.sort(key=lambda x: x["opportunityScore"], reverse=True)
        for idx, row in enumerate(scored, start=1):
            row["rank"] = idx

        return {
            "marketCondition": condition,
            "rankedCandidates": scored,
        }

    def _score(self, metrics: Dict[str, Any], risk_profile: str, condition: str) -> float:
        score = 50.0

        valuation = metrics.get("valuation", "Unknown")
        if valuation == "Cheap":
            score += 15
        elif valuation == "Fair":
            score += 8
        elif valuation == "Expensive":
            score -= 10

        momentum = metrics.get("momentum", "Unknown")
        if momentum == "Positive":
            score += 12
        elif momentum == "Negative":
            score -= 15

        attractiveness = metrics.get("entryAttractiveness", "Unknown")
        if attractiveness == "High":
            score += 10
        elif attractiveness == "Low":
            score -= 5

        vol = metrics.get("volatilityRisk", "Unknown")
        if risk_profile == "conservative" and vol == "High":
            score -= 12
        if risk_profile == "aggressive" and vol == "High":
            score += 3

        if condition == "Risk-off":
            score -= 8
        elif condition == "Favorable":
            score += 5

        return round(max(0, min(100, score)), 1)

    @staticmethod
    def _reason(metrics: Dict[str, Any], score: float) -> str:
        parts = []
        if metrics.get("valuation") not in ("Unknown", None):
            parts.append(f"valuation {metrics['valuation'].lower()}")
        if metrics.get("momentum") not in ("Unknown", None):
            parts.append(f"momentum {metrics['momentum'].lower()}")
        if metrics.get("entryAttractiveness") not in ("Unknown", None):
            parts.append(f"entry attractiveness {metrics['entryAttractiveness'].lower()}")
        if not parts:
            return "Limited market data available"
        return "Strong opportunity based on " + ", ".join(parts) + f" (score {score})"
