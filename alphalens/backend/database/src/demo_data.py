"""
Demo portfolio and discovery data for AlphaLens (Alex-style populate test data).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

from .models import Database
from .schemas import (
    CandidateCreate,
    DiscoveryRunCreate,
    HoldingCreate,
    PortfolioCreate,
    UserCreate,
)

SHARED_DATA = Path(__file__).resolve().parent.parent.parent / "shared" / "data"

DEMO_HOLDINGS = [
    HoldingCreate(ticker="NVDA", weight=Decimal("30")),
    HoldingCreate(ticker="AAPL", weight=Decimal("40")),
    HoldingCreate(ticker="TSLA", weight=Decimal("20")),
    HoldingCreate(ticker="CASH", weight=Decimal("10")),
]


def _ensure_demo_user(db: Database, clerk_user_id: str) -> None:
    if not db.users.find_by_clerk_id(clerk_user_id):
        db.users.create_user(
            UserCreate(
                clerk_user_id=clerk_user_id,
                display_name="AlphaLens Demo User",
                risk_profile="balanced",
                investment_horizon="medium-term",
                acceptable_loss_pct=Decimal("15"),
                target_return=Decimal("8"),
            )
        )


def _ensure_default_portfolio(db: Database, clerk_user_id: str) -> str:
    portfolio = db.portfolios.find_default(clerk_user_id)
    if portfolio:
        return str(portfolio["id"])
    return db.portfolios.create_portfolio(
        clerk_user_id,
        PortfolioCreate(name="Demo Portfolio", cash_weight=Decimal("10"), is_default=True),
    )


def _ensure_curated_discovery_run(db: Database, clerk_user_id: str) -> str:
    runs = db.discovery_runs.find_by_user(clerk_user_id, limit=5)
    for run in runs:
        if run.get("status") != "completed":
            continue
        run_id = str(run["id"])
        if db.candidates.find_by_run(run_id):
            return run_id

    curated_path = SHARED_DATA / "curated_nvidia_ecosystem.json"
    if not curated_path.exists():
        raise FileNotFoundError(f"Curated data not found: {curated_path}")

    with open(curated_path) as f:
        curated = json.load(f)

    run_id = db.discovery_runs.create_run(
        clerk_user_id,
        DiscoveryRunCreate(
            core_company=curated["coreCompany"],
            core_ticker=curated["coreTicker"],
            scope="level-1",
        ),
    )
    candidates = [
        CandidateCreate(
            company_name=c["companyName"],
            ticker=c.get("ticker"),
            relationship_type=c["relationshipType"],
            relationship_summary=c.get("relationshipSummary"),
            confidence=c.get("confidence", "Medium"),
            evidence_url=c.get("evidenceUrl"),
            ticker_validation=c.get("tickerValidation"),
        )
        for c in curated.get("candidates", [])
    ]
    db.candidates.bulk_create(run_id, candidates)
    db.discovery_runs.update_status(
        run_id,
        "completed",
        result_payload=curated,
        warnings=curated.get("warnings", []),
    )
    return run_id


def _holdings_to_api(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"ticker": str(row["ticker"]), "weight": float(row["weight"])}
        for row in rows
        if row.get("ticker")
    ]


def _candidate_pool_from_run(db: Database, discovery_run_id: str) -> List[Dict[str, str]]:
    pool = []
    for row in db.candidates.find_by_run(discovery_run_id):
        ticker = row.get("ticker")
        if not ticker or row.get("ticker_validation") == "invalid":
            continue
        pool.append(
            {
                "ticker": str(ticker).upper(),
                "relationshipType": row.get("relationship_type") or "supplier",
            }
        )
    return pool


def build_portfolio_payload(db: Database, clerk_user_id: str) -> Dict[str, Any]:
    """Read default portfolio + latest discovery candidate pool for API responses."""
    portfolio = db.portfolios.find_default(clerk_user_id)
    if not portfolio:
        return {
            "name": "Default Portfolio",
            "holdings": [],
            "discoveryRunId": None,
            "candidatePool": [],
        }

    holdings = _holdings_to_api(db.holdings.find_by_portfolio(str(portfolio["id"])))
    discovery_run_id = None
    candidate_pool: List[Dict[str, str]] = []

    for run in db.discovery_runs.find_by_user(clerk_user_id, limit=5):
        if run.get("status") != "completed":
            continue
        run_id = str(run["id"])
        pool = _candidate_pool_from_run(db, run_id)
        if pool:
            discovery_run_id = run_id
            candidate_pool = pool
            break

    return {
        "name": portfolio.get("name") or "Default Portfolio",
        "holdings": holdings,
        "discoveryRunId": discovery_run_id,
        "candidatePool": candidate_pool,
    }


def save_user_holdings(db: Database, clerk_user_id: str, holdings: List[HoldingCreate]) -> Dict[str, Any]:
    """Persist holdings on the user's default portfolio."""
    portfolio_id = _ensure_default_portfolio(db, clerk_user_id)
    db.holdings.replace_all(portfolio_id, holdings)
    return build_portfolio_payload(db, clerk_user_id)


def populate_demo_data(db: Database, clerk_user_id: str) -> Dict[str, Any]:
    """Create demo user, portfolio, holdings, and NVIDIA discovery run (Alex-style)."""
    _ensure_demo_user(db, clerk_user_id)
    portfolio_id = _ensure_default_portfolio(db, clerk_user_id)
    db.holdings.replace_all(portfolio_id, DEMO_HOLDINGS)
    discovery_run_id = _ensure_curated_discovery_run(db, clerk_user_id)
    portfolio = build_portfolio_payload(db, clerk_user_id)

    return {
        "message": "Test data populated successfully",
        "portfolio": portfolio,
        "discoveryRunId": discovery_run_id,
        "candidatesLoaded": len(portfolio.get("candidatePool", [])),
    }
