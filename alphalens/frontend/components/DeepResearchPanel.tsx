import type { DeepCompanyReport, DiscoveryCandidate } from "../lib/types";

interface DeepResearchPanelProps {
  report: DeepCompanyReport;
}

export default function DeepResearchPanel({ report }: DeepResearchPanelProps) {
  const { marketSnapshot, entryView, relationshipToCore } = report;

  return (
    <div className="deep-research-panel">
      <p className="deep-research-summary">{report.executiveSummary}</p>

      <div className="deep-research-grid">
        <div className="deep-research-stat">
          <span className="stat-label">Opportunity view</span>
          <strong>{entryView.opportunityView}</strong>
        </div>
        <div className="deep-research-stat">
          <span className="stat-label">Entry attractiveness</span>
          <strong>{marketSnapshot.entryAttractiveness}</strong>
        </div>
        <div className="deep-research-stat">
          <span className="stat-label">Suggested entry</span>
          <strong>{marketSnapshot.suggestedEntryRange}</strong>
        </div>
        <div className="deep-research-stat">
          <span className="stat-label">Valuation</span>
          <strong>{marketSnapshot.valuation}</strong>
        </div>
      </div>

      {entryView.rationale && (
        <p className="muted deep-research-rationale">{entryView.rationale}</p>
      )}

      {relationshipToCore?.summary && (
        <p className="muted deep-research-relationship">
          <strong>{relationshipToCore.type || "Ecosystem"}:</strong>{" "}
          {relationshipToCore.summary}
        </p>
      )}

      {(entryView.keyRisks?.length ?? 0) > 0 && (
        <ul className="deep-research-risks">
          {entryView.keyRisks!.map((risk) => (
            <li key={risk}>{risk}</li>
          ))}
        </ul>
      )}

      {(report.warnings?.length ?? 0) > 0 && (
        <ul className="deep-research-warnings">
          {report.warnings!.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function candidateWithReport(
  candidate: DiscoveryCandidate,
  report: DeepCompanyReport
): DiscoveryCandidate {
  return { ...candidate, deepResearch: report };
}
