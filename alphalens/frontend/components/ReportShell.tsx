import type { ReactNode } from "react";
import { isLlmNarrative } from "../lib/report-ui";

type ReportVariant = "validation" | "analysis" | "portfolio" | "results";

const VARIANT_ICON: Record<ReportVariant, string> = {
  validation: "✓",
  analysis: "◎",
  portfolio: "◆",
  results: "▣",
};

interface ReportShellProps {
  title: string;
  methodologyNote: string;
  variant?: ReportVariant;
  subtitle?: string;
  children: ReactNode;
}

export default function ReportShell({
  title,
  methodologyNote,
  variant = "analysis",
  subtitle,
  children,
}: ReportShellProps) {
  const llm = isLlmNarrative(methodologyNote);

  return (
    <section className={`card report-card report-card-${variant}`}>
      <div className="report-header">
        <div className="report-title-block">
          <span className="report-icon" aria-hidden>
            {VARIANT_ICON[variant]}
          </span>
          <div>
            <h2>{title}</h2>
            {subtitle && <p className="muted report-subtitle">{subtitle}</p>}
          </div>
        </div>
        <span className={`pill ${llm ? "pill-high" : ""}`}>
          {llm ? "LLM narrative" : "Deterministic"}
        </span>
      </div>
      {children}
      <p className="methodology-note muted">{methodologyNote}</p>
    </section>
  );
}
