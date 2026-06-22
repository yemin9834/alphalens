import type { PortfolioReport as PortfolioReportType } from "../lib/types";
import { actionTypeClass } from "../lib/report-ui";
import InsightCard from "./InsightCard";
import ReportShell from "./ReportShell";

interface PortfolioReportProps {
  report: PortfolioReportType;
  title?: string;
}

export default function PortfolioReport({
  report,
  title = "Portfolio recommendation",
}: PortfolioReportProps) {
  return (
    <ReportShell
      title={title}
      methodologyNote={report.methodologyNote}
      variant="portfolio"
      subtitle="Portfolio-aware actions and candidate fit from the portfolio agent."
    >
      <div className="report-callout report-callout-portfolio">
        <p className="report-summary">{report.executiveSummary}</p>
      </div>

      {report.portfolioSignalsSummary && (
        <div className="report-market-box">
          <p className="report-market-label">Portfolio signals</p>
          <p>{report.portfolioSignalsSummary}</p>
        </div>
      )}

      {report.actionNotes.length > 0 && (
        <div className="report-section">
          <h3 className="report-section-title">
            Action notes
            <span className="report-section-count">{report.actionNotes.length}</span>
          </h3>
          <div className="insight-grid">
            {report.actionNotes.map((item) => (
              <InsightCard
                key={`${item.ticker}-${item.type}`}
                ticker={item.ticker}
                summary={item.summary}
                tone="action"
                badge={
                  <span className={actionTypeClass(item.type)}>{item.type}</span>
                }
              />
            ))}
          </div>
        </div>
      )}

      {report.candidateNotes.length > 0 && (
        <div className="report-section">
          <h3 className="report-section-title">
            Candidate fit notes
            <span className="report-section-count">{report.candidateNotes.length}</span>
          </h3>
          <div className="insight-grid">
            {report.candidateNotes.map((item) => (
              <InsightCard
                key={item.ticker}
                ticker={item.ticker}
                summary={item.summary}
                tone="default"
              />
            ))}
          </div>
        </div>
      )}
    </ReportShell>
  );
}
