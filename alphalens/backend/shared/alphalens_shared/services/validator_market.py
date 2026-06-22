"""yfinance market lookup for ticker validation (deterministic)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


def market_lookup_enabled() -> bool:
    return os.getenv("VALIDATOR_SKIP_MARKET_LOOKUP", "false").lower() != "true"


def lookup_ticker_market(ticker: str) -> Dict[str, Any]:
    """
    Return whether yfinance finds tradeable market data for a symbol.

    Does not raise — callers use this to enrich validation status.
    """
    if not market_lookup_enabled():
        return {"found": False, "skipped": True}

    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed — skipping market lookup")
        return {"found": False, "error": "yfinance_not_installed"}

    try:
        stock = yf.Ticker(ticker)
        fast = getattr(stock, "fast_info", None)
        last_price = None
        market_name = None

        if fast is not None:
            last_price = _first_float(
                _get_attr(fast, "last_price"),
                _get_attr(fast, "lastPrice"),
                _get_attr(fast, "regular_market_price"),
            )
            market_name = _get_attr(fast, "short_name") or _get_attr(fast, "long_name")

        if last_price is None:
            info = stock.info or {}
            last_price = _first_float(
                info.get("regularMarketPrice"),
                info.get("previousClose"),
                info.get("currentPrice"),
            )
            market_name = market_name or info.get("shortName") or info.get("longName")

        if last_price and last_price > 0:
            return {
                "found": True,
                "marketName": str(market_name or "").strip() or None,
                "lastPrice": last_price,
            }
        return {"found": False, "reason": "no_market_price"}
    except Exception as exc:
        logger.debug("Market lookup failed for %s: %s", ticker, exc)
        return {"found": False, "error": str(exc)}


def _get_attr(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _first_float(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            parsed = float(value)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            continue
    return None
