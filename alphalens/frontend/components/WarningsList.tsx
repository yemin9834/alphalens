interface WarningsListProps {
  warnings?: string[] | null;
  title?: string;
}

export default function WarningsList({
  warnings = [],
  title = "Warnings",
}: WarningsListProps) {
  if (!warnings?.length) return null;

  return (
    <div className="warnings-banner banner-warn" role="status">
      <strong>{title}</strong>
      <ul className="warnings-list">
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </div>
  );
}
