interface Props {
  label: string;
  value: string;
  sub?: string;
  variant?: "default" | "warn" | "danger";
}

export function MetricCard({ label, value, sub, variant = "default" }: Props) {
  return (
    <div className={`metric-card ${variant !== "default" ? variant : ""}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value mono">{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}
