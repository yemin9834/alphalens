# Design Doc

## 1. Project Goal

Most individual investors lack a structured, data-grounded process for finding and evaluating investment opportunities. They may know a major company such as NVIDIA is important, but they cannot easily identify its upstream suppliers, downstream customers, strategic partners, and related public companies, then evaluate which of those companies may offer attractive entry opportunities relative to their current portfolio.

AlphaLens is an AI-powered portfolio decision-support agent that addresses this gap through an ecosystem-based workflow: it first builds a dynamic stock pool around a core company or investment theme, analyzes the companies in that pool using real market data and structured financial signals, identifies potentially undervalued or attractive entry candidates, and then evaluates whether those candidates fit the user's existing portfolio, risk profile, and investment constraints.

AlphaLens does not execute trades, does not guarantee returns, and does not replace professional financial advice. It is a structured decision-support tool designed to help investors discover relevant opportunities and act with greater discipline and clarity.

---

## 2. Core Workflow and Use Cases

### Use Case 1: Ecosystem Stock Pool Discovery

The user provides a core company, ticker, or investment theme. For example, the user may choose NVIDIA because it is a major company in AI infrastructure. The system retrieves recent public information and identifies related companies, including:
- Upstream suppliers
- Downstream customers
- Strategic partners
- Cloud, semiconductor, hardware, and software ecosystem companies
- First-level and optional second-level related companies

The system then maps public companies to stock tickers and creates a candidate stock pool for further analysis. The stock pool is not treated as a final recommendation. It is a dynamic candidate universe that must be filtered by ticker validity, confidence, market data, valuation, momentum, risk, and portfolio fit.

### Use Case 2: Stock Pool Opportunity Analysis and Daily Entry Signal Detection

After the candidate stock pool is created, the system analyzes each public company in the pool using structured market and financial signals. The goal is to identify which companies appear to offer attractive entry opportunities — including stocks that may be relatively undervalued, have pulled back toward reasonable entry zones, or have strong fundamentals with manageable downside risk.

As part of this analysis, the system includes a lightweight entry-signal check: when a stock in the pool has dropped significantly in recent sessions, the system evaluates whether the drop reflects a genuine deterioration in fundamentals or a temporary dislocation such as a sector-wide selloff or an overreaction to short-term news. If the fundamentals remain intact and the price has moved into a more attractive range, the stock is flagged accordingly within the opportunity ranking output. For the MVP, this logic is implemented as part of opportunity ranking rather than a fully automated daily scanner.

The system evaluates:
- Valuation signal
- Growth and profitability signal
- Price momentum
- Pullback or entry attractiveness
- Volatility and downside risk
- Volume trend
- Recent news impact and whether price move is fundamentally justified
- Market condition

Output: a ranked opportunity list — Potential Add Candidate / Watch / Avoid for Now / High Risk — with notable entry signals surfaced within the ranking. The system does not guarantee that a flagged stock is undervalued or that a trade will be profitable.

### Use Case 3: Portfolio-Aware Recommendation

The user provides their current holdings and risk profile. The system evaluates whether the opportunity candidates from the stock pool fit the user's existing portfolio.

For example, if a candidate looks attractive based on stock-level metrics but the user already has high exposure to technology or NVIDIA-related companies, the system may recommend Watch or Small Position Only instead of Add. The final recommendation depends on both stock-level opportunity and portfolio-level context.

Output: a structured action plan showing which candidates may be considered for entry, which should stay on watch, which should be avoided, and whether any current holdings create risk or funding constraints. The system does not execute trades; the final decision remains with the user.

---

## 3. Target Users

- **New investors** who lack the tools or experience to identify related companies and evaluate portfolio risk
- **Active investors** who want a more structured process for finding opportunities instead of reacting to headlines
- **Any investor** who wants concise, data-grounded portfolio guidance instead of generic stock commentary

---

## 4. Why AI Is Needed — And Why a Structured Approach Matters

**The discovery and personalization problem**

A correct investment decision depends on both the opportunity and the person asking. Even if a company appears attractive, the appropriate action differs based on the user's existing holdings, sector exposure, risk tolerance, investment horizon, current market conditions, and how closely the candidate is correlated with existing positions.

