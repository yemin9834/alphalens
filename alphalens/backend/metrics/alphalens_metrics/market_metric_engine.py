"""
Stock-level signal analysis — design-doc.md §Step 10.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CASH_TICKER = "CASH"


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


class MarketMetricEngine:
    """Compute valuation, momentum, volatility, and related signals per ticker."""

    def get_stock_metrics(self, ticker: str) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        if ticker == CASH_TICKER:
            return {
                "ticker": ticker,
                "companyName": "Cash",
                "valuation": "Unknown",
                "momentum": "Neutral",
                "entryAttractiveness": "Unknown",
                "volumeTrend": "Normal",
                "volatilityRisk": "Low",
                "downsideRisk": "Low",
                "suggestedEntryRange": "Data unavailable",
                "riskInvalidationLevel": "Data unavailable",
            }

        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed")
            return self._unknown_metrics(ticker)

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            if hist.empty or len(hist) < 30:
                return self._unknown_metrics(ticker, company_name=ticker)

            close = hist["Close"]
            volume = hist["Volume"]
            price = _safe_float(close.iloc[-1])
            ma20 = _safe_float(close.rolling(20).mean().iloc[-1])
            ma50 = (
                _safe_float(close.rolling(50).mean().iloc[-1])
                if len(close) >= 50
                else ma20
            )
            if price is None or ma20 is None or ma50 is None:
                return self._unknown_metrics(ticker, company_name=ticker)

            returns = close.pct_change().dropna()
            vol_raw = returns.tail(60).std() * (252**0.5) * 100 if len(returns) >= 20 else None
            vol = _safe_float(vol_raw)

            momentum = "Neutral"
            if price > ma20 and ma20 > ma50:
                momentum = "Positive"
            elif price < ma50:
                momentum = "Negative"

            pullback = "Unknown"
            if price <= ma20 * 1.02 and price >= ma50 * 0.98:
                pullback = "Medium"
            if price <= ma20 * 0.98 and momentum != "Negative":
                pullback = "High"
            if price > ma20 * 1.08:
                pullback = "Low"

            avg_vol = _safe_float(volume.tail(20).mean()) or 0.0
            last_vol = _safe_float(volume.iloc[-1]) or 0.0
            volume_trend = "Normal"
            if avg_vol > 0:
                ratio = last_vol / avg_vol
                if ratio > 2:
                    volume_trend = "Abnormal"
                elif ratio > 1.3:
                    volume_trend = "Elevated"

            volatility_risk = self._bucket_vol(vol)
            pe = _safe_float(stock.info.get("trailingPE"))
            valuation = "Unknown"
            if pe is not None:
                if pe < 20:
                    valuation = "Cheap"
                elif pe <= 35:
                    valuation = "Fair"
                else:
                    valuation = "Expensive"

            name = stock.info.get("shortName") or stock.info.get("longName") or ticker

            return {
                "ticker": ticker,
                "companyName": name,
                "valuation": valuation,
                "momentum": momentum,
                "entryAttractiveness": pullback,
                "volumeTrend": volume_trend,
                "volatilityRisk": volatility_risk,
                "downsideRisk": volatility_risk,
                "suggestedEntryRange": self._entry_range(price, ma20, ma50),
                "riskInvalidationLevel": f"Below {ma50:.2f}" if ma50 else "Data unavailable",
                "price": round(price, 2),
            }
        except Exception as exc:
            logger.warning("Metrics failed for %s: %s", ticker, exc)
            return self._unknown_metrics(ticker)

    def check_entry_signal(self, ticker: str) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        if ticker == CASH_TICKER:
            return {"ticker": ticker, "entrySignal": False, "note": ""}

        try:
            import yfinance as yf

            hist = yf.Ticker(ticker).history(period="3mo")
            if len(hist) < 5:
                return {"ticker": ticker, "entrySignal": False, "note": ""}

            close = hist["Close"]
            drop_pct = (
                _safe_float((close.iloc[-1] / close.iloc[-3] - 1) * 100)
                if len(close) >= 3
                else 0.0
            )
            drop_pct = drop_pct if drop_pct is not None else 0.0
            metrics = self.get_stock_metrics(ticker)

            fundamentals_ok = metrics["valuation"] in ("Cheap", "Fair", "Unknown") and metrics[
                "momentum"
            ] != "Negative"
            triggered = drop_pct <= -3 and fundamentals_ok

            note = ""
            if triggered:
                note = (
                    f"{ticker} dropped {drop_pct:.1f}% recently while core signals remain acceptable."
                )

            return {
                "ticker": ticker,
                "entrySignal": triggered,
                "priceDropPercent": round(drop_pct, 2),
                "note": note,
            }
        except Exception:
            return {"ticker": ticker, "entrySignal": False, "note": ""}

    @staticmethod
    def _unknown_metrics(ticker: str, company_name: Optional[str] = None) -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "companyName": company_name or ticker,
            "valuation": "Unknown",
            "momentum": "Unknown",
            "entryAttractiveness": "Unknown",
            "volumeTrend": "Unknown",
            "volatilityRisk": "Unknown",
            "downsideRisk": "Unknown",
            "suggestedEntryRange": "Data unavailable",
            "riskInvalidationLevel": "Data unavailable",
        }

    @staticmethod
    def _bucket_vol(vol: Optional[float]) -> str:
        if vol is None:
            return "Unknown"
        if vol > 45:
            return "High"
        if vol > 25:
            return "Medium"
        return "Low"

    @staticmethod
    def _entry_range(price: float, ma20: float, ma50: float) -> str:
        low = min(ma20, ma50) * 0.98
        high = max(ma20, ma50) * 1.02
        if low <= 0 or high <= 0:
            return "Data unavailable"
        return f"{low:.2f} - {high:.2f}"
