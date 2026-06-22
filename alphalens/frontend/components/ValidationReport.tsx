import type { ValidationReport as ValidationReportType } from "../lib/types";
import InsightCard from "./InsightCard";
import ReportShell from "./ReportShell";

interface ValidationReportProps {
  report: ValidationReportType;
  title?: string;
}

export default function ValidationReport({
  report,
  title = "Ticker validation",
}: ValidationReportProps) {
  return (
    <ReportShell
      title={title}
      methodologyNote={report.methodologyNote}
      variant="validation"
      subtitle="Market data checks and ticker-level validation notes."
    >
      <div className="report-callout report-callout-validation">
        <p className="report-summary">{report.executiveSummary}</p>
      </div>

      {report.candidateNotes.length > 0 && (
        <div className="report-section">
          <h3 className="report-section-title">
            Per-ticker notes
            <span className="report-section-count">{report.candidateNotes.length}</span>
          </h3>
          <div className="insight-grid">
            {report.candidateNotes.map((item) => (
              <InsightCard
                key={item.ticker}
                ticker={item.ticker}
                summary={item.summary}
                tone="validation"
              />
            ))}
          </div>
        </div>
      )}
    </ReportShell>
  );
}
