import type { ReactNode } from "react";

type InsightTone = "default" | "opportunity" | "risk" | "validation" | "action";

interface InsightCardProps {
  ticker: string;
  summary: string;
  tone?: InsightTone;
  badge?: ReactNode;
  meta?: string;
}

export default function InsightCard({
  ticker,
  summary,
  tone = "default",
  badge,
  meta,
}: InsightCardProps) {
  return (
    <article className={`insight-card insight-card-${tone}`}>
      <header className="insight-card-header">
        <span className="insight-card-ticker">{ticker}</span>
        {badge}
      </header>
      {meta && <p className="insight-card-meta muted">{meta}</p>}
      <p className="insight-card-body">{summary}</p>
    </article>
  );
}
