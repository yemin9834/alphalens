import { normalizeAnalysisResult } from "../lib/normalize-analysis";
import {
  actionTypeClass,
  formatSignalKey,
  viewPillClass,
} from "../lib/report-ui";
import type { PortfolioAnalyzeResponse } from "../lib/types";

interface AnalysisResultsProps {
  result: PortfolioAnalyzeResponse | Record<string, unknown>;
}

export default function AnalysisResults({ result }: AnalysisResultsProps) {
  const normalized = normalizeAnalysisResult(result);

  if (!normalized) {
    return (
      <section className="card report-card">
        <p className="muted">No analysis results to display.</p>
      </section>
    );
  }

  const { portfolioSignals, candidateRecommendations, actions } = normalized;

  return (
    <div className="results-stack">
      <section className="card report-card report-card-results">
        <div className="report-header">
          <div className="report-title-block">
            <span className="report-icon" aria-hidden>
              ▣
            </span>
            <div>
              <h2>Portfolio view</h2>
              <p className="muted report-subtitle">
                Synthesized portfolio posture after full pipeline analysis.
              </p>
            </div>
          </div>
        </div>

        <div className="metric-grid">
          <div className="metric-card">
            <span className="stat-label">Final view</span>
            <span className="metric-value">{normalized.finalView || "—"}</span>
          </div>
          <div className="metric-card">
            <span className="stat-label">Risk level</span>
            <span className="metric-value">{normalized.riskLevel || "—"}</span>
          </div>
          <div className="metric-card">
            <span className="stat-label">Market</span>
            <span className="metric-value">{normalized.marketCondition || "—"}</span>
          </div>
        </div>

        <div className="report-section">
          <h3 className="report-section-title">Portfolio signals</h3>
          <div className="signal-grid">
            {Object.entries(portfolioSignals).map(([key, value]) => (
              <div key={key} className="signal-card">
                <span className="signal-card-label">{formatSignalKey(key)}</span>
                <span className="signal-card-value">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {candidateRecommendations.length > 0 && (
        <section className="card report-card">
          <div className="report-header">
            <h2>Candidate recommendations</h2>
            <span className="candidate-count-pill">
              {candidateRecommendations.length}
            </span>
          </div>
          <div className="rec-grid">
            {candidateRecommendations.map((rec) => (
              <article key={rec.ticker} className="rec-card rec-card-enhanced">
                <header>
                  <h3>{rec.ticker}</h3>
                  <span className={viewPillClass(rec.view)}>{rec.view}</span>
                </header>
                <dl className="rec-detail-list">
                  <div>
                    <dt>Portfolio fit</dt>
                    <dd>{rec.portfolioFit}</dd>
                  </div>
                  <div className="rec-detail-positive">
                    <dt>Positive signal</dt>
                    <dd>{rec.positiveSignal}</dd>
                  </div>
                  <div className="rec-detail-risk">
                    <dt>Risk signal</dt>
                    <dd>{rec.riskSignal}</dd>
                  </div>
                  {rec.suggestedEntryRange && (
                    <div>
                      <dt>Entry range</dt>
                      <dd>{rec.suggestedEntryRange}</dd>
                    </div>
                  )}
                  <div>
                    <dt>Position sizing</dt>
                    <dd className="muted">{rec.positionSizingGuidance}</dd>
                  </div>
                </dl>
                {rec.fitNote && <p className="rec-fit-note">{rec.fitNote}</p>}
              </article>
            ))}
          </div>
        </section>
      )}

      {actions.length > 0 && (
        <section className="card report-card">
          <div className="report-header">
            <h2>Recommended actions</h2>
            <span className="candidate-count-pill">{actions.length}</span>
          </div>
          <ul className="action-timeline">
            {actions.map((action, i) => (
              <li key={`${action.ticker}-${i}`} className="action-timeline-item">
                <div className="action-timeline-marker" aria-hidden />
                <div className="action-timeline-body">
                  <header className="action-timeline-header">
                    <span className={actionTypeClass(action.type)}>{action.type}</span>
                    <strong className="action-timeline-ticker">{action.ticker}</strong>
                    {action.amount > 0 && (
                      <span className="action-timeline-amount">{action.amount}%</span>
                    )}
                  </header>
                  <p>{action.reason}</p>
                  {action.narrativeReason && (
                    <p className="muted action-timeline-narrative">{action.narrativeReason}</p>
                  )}
                  {action.suggestedEntryRange && (
                    <p className="muted">Entry: {action.suggestedEntryRange}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
