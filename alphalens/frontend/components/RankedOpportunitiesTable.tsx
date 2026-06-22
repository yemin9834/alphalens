import type { RankedCandidate } from "../lib/types";

interface RankedOpportunitiesTableProps {
  ranked: RankedCandidate[];
  title?: string;
  subtitle?: string;
  highlightTicker?: string | null;
  streaming?: boolean;
}

export default function RankedOpportunitiesTable({
  ranked,
  title = "Ranked opportunities",
  subtitle = "Deterministic scores from market metrics — available as soon as opportunity analysis completes.",
  highlightTicker = null,
  streaming = false,
}: RankedOpportunitiesTableProps) {
  if (ranked.length === 0) return null;

  return (
    <section className="card report-card report-card-analysis">
      <h2>
        {title}
        {streaming && ranked.length > 0 && (
          <span className="rank-stream-count"> — {ranked.length}+</span>
        )}
      </h2>
      {subtitle && <p className="muted">{subtitle}</p>}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>View</th>
              <th>Score</th>
              <th>Entry</th>
              <th>Risk</th>
              <th>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((r) => (
              <tr
                key={r.ticker}
                className={
                  highlightTicker === r.ticker ? "discovery-row-enter" : undefined
                }
              >
                <td>
                  <strong>{r.ticker}</strong>
                  <div className="muted">{r.companyName}</div>
                </td>
                <td>{r.opportunityView}</td>
                <td>
                  {r.opportunityScore != null ? r.opportunityScore.toFixed(1) : "—"}
                </td>
                <td>{r.entryAttractiveness}</td>
                <td>{r.downsideRisk}</td>
                <td className="cell-summary">{r.attractiveEntryReason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