AI is required to reason over:
- Business relationships between a core company and its ecosystem
- Candidate company relevance and relationship type
- Current portfolio composition and concentration risk
- User risk profile and investment horizon
- Stock-level metrics: valuation, momentum, volatility, growth, financial health
- Current market regime
- Recent news and whether catalysts are already priced in
- Optional: personal trading history and behavioral loss patterns

Without this full context, a recommendation may be generic, incomplete, or unsuitable for a specific user's portfolio.

**The problem with existing AI investment tools**

The rapid growth of AI has produced many investment tools and AI assistants that offer market commentary, stock opinions, and trading signals. However, many of these tools share common weaknesses: they generate unstructured output with inconsistent quality, rely on sentiment and headlines rather than systematic metrics, do not clearly explain how candidate stocks were selected, and do not account for the user's portfolio context.

AlphaLens is designed to address these weaknesses directly. Every recommendation is produced through a defined workflow — ecosystem stock pool discovery, ticker validation, market metric analysis, opportunity scoring, portfolio fit assessment, news guardrails, and AI explanation. The AI's role is to synthesize structured inputs into concise, personalized recommendations, not to generate free-form market opinions or unsupported price targets.

---

## 5. Product Positioning

**AlphaLens is:**
- An ecosystem-based portfolio opportunity discovery tool focused on finding attractive entry candidates within a logically constructed stock pool
- A structured, metrics-driven portfolio decision-support agent
- A tool that identifies candidate opportunities from a defined stock pool
- An AI explanation layer built on top of deterministic, auditable financial metrics
- A portfolio-aware recommendation system that considers risk profile and current holdings

**AlphaLens is not:**
- A trading execution system
- A tool that guarantees investment returns
- A system that blindly recommends stocks from news or hype
- A substitute for professional financial advice
- An AI that invents financial metrics, price targets, or unsupported buy/sell signals

---

## 6. High-Level Workflow

### Step 1: User Onboarding

The user provides their investment profile:
- Risk tolerance: conservative / balanced / aggressive
- Investment horizon: short-term / medium-term / long-term
- Acceptable loss percentage
- Target return
- Optional: preferred investment style

This profile is used in every recommendation. It never changes without the user updating it.

### Step 2: Portfolio Input

The user enters current holdings:
- Ticker and holding percentage for each position
- Optional: cost basis per position
- Cash percentage

The system validates that weights sum to ~100%.

### Step 3: Core Company or Theme Input

The user provides a core company, ticker, or investment theme to generate a candidate stock pool. Example:
- Core company: NVIDIA / NVDA
- Theme: AI infrastructure
- Relationship scope: first-level related companies, with optional second-level expansion

For MVP, the default demo scenario uses NVIDIA and its AI / semiconductor ecosystem.

### Step 4: Ecosystem Stock Pool Discovery

The system searches for companies related to the core company or theme. It identifies relationship types such as:
- Supplier
- Customer
- Strategic partner
- Ecosystem company
- Competitor or alternative provider

For each discovered company, the system stores:
- Company name
- Relationship type
- Relationship summary
- Evidence URL
- Confidence score
- Ticker if publicly listed

Ticker matching must be validated. If matching is uncertain, the system marks the ticker as Unknown or uses a curated override map for known companies in the demo scenario.

### Step 5: Stock Pool Filtering

The system filters the candidate stock pool before financial analysis:
- Remove duplicate companies
- Keep public companies with valid tickers when financial analysis is required
- Mark private companies as informational only
- Remove low-confidence or unsupported relationships
- Keep evidence URLs for traceability

Output: a validated stock pool for market analysis.

### Step 6: Optional Strategy Template

The user can optionally select a rule overlay:
- Default risk-based analysis (recommended)
- Momentum template
- Conservative opportunity template
- Personal loss guardrail template

MVP does not support arbitrary custom rules.

### Step 7: Optional Trading History Upload

If the user uploads a trading history CSV, the system uses it to identify simple personal risk patterns:
- Average holding period
- Short-hold loss frequency
- Overtrading frequency
- Sector concentration in past trades
- Repeated realized losses

