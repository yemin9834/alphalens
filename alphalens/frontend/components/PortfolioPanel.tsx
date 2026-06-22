import type { GetToken } from "../lib/api";
import TickerAutocomplete from "./TickerAutocomplete";
import type { PortfolioHolding } from "../lib/types";
import { ALLOCATION_COLORS, weightStatusClass } from "../lib/report-ui";

interface PortfolioPanelProps {
  holdings: PortfolioHolding[];
  riskProfile: string;
  weightTotal: number;
  populating: boolean;
  loading: boolean;
  getToken?: GetToken;
  onRiskProfileChange: (value: string) => void;
  onUpdateHolding: (index: number, field: keyof PortfolioHolding, value: string) => void;
  onAddHolding: () => void;
  onRemoveHolding: (index: number) => void;
  onPopulateTestData: () => void;
}

export default function PortfolioPanel({
  holdings,
  riskProfile,
  weightTotal,
  populating,
  loading,
  getToken,
  onRiskProfileChange,
  onUpdateHolding,
  onAddHolding,
  onRemoveHolding,
  onPopulateTestData,
}: PortfolioPanelProps) {
  const activeHoldings = holdings.filter((h) => h.ticker.trim());
  const weightClass = weightStatusClass(weightTotal);

  return (
    <section className="card portfolio-panel">
      <div className="report-header">
        <div className="report-title-block">
          <span className="report-icon" aria-hidden>
            ▣
          </span>
          <div>
            <h2>Your portfolio</h2>
            <p className="muted report-subtitle">
              Holdings and weights used for portfolio-aware recommendations.
            </p>
          </div>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={populating || loading}
          onClick={onPopulateTestData}
        >
          {populating ? "Populating…" : "Populate test data"}
        </button>
      </div>

      <div className="portfolio-toolbar">
        <label className="portfolio-risk-field">
          <span>Risk profile</span>
          <select
            value={riskProfile}
            onChange={(e) => onRiskProfileChange(e.target.value)}
          >
            <option value="conservative">Conservative</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </label>
        <div className={`portfolio-weight-summary ${weightClass}`}>
          <span className="stat-label">Total allocation</span>
          <span className="portfolio-weight-value">{weightTotal.toFixed(1)}%</span>
          <span className="portfolio-weight-hint">
            {weightClass === "weight-ok"
              ? "Ready to analyze"
              : weightClass === "weight-over"
                ? "Over-allocated — adjust weights"
                : "Under 100% — add cash or holdings"}
          </span>
        </div>
      </div>

      {activeHoldings.length > 0 && (
        <div className="allocation-bar" aria-label="Portfolio allocation">
          {activeHoldings.map((h, i) => (
            <div
              key={`${h.ticker}-${i}`}
              className="allocation-segment"
              style={{
                width: `${Math.max(0, Math.min(100, h.weight))}%`,
                backgroundColor: ALLOCATION_COLORS[i % ALLOCATION_COLORS.length],
              }}
              title={`${h.ticker} ${h.weight}%`}
            />
          ))}
        </div>
      )}

      <ul className="allocation-legend">
        {activeHoldings.map((h, i) => (
          <li key={`legend-${h.ticker}-${i}`}>
            <span
              className="allocation-swatch"
              style={{ backgroundColor: ALLOCATION_COLORS[i % ALLOCATION_COLORS.length] }}
            />
            <span className="allocation-legend-ticker">{h.ticker || "—"}</span>
            <span className="muted">{h.weight}%</span>
          </li>
        ))}
      </ul>

      <div className="holdings-editor">
        <p className="candidate-add-label">Edit holdings</p>
        {holdings.map((row, index) => (
          <div key={index} className="holding-row">
            <label>
              Ticker
              <TickerAutocomplete
                value={row.ticker}
                onChange={(value) => onUpdateHolding(index, "ticker", value)}
                getToken={getToken}
                disabled={loading || populating}
              />
            </label>
            <label>
              Weight %
              <input
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={row.weight}
                onChange={(e) => onUpdateHolding(index, "weight", e.target.value)}
              />
            </label>
            <button type="button" className="btn-remove-text" onClick={() => onRemoveHolding(index)}>
              Remove
            </button>
          </div>
        ))}
        <button type="button" className="btn" onClick={onAddHolding}>
          Add holding
        </button>
      </div>
    </section>
  );
}
