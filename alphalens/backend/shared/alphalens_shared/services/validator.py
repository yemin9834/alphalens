"""Ticker validation for discovery candidates — deterministic + optional LLM notes."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from alphalens_shared.resources import load_json
from alphalens_shared.services.validator_market import lookup_ticker_market
from alphalens_shared.services.validator_report import build_deterministic_validation_report

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def run_validator(payload: Dict[str, Any]) -> Dict[str, Any]:
    candidates = payload.get("candidates", [])
    validated = [validate_candidate(c) for c in candidates]
    result: Dict[str, Any] = {
        "success": True,
        "validatedCandidates": validated,
        "validationPayload": {
            "validatedCount": sum(1 for c in validated if c.get("tickerValidation") == "validated"),
            "unknownCount": sum(1 for c in validated if c.get("tickerValidation") == "unknown"),
            "invalidCount": sum(1 for c in validated if c.get("tickerValidation") == "invalid"),
            "candidates": validated,
        },
    }
    return attach_validation_report(result)


def attach_validation_report(result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach deterministic validationReport (default)."""
    result["validationReport"] = build_deterministic_validation_report(result)
    return result


def run_validator_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic validation + optional LLM narrative (mock / local path)."""
    from alphalens_shared.services.validator_narrative import maybe_enrich_validator_narrative

    return maybe_enrich_validator_narrative(payload, run_validator(payload))


def validate_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    ticker = str(candidate.get("ticker", "")).upper().strip()
    result = dict(candidate)
    result["ticker"] = ticker

    if not ticker:
        result["tickerValidation"] = "invalid"
        result["validationReason"] = "Missing ticker symbol."
        return result

    if ticker == "CASH":
        result["tickerValidation"] = "validated"
        result["validationReason"] = "Cash placeholder — not a listed equity."
        return result

    if not TICKER_RE.match(ticker):
        result["tickerValidation"] = "invalid"
        result["validationReason"] = "Ticker format is invalid for US symbols."
        return result

    known = _known_tickers()
    if ticker in known:
        result["tickerValidation"] = "validated"
        result["validationReason"] = "Known symbol in AlphaLens curated/sector data."
        _apply_market_enrichment(result, ticker)
        return result

    market = lookup_ticker_market(ticker)
    if market.get("found"):
        result["tickerValidation"] = "validated"
        name = market.get("marketName") or "listed symbol"
        result["validationReason"] = f"Market data found via yfinance ({name})."
        if market.get("marketName"):
            result["marketCompanyName"] = market["marketName"]
        return result

    if market.get("skipped") or market.get("error") == "yfinance_not_installed":
        result["tickerValidation"] = "unknown"
        result["validationReason"] = (
            "Well-formed ticker not in curated list; market lookup unavailable."
        )
    else:
        result["tickerValidation"] = "unknown"
        result["validationReason"] = (
            "Well-formed ticker but no reliable market data — verify before trading."
        )

    if result.get("confidence") == "High":
        result["confidence"] = "Medium"
    return result


def _apply_market_enrichment(result: Dict[str, Any], ticker: str) -> None:
    """Optional name cross-check for known symbols."""
    market = lookup_ticker_market(ticker)
    if market.get("marketName"):
        result["marketCompanyName"] = market["marketName"]
        discovery_name = str(result.get("companyName", "")).strip().lower()
        market_name = str(market["marketName"]).strip().lower()
        if discovery_name and market_name and discovery_name not in market_name and market_name not in discovery_name:
            result["validationReason"] = (
                f"Known symbol; yfinance lists '{market['marketName']}' "
                f"(discovery name: {result.get('companyName')})."
            )


def _known_tickers() -> set[str]:
    mapping = load_json("sector_mapping.json")
    curated = load_json("curated_nvidia_ecosystem.json")
    tickers = set(mapping.keys())
    tickers.update(c.get("ticker", "").upper() for c in curated.get("candidates", []))
    tickers.add(curated.get("coreTicker", "NVDA"))
    return tickers
