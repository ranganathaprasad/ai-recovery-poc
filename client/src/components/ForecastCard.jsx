import { confidenceColor, fmt } from "../utils";

export default function ForecastCard({ label, value, unit, rangeLow, rangeHigh, confidence, confidenceLabel, color }) {
  const pct = Math.min(100, Math.max(0, (confidence || 0) * 100));

  return (
    <div className="card">
      <div className="card-label">
        <span className="accent">◆</span> {label}
      </div>
      <div className="forecast-value" style={{ color }}>
        {fmt(value, label === "Steps" ? 0 : 1)}
        <span className="forecast-unit"> {unit}</span>
      </div>
      <div className="forecast-range">
        Range: {fmt(rangeLow)} – {fmt(rangeHigh)} {unit}
      </div>
      <div className="conf-bar">
        <div
          className="conf-fill"
          style={{ width: `${pct}%`, background: confidenceColor(confidenceLabel) }}
        />
      </div>
      <div className="conf-label" style={{ color: confidenceColor(confidenceLabel) }}>
        {confidenceLabel || "—"} confidence · {pct.toFixed(0)}%
      </div>
    </div>
  );
}
