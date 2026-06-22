"""Unit tests for cash-aware action plan generation."""

from alphalens_metrics.action_plan_service import ActionPlanService


def _candidate(ticker: str, score: int = 72) -> dict:
    return {
        "ticker": ticker,
        "companyName": ticker,
        "opportunityScore": score,
        "rankReason": f"Strong opportunity in {ticker}",
        "metrics": {
            "entryAttractiveness": "Medium",
            "suggestedEntryRange": "10 - 12",
            "riskInvalidationLevel": "Below 9",
        },
    }


def _build(portfolio, ranked, risk_profile="aggressive", cash_buffer="High"):
    risk = {
        "riskLevel": "High",
        "cashBuffer": cash_buffer,
        "concentrationRisk": "Medium",
        "sectorExposure": "Medium",
    }
    return ActionPlanService().build(
        portfolio=portfolio,
        ranked_candidates=ranked,
        portfolio_risk=risk,
        risk_profile=risk_profile,
        market_condition="Neutral",
    )


def test_high_cash_funds_equity_adds():
    plan = _build(
        portfolio=[
            {"ticker": "NVDA", "weight": 20},
            {"ticker": "CASH", "weight": 60},
        ],
        ranked=[_candidate("TSM"), _candidate("DELL"), _candidate("LNVGY")],
    )

    cash_actions = [a for a in plan["actions"] if a["ticker"] == "CASH"]
    equity_adds = [a for a in plan["actions"] if a.get("action") == "Add" and a["ticker"] != "CASH"]

    assert len(equity_adds) == 3
    assert len(cash_actions) == 1
    assert cash_actions[0]["action"] == "Trim"
    assert cash_actions[0]["currentWeight"] == 75
    assert cash_actions[0]["suggestedWeight"] == 60
    assert "fund Add recommendations" in cash_actions[0]["rationale"]
    assert "trim cash by 15.0%" in plan["summary"].lower()


def test_acceptable_cash_funds_adds_when_cash_available():
    """Demo-style 10% cash + equity adds should still suggest deploying cash."""
    plan = _build(
        portfolio=[
            {"ticker": "NVDA", "weight": 30},
            {"ticker": "AAPL", "weight": 40},
            {"ticker": "TSLA", "weight": 20},
            {"ticker": "CASH", "weight": 10},
        ],
        ranked=[_candidate("HNHPF"), _candidate("DELL"), _candidate("LNVGY")],
        risk_profile="aggressive",
        cash_buffer="Acceptable",
    )

    cash_actions = [a for a in plan["actions"] if a["ticker"] == "CASH"]
    assert len(cash_actions) == 1
    assert cash_actions[0]["action"] == "Trim"
    assert cash_actions[0]["currentWeight"] == 10
    assert cash_actions[0]["suggestedWeight"] == 0
    assert "Remaining 5.0% of suggested adds" in cash_actions[0]["rationale"]


def test_high_cash_without_adds_trims_to_profile_band():
    plan = _build(
        portfolio=[{"ticker": "CASH", "weight": 60}],
        ranked=[_candidate("TSM", score=40)],
        cash_buffer="High",
    )

    cash_actions = [a for a in plan["actions"] if a["ticker"] == "CASH"]
    assert not [a for a in plan["actions"] if a["ticker"] != "CASH"]
    assert len(cash_actions) == 1
    assert cash_actions[0]["action"] == "Trim"
    assert cash_actions[0]["suggestedWeight"] == 15


def test_low_cash_suggests_increase():
    plan = _build(
        portfolio=[
            {"ticker": "NVDA", "weight": 98},
            {"ticker": "CASH", "weight": 2},
        ],
        ranked=[_candidate("TSM", score=40)],
        risk_profile="balanced",
        cash_buffer="Low",
    )

    cash_actions = [a for a in plan["actions"] if a["ticker"] == "CASH"]
    assert len(cash_actions) == 1
    assert cash_actions[0]["action"] == "Add"
    assert cash_actions[0]["suggestedWeight"] == 5
    assert "raise cash buffer" in cash_actions[0]["rationale"].lower()


def test_acceptable_cash_without_adds_has_no_cash_action():
    plan = _build(
        portfolio=[
            {"ticker": "NVDA", "weight": 85},
            {"ticker": "CASH", "weight": 15},
        ],
        ranked=[_candidate("TSM", score=40)],
        cash_buffer="Acceptable",
    )

    assert not [a for a in plan["actions"] if a["ticker"] == "CASH"]
