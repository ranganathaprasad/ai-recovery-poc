import { C } from "../constants";

export default function SeverityCard({ severity, guardrails }) {
  const isSevere = severity?.is_severe;
  const flags    = severity?.flags || [];
  const warnings = guardrails?.warnings || [];

  return (
    <div className="card">
      <div className="card-label"><span className="accent">◆</span> Severity & Guardrails</div>

      <div className="tags-wrap">
        <span
          className="tag"
          style={{
            background: isSevere ? "#F5455C20" : "#00C9A720",
            color:      isSevere ? "#F5455C"   : "#00C9A7",
          }}
        >
          {isSevere ? "🔴 Severe" : "🟢 Stable"}
        </span>
        {flags.map((f, i) => (
          <span key={i} className="tag" style={{ background: "#F5A62320", color: "#F5A623" }}>
            {f}
          </span>
        ))}
      </div>

      {warnings.length > 0 && (
        <>
          <div style={{ fontSize: 10, color: "#4A6174", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 7 }}>
            Guardrail Warnings
          </div>
          {warnings.map((w, i) => (
            <div key={i} className="guardrail-warning">
              <span>⚠</span> {w}
            </div>
          ))}
        </>
      )}

      {warnings.length === 0 && (
        <div style={{ fontSize: 12, color: "#7A94A8", lineHeight: 1.5 }}>
          ✓ All guardrails passed — input validated, output within clinical bounds.
        </div>
      )}
    </div>
  );
}
