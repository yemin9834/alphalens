-- AlphaLens database schema
-- Applied statement-by-statement via run_migrations.py (Data API limitation)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    clerk_user_id VARCHAR(255) PRIMARY KEY,
    display_name VARCHAR(255),
    risk_profile VARCHAR(50) DEFAULT 'balanced',
    investment_horizon VARCHAR(50) DEFAULT 'medium-term',
    acceptable_loss_pct DECIMAL(5,2),
    target_return DECIMAL(5,2),
    strategy_profile VARCHAR(100) DEFAULT 'default-risk-based',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clerk_user_id VARCHAR(255) NOT NULL REFERENCES users(clerk_user_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL DEFAULT 'Default Portfolio',
    cash_weight DECIMAL(6,2) DEFAULT 0,
    is_default BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS holdings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    weight DECIMAL(6,2) NOT NULL,
    cost_basis DECIMAL(12,4),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(portfolio_id, ticker)
);

CREATE TABLE IF NOT EXISTS discovery_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clerk_user_id VARCHAR(255) NOT NULL REFERENCES users(clerk_user_id) ON DELETE CASCADE,
    core_company VARCHAR(255) NOT NULL,
    core_ticker VARCHAR(20) NOT NULL,
    scope VARCHAR(50) DEFAULT 'level-1',
    status VARCHAR(20) DEFAULT 'pending',
    result_payload JSONB,
    warnings JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discovery_run_id UUID NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    ticker VARCHAR(20),
    relationship_type VARCHAR(50),
    relationship_summary TEXT,
    confidence VARCHAR(20),
    evidence_url TEXT,
    ticker_validation VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clerk_user_id VARCHAR(255) NOT NULL REFERENCES users(clerk_user_id) ON DELETE CASCADE,
    discovery_run_id UUID REFERENCES discovery_runs(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'pending',
    strategy_profile VARCHAR(100) DEFAULT 'default-risk-based',
    request_payload JSONB,
    ranked_payload JSONB,
    recommendation_payload JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_user ON discovery_runs(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_status ON discovery_runs(status);
CREATE INDEX IF NOT EXISTS idx_candidates_run ON candidates(discovery_run_id);
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_user ON analysis_jobs(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status ON analysis_jobs(status);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
