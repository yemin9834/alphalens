"""Action plan generation — design-doc.md §Step 13."""

from __future__ import annotations

from typing import Any, Dict, List

from alphalens_metrics.portfolio_risk_engine import PortfolioRiskEngine


class ActionPlanService:
    """Build portfolio-aware action recommendations."""

    @staticmethod
    def _holdings_map(portfolio: List[Dict[str, Any]]) -> Dict[str, float]:
        """Normalize portfolio weights to sum to 100 (matches PortfolioRiskEngine)."""
        raw = {p["ticker"].upper(): float(p["weight"]) for p in portfolio}
        total = sum(raw.values())
        if total <= 0:
            return raw
        return {ticker: weight / total * 100 for ticker, weight in raw.items()}

    def build(
        self,
        portfolio: List[Dict[str, Any]],
        ranked_candidates: List[Dict[str, Any]],
        portfolio_risk: Dict[str, Any],
        risk_profile: str,
        market_condition: str,
    ) -> Dict[str, Any]:
        holdings = self._holdings_map(portfolio)
        actions: List[Dict[str, Any]] = []

        for candidate in ranked_candidates[:5]:
            ticker = candidate["ticker"].upper()
            current_weight = holdings.get(ticker, 0)
            score = candidate.get("opportunityScore", 0)
            metrics = candidate.get("metrics", {})

            if score < 55:
                continue

            target = self._target_weight(score, risk_profile, current_weight)
            delta = target - current_weight

            if abs(delta) < 1:
                action = "Hold"
            elif delta > 0:
                action = "Add"
            else:
                action = "Trim"

            actions.append(
                {
                    "ticker": ticker,
                    "companyName": candidate.get("companyName", ticker),
                    "action": action,
                    "currentWeight": round(current_weight, 2),
                    "suggestedWeight": round(target, 2),
                    "rationale": candidate.get("rankReason", ""),
                    "entryAttractiveness": metrics.get("entryAttractiveness", "Unknown"),
                    "suggestedEntryRange": metrics.get("suggestedEntryRange", "Data unavailable"),
                    "riskInvalidationLevel": metrics.get("riskInvalidationLevel", "Data unavailable"),
                }
            )

        actions.extend(
            self._cash_actions(holdings, actions, portfolio_risk, risk_profile)
        )

        summary = self._summary(actions, portfolio_risk, market_condition, risk_profile)
        return {
            "summary": summary,
            "actions": actions,
            "portfolioRisk": portfolio_risk,
            "marketCondition": market_condition,
        }

    @staticmethod
    def _cash_actions(
        holdings: Dict[str, float],
        equity_actions: List[Dict[str, Any]],
        portfolio_risk: Dict[str, Any],
        risk_profile: str,
    ) -> List[Dict[str, Any]]:
        cash_pct = holdings.get("CASH", 0)
        cash_buffer = portfolio_risk.get("cashBuffer", "Unknown")
        low, high = PortfolioRiskEngine.cash_thresholds(risk_profile)

        add_deploy = sum(
            action["suggestedWeight"] - action["currentWeight"]
            for action in equity_actions
            if action.get("action") == "Add"
        )

        if add_deploy >= 1 and cash_pct >= 1:
            deploy = min(add_deploy, cash_pct)
            target = round(cash_pct - deploy, 2)
            funded = ", ".join(
                action["ticker"] for action in equity_actions if action.get("action") == "Add"
            )
            shortfall = round(add_deploy - deploy, 2)
            rationale = (
                f"Deploy {deploy:.1f}% from cash to fund Add recommendations ({funded})."
            )
            if shortfall >= 1:
                rationale += (
                    f" Remaining {shortfall:.1f}% of suggested adds would need funding "
                    "from other holdings."
                )
            return [
                _cash_action_row(
                    action="Trim",
                    current=cash_pct,
                    target=target,
                    rationale=rationale,
                )
            ]

        if cash_buffer == "High":
            excess = cash_pct - high
            if excess >= 1:
                return [
                    _cash_action_row(
                        action="Trim",
                        current=cash_pct,
                        target=round(high, 2),
                        rationale=(
                            f"Cash ({cash_pct:.1f}%) is above the {risk_profile} target "
                            f"range (up to {high:.0f}%). Consider deploying {excess:.1f}% "
                            "into opportunities or rebalancing."
                        ),
                    )
                ]
            return []

        if cash_buffer == "Low":
            increase = low - cash_pct
            if increase >= 1:
                return [
                    _cash_action_row(
                        action="Add",
                        current=cash_pct,
                        target=round(low, 2),
                        rationale=(
                            f"Raise cash buffer toward {low:.0f}% minimum for a "
                            f"{risk_profile} profile (currently {cash_pct:.1f}%)."
                        ),
                    )
                ]

        return []

    @staticmethod
    def _target_weight(score: float, risk_profile: str, current: float) -> float:
        caps = {"conservative": 12, "balanced": 18, "aggressive": 25}
        cap = caps.get(risk_profile, 18)
        if score >= 80:
            return min(cap, current + 8)
        if score >= 65:
            return min(cap, current + 5)
        return min(cap, current + 2)

    @staticmethod
    def _summary(
        actions: List[Dict[str, Any]],
        risk: Dict[str, Any],
        market: str,
        risk_profile: str,
    ) -> str:
        if not actions:
            return (
                f"Market is {market.lower()}. No high-conviction changes recommended "
                "based on current signals and portfolio risk."
            )

        equity_actions = [a for a in actions if a["ticker"] != "CASH"]
        cash_actions = [a for a in actions if a["ticker"] == "CASH"]
        tickers = ", ".join(a["ticker"] for a in equity_actions[:3])
        base = (
            f"Market is {market.lower()}. Portfolio risk is {risk.get('riskLevel', 'Unknown').lower()}."
        )

        if equity_actions and tickers:
            base += f" Consider reviewing opportunities in {tickers}."
        elif not equity_actions:
            base += " No equity position changes recommended."

        if cash_actions:
            cash = cash_actions[0]
            verb = cash.get("action", "Adjust").lower()
            delta = abs(cash.get("suggestedWeight", 0) - cash.get("currentWeight", 0))
            base += (
                f" Cash buffer is {risk.get('cashBuffer', 'unknown').lower()} for a "
                f"{risk_profile} profile — {verb} cash by {delta:.1f}%."
            )

        return base


def _cash_action_row(
    action: str,
    current: float,
    target: float,
    rationale: str,
) -> Dict[str, Any]:
    return {
        "ticker": "CASH",
        "companyName": "Cash",
        "action": action,
        "currentWeight": round(current, 2),
        "suggestedWeight": round(target, 2),
        "rationale": rationale,
        "entryAttractiveness": "N/A",
        "suggestedEntryRange": "N/A",
        "riskInvalidationLevel": "N/A",
    }