MVP supports one CSV format only:
```csv
date,ticker,action,quantity,price
2025-01-10,NVDA,buy,10,500
2025-01-18,NVDA,sell,10,520
```

**Important rule:** Personal history is a warning layer, not the decision layer. The system always shows both the personal risk warning and the objective market view separately.

### Step 8: Portfolio Risk Analysis

The system computes:
- Concentration risk (single-stock and top-3 weight)
- Sector exposure
- Cash buffer vs. risk profile
- Volatility exposure
- Downside risk composite

Output: Portfolio risk level (Low / Medium / High) and main portfolio issues.

### Step 9: Market Condition Retrieval

The system retrieves market context:
- SPY and QQQ trend vs. 50-day moving average
- VIX level if available
- Optional FRED macro signals (interest rates, CPI, yield curve)

Output: Market condition label — **Favorable / Neutral / Overheated / Risk-off**

### Step 10: Stock-Level Signal Analysis

For each public company in the validated stock pool and each major holding, the system calculates:
- Valuation: Cheap / Fair / Expensive / Unknown
- Revenue growth: Weak / Stable / Strong / Unknown
- Profitability: Weak / Healthy / Strong / Unknown
- Financial health: Weak / Acceptable / Strong / Unknown
- Price momentum: Negative / Neutral / Positive
- Pullback / entry attractiveness: Low / Medium / High / Unknown
- Volume trend: Normal / Elevated / Abnormal
- Volatility risk: Low / Medium / High
- Downside risk: Low / Medium / High
- Portfolio fit: Good / Neutral / Poor

If data is missing, the field returns "Unknown" — AI never invents values.

**Price guidance fields (shown when data supports it):**
- Suggested entry range (based on moving averages, support levels, recent lows)
- Suggested exit or trim range (based on resistance, recent highs, cost basis)
- Risk invalidation level (below key support or user-defined max loss)

### Step 11: Opportunity Ranking

The system ranks stock pool candidates using deterministic signals before AI explanation. The purpose of this ranking is to find potential entry opportunities inside the stock pool, not to randomly recommend popular stocks. A simple MVP scoring model may consider:
- Valuation attractiveness
- Pullback or entry attractiveness
- Momentum quality
- Growth and profitability strength
- Volatility and downside risk penalty
- Market condition
- News impact after guardrails

A candidate should only become a Potential Add Candidate when the opportunity score is supported by multiple signals, such as reasonable valuation, a pullback toward support or moving averages, intact momentum, manageable downside risk, and acceptable portfolio fit. AI may explain this result, but it must not invent an entry thesis without supporting metrics.

Output: a ranked list of candidate opportunities:
- Potential Add Candidate
- Watch
- Avoid for Now
- High Risk

The ranking is not a guaranteed prediction. It is a structured way to prioritize which stocks may deserve attention because their current price, valuation, momentum, and risk profile appear more attractive relative to other companies in the same stock pool.

As part of the ranking, the system includes a lightweight entry-signal check. If a stock has dropped significantly in recent sessions (e.g. >3–5% over 1–3 days) with abnormal volume, the system evaluates whether the drop reflects a genuine fundamental deterioration or a temporary dislocation. If fundamentals remain intact and the price has moved into a more attractive range, the candidate's ranking reflects this and a brief signal note is included in the output. This check is integrated into the ranking logic and does not require a separate pipeline for the MVP.

**Rule:** A price drop alone does not elevate a candidate's ranking. The drop must be accompanied by intact valuation, growth, and financial health signals before it is treated as an entry signal.

### Step 12: News-to-Action Guardrail

Recent news is not treated as a direct Buy or Sell signal. The system:
1. Retrieves recent headlines
2. Classifies news type (earnings, analyst upgrade, product event, partnership, regulation, macro)
3. Maps news to metric impact (EPS expectation, margin, demand, valuation, supply chain, customer demand)
4. Checks whether the catalyst is already priced in
5. Factors into recommendation only after passing metric and portfolio fit checks

**Rule:** An analyst upgrade or partnership headline does not trigger Buy if the stock has already rallied, valuation is stretched, momentum is overextended, or adding it increases portfolio concentration risk.

### Step 13: Portfolio-Aware Recommendation Generation

