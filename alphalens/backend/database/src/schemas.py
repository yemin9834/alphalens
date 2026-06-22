"""
Pydantic schemas for AlphaLens database validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

RiskProfile = Literal["conservative", "balanced", "aggressive"]
InvestmentHorizon = Literal["short-term", "medium-term", "long-term"]
JobStatus = Literal["pending", "running", "completed", "failed"]
DiscoveryStatus = Literal["pending", "running", "completed", "failed"]
ConfidenceLevel = Literal["High", "Medium", "Low"]


class UserCreate(BaseModel):
    clerk_user_id: str = Field(min_length=1, max_length=255)
    display_name: Optional[str] = None
    risk_profile: RiskProfile = "balanced"
    investment_horizon: InvestmentHorizon = "medium-term"
    acceptable_loss_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    target_return: Optional[Decimal] = None
    strategy_profile: str = "default-risk-based"


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    risk_profile: Optional[RiskProfile] = None
    investment_horizon: Optional[InvestmentHorizon] = None
    acceptable_loss_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    target_return: Optional[Decimal] = None
    strategy_profile: Optional[str] = None


class PortfolioCreate(BaseModel):
    name: str = Field(default="Default Portfolio", max_length=255)
    cash_weight: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    is_default: bool = True


class HoldingCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    weight: Decimal = Field(ge=0, le=100)
    cost_basis: Optional[Decimal] = Field(None, ge=0)

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.upper().strip()


class PortfolioSaveInput(BaseModel):
    """Persist portfolio holdings — draft saves allowed (weights need not sum to 100)."""

    holdings: List[HoldingCreate] = Field(default_factory=list)


class PortfolioInput(BaseModel):
    """Portfolio holdings for API / analysis — weights should sum to ~100."""

    holdings: List[HoldingCreate]

    @field_validator("holdings")
    @classmethod
    def validate_weights(cls, v: List[HoldingCreate]) -> List[HoldingCreate]:
        total = sum(h.weight for h in v)
        if abs(float(total) - 100) > 3:
            raise ValueError(f"Portfolio weights must sum to ~100, got {total}")
        return v


class DiscoveryRunCreate(BaseModel):
    core_company: str
    core_ticker: str
    scope: str = "level-1"


class CandidateCreate(BaseModel):
    company_name: str
    ticker: Optional[str] = None
    relationship_type: str
    relationship_summary: Optional[str] = None
    confidence: ConfidenceLevel = "Medium"
    evidence_url: Optional[str] = None
    ticker_validation: Optional[str] = None
    deep_research: Optional[Dict[str, Any]] = None


class AnalysisJobCreate(BaseModel):
    discovery_run_id: Optional[str] = None
    strategy_profile: str = "default-risk-based"
    request_payload: Optional[Dict[str, Any]] = None


class AnalysisJobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    ranked_payload: Optional[Dict[str, Any]] = None
    recommendation_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
