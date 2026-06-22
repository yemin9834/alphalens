"""Market regime classification — design-doc.md §Step 9."""

from __future__ import annotations


class MarketRegimeService:
    """Classify market as Favorable / Neutral / Overheated / Risk-off."""

    def get_market_condition(self) -> str:
        try:
            import yfinance as yf

            spy = yf.Ticker("SPY").history(period="6mo")["Close"]
            qqq = yf.Ticker("QQQ").history(period="6mo")["Close"]
            if len(spy) < 50 or len(qqq) < 50:
                return "Neutral"

            spy_above = float(spy.iloc[-1]) > float(spy.rolling(50).mean().iloc[-1])
            qqq_above = float(qqq.iloc[-1]) > float(qqq.rolling(50).mean().iloc[-1])

            if spy_above and qqq_above:
                return "Favorable"
            if not spy_above and not qqq_above:
                return "Risk-off"
            return "Neutral"
        except Exception:
            return "Neutral"