AI receives all structured inputs and generates concise, structured output — not long essays.

#### Stock Pool Output
For each candidate:
- Company name and ticker
- Relationship to the core company or theme
- Opportunity view: Potential Add Candidate / Watch / Avoid for Now / High Risk
- Entry attractiveness
- Attractive entry reason
- Top positive signal
- Top risk signal
- Confidence
- Evidence URL and data-availability notes

#### Portfolio-Level Output
- Final view: Hold / Rebalance Recommended / Opportunity Available / High Risk
- Portfolio risk level
- Main issues identified
- Key risks and positive signals
- Suggested portfolio-level action

#### Portfolio-Aware Candidate Output
For each selected opportunity candidate:
- Recommendation: Consider Adding / Watch / Small Position Only / Avoid Adding
- Portfolio fit assessment
- Suggested entry range (if applicable and data available)
- Suggested position sizing guidance
- Risk invalidation level (if data supports it)
- Short reason

### Step 14: Action Plan Generation

Converts recommendations into a concrete action list. Each action includes:
- Action type: add / watch / hold / reduce / avoid_adding / increase_cash
- Ticker
- Suggested percentage change or suggested maximum exposure
- Suggested entry range (for add actions, if available)
- Suggested exit or trim range (for reduce actions, if available)
- Risk invalidation level (if available)
- Reason
- Risk impact
- Confidence level

**Price rule:** Entry, exit, and stop-loss levels must come from market data logic (moving averages, support/resistance, cost basis). AI does not invent price targets. If data is not available, the field returns "Data unavailable."

### Step 15: Follow-Up Questions

Users can ask targeted follow-up questions:
- "Why is this stock in the candidate pool?"
- "What relationship does this company have with NVIDIA?"
- "Why is this candidate ranked higher than another one?"
- "What would make this stock a Buy?"
- "What entry price would make this more attractive?"
- "How would this change if I were more aggressive?"
- "How would adding this affect my portfolio risk?"

---

## 7. Product Layers

| Layer | Purpose |
|---|---|
| User Profile | Understand risk tolerance, horizon, and constraints before any recommendation |
| Portfolio Input | Capture existing holdings, cash position, and optional cost basis |
| Ecosystem Stock Pool Discovery | Build a candidate universe around a core company or theme |
| Ticker Validation | Map discovered companies to public tickers and flag uncertain matches |
| Stock Pool Filtering | Remove duplicates, low-confidence relationships, and unsupported candidates |
| Strategy / Rule Profile | Optional rule overlay (momentum, conservative, guardrail) |
| Trading History Guardrail | Detect personal loss patterns as warning layer |
| Portfolio Analysis | Identify concentration, sector, volatility, and cash risks |
| Market Regime | Classify market as favorable / neutral / overheated / risk-off |
| Stock-Level Signals | Compute valuation, growth, momentum, volume, downside risk, portfolio fit |
| Opportunity Ranking | Prioritize stock pool candidates using deterministic signals |
| News-to-Action Guardrail | Prevent news from directly triggering trades |
| AI Explanation | Combine all inputs into structured, concise recommendations |
| Action Plan | Convert recommendations into concrete portfolio-aware actions |

---

## 8. MVP Scope

**Must have:**
- User risk profile form
- Portfolio input form
- Core company / theme input for stock pool discovery
- NVIDIA ecosystem discovery demo
- Ticker validation and public-company filtering
- Basic market data retrieval (yfinance)
- Basic metric engine for stock pool candidates
- Opportunity ranking table focused on potential add candidates and watchlist candidates
- Portfolio risk dashboard
- AI recommendation panel for selected candidates
- Portfolio-aware action plan generation

**Should have if time allows:**
- CSV portfolio upload
- First-level and limited second-level ecosystem expansion
- FRED macro signal integration
- Lightweight news-to-action signal
- Simplified trading history upload and loss pattern detection
- Strategy template selection
- Suggested entry / exit range using technical levels

**Do not build in MVP:**
- Real brokerage trade execution
- Full options strategy engine
- Full SEC XBRL parsing
- Complex backtesting engine
- AI-generated price targets without market data support
- Full brokerage CSV compatibility
- Unlimited graph expansion across all related companies
- Fully automated ticker matching without validation

