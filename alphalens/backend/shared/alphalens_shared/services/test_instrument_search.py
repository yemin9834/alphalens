"""Tests for instrument search service."""

import os

os.environ["VALIDATOR_SKIP_MARKET_LOOKUP"] = "true"

from alphalens_shared.services.instrument_search import search_instruments


def test_search_empty_query():
    assert search_instruments("") == {"query": "", "results": []}


def test_search_local_ticker_prefix():
    result = search_instruments("NV")
    tickers = [item["ticker"] for item in result["results"]]
    assert "NVDA" in tickers


def test_search_local_company_name():
    result = search_instruments("Microsoft")
    tickers = [item["ticker"] for item in result["results"]]
    assert "MSFT" in tickers


def test_search_respects_limit():
    result = search_instruments("N", limit=3)
    assert len(result["results"]) <= 3
