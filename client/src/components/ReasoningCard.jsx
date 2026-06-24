export default function ReasoningCard({ reasoning }) {
  if (!reasoning) return null;
  return (
    <div className="card">
      <div className="card-label"><span className="accent">◆</span> Agent Reasoning</div>
      <div className="reasoning-box">{reasoning}</div>
    </div>
  );
}