---

## 9. Data Sources

| Source | Used For | Risk |
|---|---|---|
| Real-time web search API | Ecosystem company discovery and evidence URLs | May return noisy or incomplete results |
| LLM extraction | Relationship extraction from search results | Requires confidence scoring and validation |
| yfinance | Price, volume, moving averages, volatility, SPY/QQQ trend | Suitable for demo; not production-grade |
| Alpha Vantage | Fallback market data | Rate limits on free tier |
| FRED | Interest rates, CPI, yield curve, macro signals | Optional for MVP |
| SEC EDGAR | Filing metadata and links only | No full XBRL parsing in MVP |
| News API or mock | News-to-action guardrail | Use mocked data for MVP reliability |
| Local static files | sector_mapping.json, demo portfolios, curated NVIDIA ecosystem data, sample CSV | Always available as demo fallback |

**Data rule:** If any field is missing or unavailable, return "Unknown" or "Data unavailable." AI never infers or guesses missing financial data.

---

## 10. Key Metric Definitions

### Relationship Confidence
- High: company relationship is directly supported by a credible source and the company name is clearly identified
- Medium: company relationship is supported but may require validation or appears in a secondary source
- Low: company is weakly implied, ticker match is uncertain, or source quality is limited

### Candidate Stock Pool
A candidate stock pool is a set of companies discovered around a core company or theme. It includes public companies for financial analysis and may include private companies as informational ecosystem context.

### Opportunity View
- Potential Add Candidate: attractive stock-level signals, reasonable valuation or pullback entry, acceptable risk, and reasonable portfolio fit
- Watch: relevant company with mixed signals, less attractive entry, or insufficient confirmation
- Avoid for Now: weak entry, stretched valuation, weak momentum, or poor portfolio fit
- High Risk: high volatility, poor downside profile, or major data/news risk

### Concentration Risk
- High: largest single holding > 35%, or top 3 holdings > 75%
- Medium: largest holding 20–35%, or top 3 holdings 50–75%
- Low: otherwise

### Sector Exposure
- High: largest sector > 60%
- Medium: 40–60%
- Low: < 40%

### Cash Buffer (varies by risk profile)
| Profile | Low | Acceptable | High |
|---|---|---|---|
| Conservative | < 10% | 10–25% | > 25% |
| Balanced | < 5% | 5–20% | > 20% |
| Aggressive | < 2% | 2–15% | > 15% |

### Volatility Risk (60-day annualized)
- High: > 45%
- Medium: 25–45%
- Low: < 25%

### Market Condition (SPY + QQQ vs. 50-day MA)
- Favorable: both above 50-day MA
- Neutral: mixed
- Risk-off: both below 50-day MA
- Overheated: both above MA but VIX very low or momentum very extended

### Momentum Signal (20-day and 50-day MA)
- Positive: price > 20-day MA and 20-day MA > 50-day MA
- Neutral: mixed
- Negative: price < 50-day MA

### Pullback / Entry Attractiveness
- High: price has pulled back toward a key moving average or support level without breaking trend
- Medium: price is near a reasonable entry zone but signals are mixed
- Low: price is extended, trend is broken, or downside risk is elevated
- Unknown: insufficient data

### Volume Trend (vs. 20-day average volume)
- Abnormal: > 2x average
- Elevated: 1.3–2x average
- Normal: < 1.3x average

### Suggested Entry / Exit / Risk Levels
Only shown when data supports it. Derived from:
- Entry: near 20-day or 50-day MA, near recent support, on pullback from extended price
- Exit / Trim: near recent high, near resistance, after strong price extension, above cost basis
- Risk invalidation: below 50-day MA, below recent support, below cost basis by max loss %

---

## 11. AI Prompt Design

Prompt files are split by task to keep each prompt focused:

```
backend/app/prompts/
  ecosystem_discovery_prompt.md
  opportunity_ranking_prompt.md
  portfolio_summary_prompt.md
  candidate_recommendation_prompt.md
  action_plan_prompt.md
  guardrail_explanation_prompt.md
```

