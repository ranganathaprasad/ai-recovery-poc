import { C } from "../constants";

export default function EmailStatus({ agent, visible }) {
  if (!visible) return null;
  return (
    <div
      className="email-status"
      style={{
        background: agent?.email_sent ? "#00C9A715" : "#162030",
        border:     `1px solid ${agent?.email_sent ? "#00C9A740" : "#243447"}`,
        color:      agent?.email_sent ? "#00C9A7"   : "#7A94A8",
      }}
    >
      <span>{agent?.email_sent ? "✉️ Alert email sent to physician" : "📭 No alert email sent"}</span>
      {agent?.email_error && (
        <span className="email-error">
          — {agent.email_error.split("\n")[0]}
        </span>
      )}
    </div>
  );
}
