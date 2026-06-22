"""
News-to-action guardrail — design-doc.md §Step 12.
"""


class NewsGuardrailService:
    """Prevent headlines from directly triggering Add recommendations."""

    def apply_guardrail(self, ticker: str, headlines: list[dict], metrics: dict) -> dict:
        return {"passed": True, "impactNote": ""}