**Every prompt must include these anti-hallucination rules:**
- Use only provided metrics and data
- Do not invent missing numbers
- If data is missing, write "Unknown" or "Data unavailable"
- Do not promise returns
- Do not recommend real trade execution
- Do not generate price targets unless provided by the metric engine
- Do not treat a partnership, analyst upgrade, or positive headline as a direct Buy signal
- Keep output concise and structured

**All AI outputs are requested in structured JSON.** Frontend renders JSON into cards, tables, and short text. If AI returns malformed JSON, backend retries or returns safe fallback.

---

## 12. Error Handling

All backend endpoints return a consistent error format:

```json
{
  "error": true,
  "code": "DATA_UNAVAILABLE",
  "message": "Market data for NVDA could not be retrieved.",
  "affectedFields": ["momentum", "volumeTrend", "suggestedEntryRange"],
  "fallback": "Proceeding with available portfolio, profile, and candidate data only."
}
```

**Error codes:**
- `DATA_UNAVAILABLE`: external API returned no data
- `DATA_PARTIAL`: some fields returned, others missing
- `FORMAT_ERROR`: uploaded file does not match expected schema
- `VALIDATION_ERROR`: portfolio weights do not sum to valid range
- `AI_PARSE_ERROR`: AI returned malformed JSON
- `DISCOVERY_UNAVAILABLE`: ecosystem discovery failed or returned no supported companies
- `TICKER_VALIDATION_ERROR`: ticker matching is ambiguous or unsupported

**Degradation rule:** When data is missing, the system continues with available data. Missing fields are labeled "Unknown." AI recommendation still generates if enough structured inputs remain. Frontend shows inline warning labels — not blocking error modals.

---

## 13. Dashboard Design

### Stock Pool Discovery View
- Core company or theme input
- Discovered company table
- Relationship type, confidence, ticker, and evidence URL
- Warning labels for private companies, uncertain ticker matches, or low-confidence relationships

### Opportunity Ranking View
- Ranked candidate list
- Opportunity view: Potential Add Candidate / Watch / Avoid for Now / High Risk
- Key metrics: valuation, momentum, pullback attractiveness, volatility, news impact, confidence
- Data availability warnings shown inline

### Portfolio Dashboard
- Final view: Hold / Rebalance Recommended / Opportunity Available / High Risk
- Portfolio risk level, concentration risk, sector exposure, cash buffer, market condition
- Existing holding recommendation cards
- Candidate opportunity cards
- Action plan panel

### Stock Detail View
Triggered when user clicks a holding, candidate, or searches a ticker:
- Final view, entry attractiveness, downside risk, confidence
- Full metric summary table
- Suggested entry range, exit range, risk invalidation level (or "Data unavailable")
- Position sizing guidance relative to current portfolio
- Short AI explanation
- Actionable next step

### Action Plan View
- Each action: type, ticker, percentage or maximum exposure, entry/exit range if available, reason, risk impact
- Data availability warnings shown inline

---

## 14. API Contract

### POST /api/ecosystem/discover

Input:
```json
{
  "coreCompany": "NVIDIA",
  "coreTicker": "NVDA",
  "scope": "level-1",
  "includeSecondLevel": false
}
```

Output:
```json
{
  "coreCompany": "NVIDIA",
  "coreTicker": "NVDA",
  "candidates": [
    {
      "companyName": "Taiwan Semiconductor Manufacturing Company",
      "ticker": "TSM",
      "relationshipType": "supplier",
      "relationshipSummary": "TSMC provides semiconductor manufacturing services for NVIDIA chips.",
      "confidence": "High",
      "evidenceUrl": "Data unavailable for mock demo",
      "tickerValidation": "validated"
    },
    {
      "companyName": "Amazon Web Services",
      "ticker": "AMZN",
      "relationshipType": "customer_partner",
      "relationshipSummary": "AWS provides cloud infrastructure that uses NVIDIA GPUs for AI workloads.",
      "confidence": "High",
      "evidenceUrl": "Data unavailable for mock demo",
      "tickerValidation": "mapped_to_parent_company"
    }
  ],
  "warnings": []
}
```

### POST /api/opportunities/rank

