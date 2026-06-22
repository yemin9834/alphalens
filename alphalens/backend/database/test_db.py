#!/usr/bin/env python3
"""Quick test of AlphaLens database models (requires migrated schema)."""

from decimal import Decimal

from src import Database
from src.schemas import HoldingCreate, PortfolioCreate, UserCreate

TEST_USER = "test_local_001"


def main():
    db = Database()
    user = db.users.find_by_clerk_id(TEST_USER)
    if not user:
        db.users.create_user(
            UserCreate(
                clerk_user_id=TEST_USER,
                display_name="Local Test",
                risk_profile="balanced",
            )
        )
        print("✅ Created user", TEST_USER)
    else:
        print("ℹ️  User exists:", TEST_USER)

    portfolio = db.portfolios.find_default(TEST_USER)
    if not portfolio:
        pid = db.portfolios.create_portfolio(
            TEST_USER, PortfolioCreate(name="Test", cash_weight=Decimal("5"))
        )
        db.holdings.upsert_holding(pid, HoldingCreate(ticker="NVDA", weight=Decimal("50")))
        db.holdings.upsert_holding(pid, HoldingCreate(ticker="CASH", weight=Decimal("50")))
        print("✅ Created portfolio with holdings")
    else:
        holdings = db.holdings.find_by_portfolio(portfolio["id"])
        print(f"ℹ️  Portfolio has {len(holdings)} holdings")

    print("✅ Database model test passed")


if __name__ == "__main__":
    main()
