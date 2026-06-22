"""
API request/response schemas — mirrors design-doc.md §14.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class EcosystemDiscoverRequest(BaseModel):
    coreCompany: str
    coreTicker: str
    scope: str = "level-1"
    includeSecondLevel: bool = False


class DiscoveryCandidate(BaseModel):
    companyName: str
    ticker: str
    relationshipType: str
    relationshipSummary: str
    confidence: Literal["High", "Medium", "Low"]
    evidenceUrl: str
    tickerValidation: str
    deepResearch: Optional["DeepCompanyReport"] = None


class DeepResearchNewsItem(BaseModel):
    headline: str
    date: str = ""
    impact: Literal["positive", "negative", "neutral", "mixed"] = "neutral"
    summary: str = ""
    sourceUrl: str = ""


class DeepResearchFundamentals(BaseModel):
    revenueTrend: str = ""
    earningsSummary: str = ""
    lastReportDate: str = ""
    dataQuality: Literal["high", "partial", "unavailable"] = "unavailable"


class DeepResearchMarketSnapshot(BaseModel):
    price: Optional[float] = None
    valuation: str = "Unknown"
    momentum: str = "Unknown"
    volatilityRisk: str = "Unknown"
    entryAttractiveness: str = "Unknown"
    suggestedEntryRange: str = "Data unavailable"
    riskInvalidationLevel: str = "Data unavailable"


class DeepResearchEntryView(BaseModel):
    opportunityView: Literal["Attractive", "Watch", "Avoid", "Neutral"] = "Neutral"
    rationale: str = ""
    keyRisks: List[str] = Field(default_factory=list)


class DeepCompanyReport(BaseModel):
    ticker: str
    companyName: str
    executiveSummary: str = ""
    relationshipToCore: Dict[str, str] = Field(default_factory=dict)
    recentNews: List[DeepResearchNewsItem] = Field(default_factory=list)
    fundamentals: DeepResearchFundamentals = Field(default_factory=DeepResearchFundamentals)
    marketSnapshot: DeepResearchMarketSnapshot = Field(default_factory=DeepResearchMarketSnapshot)
    entryView: DeepResearchEntryView = Field(default_factory=DeepResearchEntryView)
    evidenceUrls: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EcosystemDiscoverResponse(BaseModel):
    coreCompany: str
    coreTicker: str
    candidates: List[DiscoveryCandidate]
    warnings: List[str] = Field(default_factory=list)
    discoveryRunId: Optional[str] = None
    researchStatus: Optional[str] = None


class DiscoveryRunStatusResponse(BaseModel):
    discoveryRunId: str
    coreCompany: str
    coreTicker: str
    status: str = "completed"
    researchStatus: str = "pending"
    researchProgress: Dict[str, Any] = Field(default_factory=dict)
    candidateCount: int = 0
    researchedCount: int = 0


class DiscoveryRunCandidatesResponse(BaseModel):
    discoveryRunId: str
    researchStatus: str = "pending"
    candidates: List[DiscoveryCandidate] = Field(default_factory=list)


class RankCandidateInput(BaseModel):
    ticker: str
    relationshipType: str


class OpportunitiesRankRequest(BaseModel):
    riskProfile: str
    marketCondition: str = "Neutral"
    candidates: List[RankCandidateInput]


class RankedCandidate(BaseModel):
    ticker: str
    companyName: str
    opportunityView: str
    entryAttractiveness: str
    attractiveEntryReason: str
    downsideRisk: str
    confidence: str
    positiveSignal: str
    riskSignal: str
    suggestedEntryRange: str = "Data unavailable"
    riskInvalidationLevel: str = "Data unavailable"
    opportunityScore: Optional[float] = None


class AnalysisReport(BaseModel):
    executiveSummary: str
    marketOverview: str
    topOpportunities: List[Dict[str, str]] = Field(default_factory=list)
    risksToWatch: List[Dict[str, str]] = Field(default_factory=list)
    methodologyNote: str


class ValidationReport(BaseModel):
    executiveSummary: str
    candidateNotes: List[Dict[str, str]] = Field(default_factory=list)
    methodologyNote: str


class PortfolioReport(BaseModel):
    executiveSummary: str
    actionNotes: List[Dict[str, str]] = Field(default_factory=list)
    candidateNotes: List[Dict[str, str]] = Field(default_factory=list)
    portfolioSignalsSummary: str = ""
    methodologyNote: str


class OpportunitiesRankResponse(BaseModel):
    rankedCandidates: List[RankedCandidate]
    validationReport: Optional[ValidationReport] = None
    analysisReport: Optional[AnalysisReport] = None
    warnings: List[str] = Field(default_factory=list)


class PortfolioHolding(BaseModel):
    ticker: str
    weight: float


class SavedPortfolioResponse(BaseModel):
    name: str = "Default Portfolio"
    holdings: List[PortfolioHolding] = Field(default_factory=list)
    discoveryRunId: Optional[str] = None
    candidatePool: List[RankCandidateInput] = Field(default_factory=list)


class PopulateTestDataResponse(BaseModel):
    message: str
    portfolio: SavedPortfolioResponse
    discoveryRunId: Optional[str] = None
    candidatesLoaded: int = 0


class PortfolioAnalyzeRequest(BaseModel):
    riskProfile: str
    investmentHorizon: str = "medium-term"
    marketCondition: str = "Neutral"
    portfolio: List[PortfolioHolding]
    candidatePool: List[RankCandidateInput]
    strategyProfile: str = "default-risk-based"


class PortfolioAction(BaseModel):
    type: str
    ticker: str
    amount: float = 0
    reason: str
    suggestedEntryRange: Optional[str] = None


class CandidateRecommendation(BaseModel):
    ticker: str
    view: str
    portfolioFit: str
    positiveSignal: str
    riskSignal: str
    suggestedEntryRange: str = "Data unavailable"
    positionSizingGuidance: str


class PortfolioAnalyzeResponse(BaseModel):
    finalView: str
    riskLevel: str
    marketCondition: str
    portfolioSignals: Dict[str, str]
    candidateRecommendations: List[CandidateRecommendation]
    actions: List[PortfolioAction]
    portfolioReport: Optional[PortfolioReport] = None
    validationReport: Optional[ValidationReport] = None
    analysisReport: Optional[AnalysisReport] = None
    warnings: List[str] = Field(default_factory=list)


class InstrumentSearchResult(BaseModel):
    ticker: str
    companyName: str = ""
    source: str = "unknown"


class InstrumentSearchResponse(BaseModel):
    query: str
    results: List[InstrumentSearchResult] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: bool = True
    code: str
    message: str
    affectedFields: List[str] = Field(default_factory=list)
    fallback: str = ""
