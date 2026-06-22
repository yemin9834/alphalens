"""Ecosystem discovery — curated fallback for MVP."""

from __future__ import annotations

from typing import Any, Dict, List

from alphalens_shared.resources import load_json


def run_discovery(payload: Dict[str, Any]) -> Dict[str, Any]:
    core_ticker = payload.get("coreTicker", "NVDA").upper()
    curated = load_json("curated_nvidia_ecosystem.json")

    if core_ticker != curated.get("coreTicker", "NVDA"):
        return {
            "success": True,
            "coreCompany": payload.get("coreCompany", core_ticker),
            "coreTicker": core_ticker,
            "candidates": [],
            "warnings": [
                f"No curated ecosystem data for {core_ticker}. "
                "Deploy Guide 4 discovery service for live research."
            ],
        }

    return {
        "success": True,
        "coreCompany": curated["coreCompany"],
        "coreTicker": curated["coreTicker"],
        "candidates": curated["candidates"],
        "warnings": ["Using curated NVIDIA ecosystem demo data."],
    }


def to_api_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in candidates:
        item = {
            "companyName": c.get("companyName", c.get("company_name", "")),
            "ticker": c.get("ticker", "").upper(),
            "relationshipType": c.get("relationshipType", c.get("relationship_type", "")),
            "relationshipSummary": c.get(
                "relationshipSummary", c.get("relationship_summary", "")
            ),
            "confidence": c.get("confidence", "Medium"),
            "evidenceUrl": c.get("evidenceUrl", c.get("evidence_url", "")),
            "tickerValidation": c.get("tickerValidation", c.get("ticker_validation", "unknown")),
        }
        deep = c.get("deepResearch") or c.get("deep_research")
        if deep:
            item["deepResearch"] = deep
        out.append(item)
    return out