Input:
```json
{
  "riskProfile": "balanced",
  "marketCondition": "Neutral",
  "candidates": [
    { "ticker": "TSM", "relationshipType": "supplier" },
    { "ticker": "MSFT", "relationshipType": "partner" },
    { "ticker": "AVGO", "relationshipType": "ecosystem" }
  ]
}
```

Output:
```json
{
  "rankedCandidates": [
    {
      "ticker": "TSM",
      "companyName": "Taiwan Semiconductor Manufacturing Company",
      "opportunityView": "Watch",
      "entryAttractiveness": "Medium",
      "attractiveEntryReason": "Price is closer to a reasonable entry zone than other candidates, but confirmation is still limited",
      "downsideRisk": "Medium",
      "confidence": "Medium",
      "positiveSignal": "Relevant supplier with healthy demand exposure",
      "riskSignal": "Semiconductor cycle and valuation risk remain relevant",
      "suggestedEntryRange": "Data unavailable",
      "riskInvalidationLevel": "Data unavailable"
    }
  ]
}
```

### POST /api/portfolio/analyze

Input:
```json
{
  "riskProfile": "balanced",
  "investmentHorizon": "medium-term",
  "portfolio": [
    { "ticker": "NVDA", "weight": 30 },
    { "ticker": "AAPL", "weight": 40 },
    { "ticker": "TSLA", "weight": 20 },
    { "ticker": "CASH", "weight": 10 }
  ],
  "candidatePool": [
    { "ticker": "TSM", "relationshipType": "supplier" },
    { "ticker": "MSFT", "relationshipType": "partner" },
    { "ticker": "AMZN", "relationshipType": "customer_partner" }
  ],
  "strategyProfile": "default-risk-based"
}
```

Output:
```json
{
  "finalView": "Opportunity Available",
  "riskLevel": "High",
  "marketCondition": "Neutral",
  "portfolioSignals": {
    "concentrationRisk": "High",
    "sectorExposure": "Tech-heavy",
    "cashBuffer": "Acceptable",
    "volatilityRisk": "High"
  },
  "candidateRecommendations": [
    {
      "ticker": "MSFT",
      "view": "Watch",
      "portfolioFit": "Neutral",
      "positiveSignal": "Strong AI cloud ecosystem relevance",
      "riskSignal": "Adding more technology exposure may increase concentration",
      "suggestedEntryRange": "Data unavailable",
      "positionSizingGuidance": "Small position only if the user wants additional AI infrastructure exposure"
    },
    {
      "ticker": "TSM",
      "view": "Potential Add Candidate",
      "portfolioFit": "Potential diversification within the NVIDIA ecosystem",
      "positiveSignal": "Key supplier exposure",
      "riskSignal": "Semiconductor cycle and geopolitical risk",
      "suggestedEntryRange": "Data unavailable",
      "positionSizingGuidance": "Limit exposure due to existing technology concentration"
    }
  ],
  "actions": [
    {
      "type": "watch",
      "ticker": "MSFT",
      "amount": 0,
      "reason": "Relevant candidate but not clearly attractive enough to add immediately"
    },
    {
      "type": "add",
      "ticker": "TSM",
      "amount": 5,
      "suggestedEntryRange": "Data unavailable",
      "reason": "Potential add candidate from NVIDIA supplier ecosystem with acceptable portfolio fit and more attractive entry profile than other candidates"
    }
  ]
}
```

### Optional: POST /api/opportunities/entry-signals

For the MVP, entry signal detection is integrated into `POST /api/opportunities/rank` and returned as part of the ranking output. This endpoint may be extracted as a standalone endpoint in a later iteration if the feature warrants its own interface.

When implemented as a standalone endpoint, it scans the stock pool and existing holdings for short-term entry opportunity signals — stocks that have dropped significantly but whose fundamentals remain intact.

Input:
```json
{
  "stockPool": ["TSM", "MSFT", "AVGO", "MU"],
  "holdings": [
    { "ticker": "NVDA", "weight": 30 },
    { "ticker": "AAPL", "weight": 40 }
  ],
  "riskProfile": "balanced"
}
```

