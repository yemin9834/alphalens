import Link from "next/link";
import { useMemo, type KeyboardEvent } from "react";
import type { RankCandidateInput } from "../lib/types";

const RELATIONSHIP_OPTIONS = [
  "supplier",
  "partner",
  "customer",
  "competitor",
  "adjacent",
  "other",
] as const;

function normalizeRelationship(value: string): string {
  return value.trim().toLowerCase() || "other";
}

function formatRelationship(value: string): string {
  if (!value) return "Other";
  const normalized = normalizeRelationship(value);
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function relationshipPillClass(value: string): string {
  const key = normalizeRelationship(value);
  if (key === "supplier") return "pill pill-high";
  if (key === "partner") return "pill pill-medium";
  if (key === "competitor") return "pill pill-low";
  return "pill";
}

function groupCandidates(
  candidates: RankCandidateInput[]
): { relationship: string; label: string; items: RankCandidateInput[] }[] {
  const buckets = new Map<string, RankCandidateInput[]>();

  for (const candidate of candidates) {
    const key = normalizeRelationship(candidate.relationshipType);
    const list = buckets.get(key) ?? [];
    list.push(candidate);
    buckets.set(key, list);
  }

  const known = RELATIONSHIP_OPTIONS.filter((key) => buckets.has(key)).map((key) => ({
    relationship: key,
    label: formatRelationship(key),
    items: [...(buckets.get(key) ?? [])].sort((a, b) =>
      a.ticker.localeCompare(b.ticker)
    ),
  }));

  const unknown = [...buckets.keys()]
    .filter((key) => !RELATIONSHIP_OPTIONS.includes(key as (typeof RELATIONSHIP_OPTIONS)[number]))
    .sort()
    .map((key) => ({
      relationship: key,
      label: formatRelationship(key),
      items: [...(buckets.get(key) ?? [])].sort((a, b) =>
        a.ticker.localeCompare(b.ticker)
      ),
    }));

  return [...known, ...unknown];
}

interface CandidatePoolPanelProps {
  candidates: RankCandidateInput[];
  manualTicker: string;
  manualRel: string;
  onManualTickerChange: (value: string) => void;
  onManualRelChange: (value: string) => void;
  onAdd: () => void;
  onRemove: (ticker: string) => void;
  onClearAll?: () => void;
}

export default function CandidatePoolPanel({
  candidates,
  manualTicker,
  manualRel,
  onManualTickerChange,
  onManualRelChange,
  onAdd,
  onRemove,
  onClearAll,
}: CandidatePoolPanelProps) {
  const grouped = useMemo(() => groupCandidates(candidates), [candidates]);

  const handleAddKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onAdd();
    }
  };

  return (
    <section className="card candidate-pool-card">
      <div className="candidate-pool-header">
        <div>
          <h2>Candidate pool</h2>
          <p className="muted candidate-pool-subtitle">
            Ecosystem tickers grouped by relationship to your core theme.
          </p>
        </div>
        <div className="candidate-pool-meta">
          <span className="candidate-count-pill">
            {candidates.length} {candidates.length === 1 ? "candidate" : "candidates"}
          </span>
          {grouped.length > 1 && (
            <span className="candidate-group-count muted">
              {grouped.length} groups
            </span>
          )}
          {candidates.length > 0 && onClearAll && (
            <button type="button" className="btn btn-ghost" onClick={onClearAll}>
              Clear all
            </button>
          )}
        </div>
      </div>

      {candidates.length === 0 ? (
        <div className="candidate-pool-empty">
          <div className="candidate-pool-empty-icon" aria-hidden>
            ◎
          </div>
          <p className="candidate-pool-empty-title">No candidates yet</p>
          <p className="muted">
            Run discovery to load an ecosystem, populate test data, or add tickers
            manually below.
          </p>
          <div className="btn-row candidate-pool-empty-actions">
            <Link href="/discover" className="btn btn-primary">
              Run discovery
            </Link>
          </div>
        </div>
      ) : (
        <div className="candidate-groups">
          {grouped.map((group) => (
            <section key={group.relationship} className="candidate-group">
              <header className="candidate-group-header">
                <span className={relationshipPillClass(group.relationship)}>
                  {group.label}
                </span>
                <span className="candidate-group-count muted">
                  {group.items.length}{" "}
                  {group.items.length === 1 ? "ticker" : "tickers"}
                </span>
              </header>
              <ul className="candidate-chip-list">
                {group.items.map((c) => (
                  <li key={c.ticker}>
                    <span className="candidate-chip">
                      <span className="candidate-chip-ticker">{c.ticker}</span>
                      <button
                        type="button"
                        className="candidate-chip-remove"
                        onClick={() => onRemove(c.ticker)}
                        aria-label={`Remove ${c.ticker}`}
                      >
                        ×
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      <div className="candidate-add-panel">
        <p className="candidate-add-label">Add candidate</p>
        <div className="candidate-add-form">
          <label className="candidate-add-field">
            <span>Ticker</span>
            <input
              value={manualTicker}
              onChange={(e) => onManualTickerChange(e.target.value.toUpperCase())}
              onKeyDown={handleAddKeyDown}
              placeholder="TSM"
              maxLength={12}
            />
          </label>
          <label className="candidate-add-field">
            <span>Relationship</span>
            <select
              value={manualRel}
              onChange={(e) => onManualRelChange(e.target.value)}
            >
              {RELATIONSHIP_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {formatRelationship(opt)}
                </option>
              ))}
              {!RELATIONSHIP_OPTIONS.includes(
                manualRel as (typeof RELATIONSHIP_OPTIONS)[number]
              ) && manualRel ? (
                <option value={manualRel}>{formatRelationship(manualRel)}</option>
              ) : null}
            </select>
          </label>
          <button
            type="button"
            className="btn btn-primary candidate-add-btn"
            onClick={onAdd}
            disabled={!manualTicker.trim()}
          >
            Add
          </button>
        </div>
      </div>
    </section>
  );
}
