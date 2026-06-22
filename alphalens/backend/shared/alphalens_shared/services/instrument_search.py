"""Deterministic instrument search for portfolio ticker autocomplete."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

from alphalens_shared.resources import load_json
from alphalens_shared.services.validator import TICKER_RE
from alphalens_shared.services.validator_market import lookup_ticker_market

logger = logging.getLogger(__name__)

QUOTE_TYPES = {"EQUITY", "ETF"}


@lru_cache(maxsize=1)
def _local_instruments() -> tuple[dict[str, str], ...]:
    mapping = load_json("sector_mapping.json")
    curated = load_json("curated_nvidia_ecosystem.json")
    by_ticker: dict[str, str] = {}

    core_ticker = str(curated.get("coreTicker", "NVDA")).upper().strip()
    if core_ticker:
        by_ticker[core_ticker] = str(curated.get("coreCompany", "")).strip()

    for candidate in curated.get("candidates", []):
        ticker = str(candidate.get("ticker", "")).upper().strip()
        name = str(candidate.get("companyName", "")).strip()
        if ticker:
            by_ticker[ticker] = name or by_ticker.get(ticker, "")

    for ticker in mapping.keys():
        symbol = str(ticker).upper().strip()
        if symbol and symbol not in by_ticker:
            by_ticker[symbol] = ""

    return tuple({"ticker": t, "name": n, "source": "curated"} for t, n in sorted(by_ticker.items()))


def _match_local(query: str, limit: int) -> list[dict[str, Any]]:
    q_lower = query.lower()
    q_upper = query.upper().strip()
    scored: list[tuple[int, dict[str, Any]]] = []

    for item in _local_instruments():
        ticker = item["ticker"]
        name = item["name"]
        score = 0

        if ticker == q_upper:
            score = 100
        elif ticker.startswith(q_upper):
            score = 85
        elif name and q_lower in name.lower():
            score = 75
        elif q_lower in ticker.lower():
            score = 60

        if score:
            scored.append((score, dict(item)))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["ticker"]))
    return [item for _, item in scored[:limit]]


def _search_yahoo(query: str, limit: int) -> list[dict[str, Any]]:
    try:
        import yfinance as yf
    except ImportError:
        return _search_yahoo_http(query, limit)

    try:
        search = yf.Search(query, max_results=max(limit * 2, 8))
        quotes = search.quotes or []
    except Exception as exc:
        logger.debug("Yahoo search failed for %r: %s", query, exc)
        return _search_yahoo_http(query, limit)

    results: list[dict[str, Any]] = []
    for quote in quotes:
        quote_type = str(quote.get("quoteType", "")).upper()
        if quote_type not in QUOTE_TYPES:
            continue
        ticker = str(quote.get("symbol", "")).upper().strip()
        if not ticker:
            continue
        name = str(quote.get("longname") or quote.get("shortname") or "").strip()
        results.append(
            {
                "ticker": ticker,
                "name": name,
                "source": "yfinance",
                "quoteType": quote_type,
            }
        )
        if len(results) >= limit:
            break
    if results:
        return results
    return _search_yahoo_http(query, limit)


def _search_yahoo_http(query: str, limit: int) -> list[dict[str, Any]]:
    """Lightweight Yahoo search without yfinance (Lambda-friendly)."""
    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    url = (
        "https://query1.finance.yahoo.com/v1/finance/search?"
        + urllib.parse.urlencode({"q": query, "quotesCount": max(limit * 2, 8)})
    )
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "AlphaLens/1.0"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.debug("Yahoo HTTP search failed for %r: %s", query, exc)
        return []

    results: list[dict[str, Any]] = []
    for quote in payload.get("quotes") or []:
        quote_type = str(quote.get("quoteType", "")).upper()
        if quote_type not in QUOTE_TYPES:
            continue
        ticker = str(quote.get("symbol", "")).upper().strip()
        if not ticker:
            continue
        name = str(quote.get("longname") or quote.get("shortname") or "").strip()
        results.append(
            {
                "ticker": ticker,
                "name": name,
                "source": "yahoo",
                "quoteType": quote_type,
            }
        )
        if len(results) >= limit:
            break
    return results


def search_instruments(query: str, limit: int = 8) -> dict[str, Any]:
    """Search curated data and Yahoo Finance for ticker or company name matches."""
    q = query.strip()
    if not q:
        return {"query": "", "results": []}

    limit = max(1, min(limit, 20))
    q_upper = q.upper()
    seen: set[str] = set()
    results: list[dict[str, str]] = []

    def add(item: dict[str, Any]) -> None:
        ticker = str(item.get("ticker", "")).upper().strip()
        if not ticker or ticker in seen:
            return
        seen.add(ticker)
        results.append(
            {
                "ticker": ticker,
                "companyName": str(item.get("name") or item.get("companyName") or "").strip(),
                "source": str(item.get("source") or "unknown"),
            }
        )

    if TICKER_RE.match(q_upper):
        market = lookup_ticker_market(q_upper)
        if market.get("found"):
            add(
                {
                    "ticker": q_upper,
                    "name": market.get("marketName") or "",
                    "source": "market",
                }
            )

    for item in _match_local(q, limit):
        add(item)
        if len(results) >= limit:
            return {"query": q, "results": results[:limit]}

    remaining = limit - len(results)
    if remaining > 0:
        for item in _search_yahoo(q, remaining):
            add(item)
            if len(results) >= limit:
                break

    return {"query": q, "results": results[:limit]}