Output:
```json
{
  "entrySignals": [
    {
      "ticker": "MU",
      "signalType": "Entry Opportunity — Potential Dislocation",
      "priceDropPercent": -6.2,
      "dropWindow": "2 days",
      "newsContext": "Sector-wide semiconductor selloff following macro rate concerns",
      "fundamentalAssessment": "Revenue growth Strong, profitability Healthy, valuation Fair — no fundamental deterioration detected",
      "entryAttractiveness": "High",
      "portfolioFit": "Good — adds semiconductor exposure without increasing existing concentration",
      "suggestedEntryRange": "Data unavailable",
      "confidence": "Medium",
      "shortExplanation": "MU dropped sharply in a sector rotation event unrelated to company fundamentals. Valuation has moved into a more attractive range. Warrants attention if the user has available allocation."
    }
  ],
  "noSignalTickers": ["TSM", "MSFT", "AVGO"],
  "scanTimestamp": "2025-06-03T10:00:00Z"
}
```

---

## 15. CLAUDE.md Definition

```markdown
# CLAUDE.md

AlphaLens Portfolio Agent is an AI-powered portfolio decision assistant.
It discovers ecosystem-based stock pools around a core company or theme,
analyzes candidate stocks using deterministic market metrics, and generates
portfolio-aware action recommendations based on user holdings and risk profile.
It does not execute trades or guarantee returns.

## Tech Stack
- Frontend: React.js, TypeScript
- Backend: Python
- Market data: yfinance (primary), Alpha Vantage (fallback)
- Search data: real-time web search API with local curated fallback
- Macro data: FRED API, optional for MVP
- AI: Anthropic Claude API

## Key Locations
- API routes: backend/app/routes/
- Ecosystem discovery service: backend/app/services/ecosystem_discovery_service.py
- Ticker validation service: backend/app/services/ticker_validation_service.py
- Metric engine: backend/app/services/market_metric_engine.py
- Opportunity ranking service: backend/app/services/opportunity_ranking_service.py
- AI prompts: backend/app/prompts/
- Static data: backend/app/data/
- Frontend components: frontend/src/components/

## Do Not Auto-Edit
- backend/app/prompts/ (prompt files require careful manual review)
- backend/app/data/sector_mapping.json (manually curated)
- backend/app/data/curated_nvidia_ecosystem.json (demo fallback data)

## Data Rules
- Never invent financial metrics
- If data is missing, return "Unknown" or "Data unavailable"
- Do not generate price targets without market data support
- Do not treat relationship discovery as a final investment recommendation

## Test Commands
- Backend: pytest backend/app/tests/
- Frontend: npm run test
```

---

## 16. Development Order

1. Create repo skeleton, README, CLAUDE.md, design doc
2. Define API contract for ecosystem discovery, opportunity ranking, and portfolio analysis
3. Build frontend with mock data for stock pool discovery, opportunity ranking, portfolio dashboard, and action plan
4. Build backend ecosystem discovery service with NVIDIA demo scenario
5. Add ticker validation and curated NVIDIA ecosystem fallback data
6. Build backend market metric engine for stock pool candidates
7. Build opportunity ranking service using deterministic signals, including lightweight entry-signal check
8. Build portfolio parser and portfolio risk engine
9. Connect candidate opportunities to portfolio-aware recommendation logic
10. Add AI recommendation generation after metrics and ranking are stable
11. Add action plan generation
12. Add error handling and fallback behavior
13. Add optional strategy template selection
14. Add news / FRED / trading history if time allows
15. Polish UI
16. Prepare demo script

---

## 17. MVP Success Criteria

The MVP is considered complete when a user can:
- Input a core company or theme and generate a related stock pool
- View discovered related companies with relationship type, ticker, confidence, and evidence
- Filter the stock pool to public companies with valid tickers
- View a ranked list of potential add and watchlist candidates based on structured market metrics, with notable entry signals surfaced within the ranking when a stock has pulled back but fundamentals remain intact
- Input a portfolio and risk profile, and receive a structured portfolio risk summary
- See whether candidate opportunities fit the user's current portfolio
- Review a concrete action plan with suggested candidate actions and supporting reasoning
- Understand the basis of each recommendation without reading a long-form report
- See explicit "Data unavailable" labels for any field where market data is absent, with no AI-invented substitutes
