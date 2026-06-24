import { DECISION_STYLE } from "../constants";
import { C } from "../constants";

export default function DecisionBanner({ agent }) {
  if (!agent?.decision) return null;
  const ds = DECISION_STYLE[agent.decision] || DECISION_STYLE.OK;

  return (
    <div
      className="decision-banner"
      style={{ background: ds.bg, borderColor: ds.border + "55", color: ds.color }}
    >
      <div className="decision-icon" style={{ background: ds.border + "25" }}>
        {ds.icon}
      </div>

      <div className="decision-text">
        <h3>
          {agent.decision}
          {agent.alert_reason ? ` — ${agent.alert_reason}` : ""}
        </h3>
        {agent.recommended_action && <p>{agent.recommended_action}</p>}
      </div>

      <div className="decision-right" style={{ color: ds.color }}>
        <div className="decision-conf-val">{agent.confidence}</div>
        <div className="decision-conf-lbl">Confidence</div>
        {agent.source && <div className="source-pill">{agent.source}</div>}
      </div>
    </div>
  );
}
