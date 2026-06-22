import type { AnalysisReport as AnalysisReportType } from "../lib/types";
import InsightCard from "./InsightCard";
import ReportShell from "./ReportShell";

interface AnalysisReportProps {
  report: AnalysisReportType;
  title?: string;
}

export default function AnalysisReport({
  report,
  title = "Opportunity analysis",
}: AnalysisReportProps) {
  return (
    <ReportShell
      title={title}
      methodologyNote={report.methodologyNote}
      variant="analysis"
      subtitle="Ranked opportunity views and market context from the analyst agent."
    >
      <div className="report-callout report-callout-analysis">
        <p className="report-summary">{report.executiveSummary}</p>
      </div>

      {report.marketOverview && (
        <div className="report-market-box">
          <p className="report-market-label">Market overview</p>
          <p>{report.marketOverview}</p>
        </div>
      )}

      {report.topOpportunities.length > 0 && (
        <div className="report-section">
          <h3 className="report-section-title">
            Top opportunities
            <span className="report-section-count">{report.topOpportunities.length}</span>
          </h3>
          <div className="insight-grid">
            {report.topOpportunities.map((item) => (
              <InsightCard
                key={item.ticker}
                ticker={item.ticker}
                summary={item.summary}
                tone="opportunity"
              />
            ))}
          </div>
        </div>
      )}

      {report.risksToWatch.length > 0 && (
        <div className="report-section">
          <h3 className="report-section-title">
            Risks to watch
            <span className="report-section-count">{report.risksToWatch.length}</span>
          </h3>
          <div className="insight-grid">
            {report.risksToWatch.map((item) => (
              <InsightCard
                key={item.ticker}
                ticker={item.ticker}
                summary={item.summary}
                tone="risk"
              />
            ))}
          </div>
        </div>
      )}
    </ReportShell>
  );
}
