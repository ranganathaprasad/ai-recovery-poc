import { C } from "../constants";

function DriverItem({ text, type }) {
  const isPositive = type === "positive";
  return (
    <div
      className="driver-item"
      style={{ background: isPositive ? "#00C9A712" : "#F5455C12" }}
    >
      <div
        className="driver-dot"
        style={{ background: isPositive ? "#00C9A7" : "#F5455C" }}
      />
      <span style={{ color: "#E8F0F7" }}>{text}</span>
    </div>
  );
}

export default function DriversCard({ drivers }) {
  if (!drivers) return null;
  const positives = drivers.positive || [];
  const concerns  = drivers.concerns || [];

  return (
    <div className="card">
      <div className="card-label"><span className="accent">◆</span> SHAP Drivers</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div>
          <div className="drivers-col-label" style={{ color: "#00C9A7" }}>↑ Positive</div>
          {positives.length
            ? positives.map((d, i) => <DriverItem key={i} text={d} type="positive" />)
            : <div style={{ fontSize: 11, color: "#4A6174" }}>None identified</div>
          }
        </div>
        <div>
          <div className="drivers-col-label" style={{ color: "#F5455C" }}>↓ Concerns</div>
          {concerns.length
            ? concerns.map((d, i) => <DriverItem key={i} text={d} type="concern" />)
            : <div style={{ fontSize: 11, color: "#4A6174" }}>None identified</div>
          }
        </div>
      </div>
    </div>
  );
}
