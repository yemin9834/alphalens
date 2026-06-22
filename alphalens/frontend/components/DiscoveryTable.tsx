import { Fragment, useState } from "react";
import DeepResearchPanel from "./DeepResearchPanel";
import type { DiscoveryCandidate } from "../lib/types";

interface DiscoveryTableProps {
  candidates: DiscoveryCandidate[];
  selected: Set<string>;
  onToggle: (ticker: string) => void;
  highlightTicker?: string | null;
  researchingTicker?: string | null;
}

export default function DiscoveryTable({
  candidates,
  selected,
  onToggle,
  highlightTicker = null,
  researchingTicker = null,
}: DiscoveryTableProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggleExpanded = (ticker: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
  };

  if (candidates.length === 0) {
    return <p className="muted">No candidates returned.</p>;
  }

  return (
    <div className="table-wrap">
      <table className="data-table discovery-table">
        <thead>
          <tr>
            <th>Use</th>
            <th>Ticker</th>
            <th>Company</th>
            <th>Relationship</th>
            <th>Confidence</th>
            <th>Research</th>
            <th>Summary</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => {
            const hasReport = Boolean(c.deepResearch);
            const isResearching = researchingTicker === c.ticker;
            const isExpanded = expanded.has(c.ticker);

            return (
              <Fragment key={c.ticker}>
                <tr
                  className={
                    highlightTicker === c.ticker ? "discovery-row-enter" : undefined
                  }
                >
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(c.ticker)}
                      disabled={c.tickerValidation === "invalid"}
                      onChange={() => onToggle(c.ticker)}
                      aria-label={`Select ${c.ticker}`}
                    />
                  </td>
                  <td>
                    <strong>{c.ticker}</strong>
                  </td>
                  <td>{c.companyName}</td>
                  <td>{c.relationshipType}</td>
                  <td>
                    <span className={`pill pill-${c.confidence.toLowerCase()}`}>
                      {c.confidence}
                    </span>
                  </td>
                  <td className="discovery-research-cell">
                    {hasReport ? (
                      <button
                        type="button"
                        className="btn btn-sm discovery-research-toggle"
                        onClick={() => toggleExpanded(c.ticker)}
                        aria-expanded={isExpanded}
                      >
                        {isExpanded ? "Hide" : "View"}
                        {c.deepResearch?.entryView?.opportunityView && (
                          <span
                            className={`pill pill-research-${c.deepResearch.entryView.opportunityView.toLowerCase()}`}
                          >
                            {c.deepResearch.entryView.opportunityView}
                          </span>
                        )}
                      </button>
                    ) : isResearching ? (
                      <span className="discovery-research-pending">Researching…</span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="cell-summary">{c.relationshipSummary}</td>
                </tr>
                {hasReport && isExpanded && c.deepResearch && (
                  <tr className="discovery-research-row">
                    <td colSpan={7}>
                      <DeepResearchPanel report={c.deepResearch} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
