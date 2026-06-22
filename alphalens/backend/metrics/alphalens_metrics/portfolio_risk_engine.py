"""Portfolio risk analysis — design-doc.md §Step 8."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _load_sector_mapping() -> Dict[str, str]:
    candidates = [
        Path(__file__).resolve().parents[2] / "shared" / "data" / "sector_mapping.json",
        Path(__file__).resolve().parents[2] / ".." / "shared" / "data" / "sector_mapping.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


CASH_THRESHOLDS: Dict[str, tuple[float, float]] = {
    "conservative": (10, 25),
    "balanced": (5, 20),
    "aggressive": (2, 15),
}


class PortfolioRiskEngine:
    """Compute concentration, sector exposure, cash buffer, volatility risk."""

    def __init__(self) -> None:
        self.sector_mapping = _load_sector_mapping()

    @staticmethod
    def cash_thresholds(risk_profile: str) -> tuple[float, float]:
        return CASH_THRESHOLDS.get(risk_profile, CASH_THRESHOLDS["balanced"])

    def analyze(self, portfolio: List[Dict[str, Any]], risk_profile: str) -> Dict[str, Any]:
        weights = {p["ticker"].upper(): float(p["weight"]) for p in portfolio}
        total = sum(weights.values())
        if total <= 0:
            return self._empty_risk()

        normalized = {k: v / total * 100 for k, v in weights.items()}
        sorted_weights = sorted(normalized.values(), reverse=True)
        top1 = sorted_weights[0]
        top3 = sum(sorted_weights[:3])

        concentration = "Low"
        if top1 > 35 or top3 > 75:
            concentration = "High"
        elif top1 > 20 or top3 > 50:
            concentration = "Medium"

        sectors: Dict[str, float] = {}
        for ticker, weight in normalized.items():
            sector = self.sector_mapping.get(ticker, "Unknown")
            sectors[sector] = sectors.get(sector, 0) + weight
        max_sector = max(sectors.values()) if sectors else 0
        if max_sector > 60:
            sector_exposure = "High"
        elif max_sector > 40:
            sector_exposure = "Medium"
        else:
            sector_exposure = "Low"

        cash = normalized.get("CASH", 0)
        cash_buffer = self._cash_buffer(cash, risk_profile)

        risk_level = "Medium"
        if concentration == "High" or sector_exposure == "High":
            risk_level = "High"
        elif concentration == "Low" and sector_exposure == "Low":
            risk_level = "Low"

        return {
            "concentrationRisk": concentration,
            "sectorExposure": sector_exposure,
            "cashBuffer": cash_buffer,
            "volatilityRisk": "Unknown",
            "riskLevel": risk_level,
            "sectorBreakdown": sectors,
        }

    @staticmethod
    def _cash_buffer(cash_pct: float, risk_profile: str) -> str:
        low, high = PortfolioRiskEngine.cash_thresholds(risk_profile)
        if cash_pct < low:
            return "Low"
        if cash_pct <= high:
            return "Acceptable"
        return "High"

    @staticmethod
    def _empty_risk() -> Dict[str, Any]:
        return {
            "concentrationRisk": "Unknown",
            "sectorExposure": "Unknown",
            "cashBuffer": "Unknown",
            "volatilityRisk": "Unknown",
            "riskLevel": "Unknown",
            "sectorBreakdown": {},
        }
