export default function NarrativeCard({ narrative }) {
  if (!narrative) return null;
  return (
    <div className="card">
      <div className="card-label"><span className="accent">◆</span> Clinical Narrative</div>
      <div className="narrative-text">{narrative}</div>
    </div>
  );
}
