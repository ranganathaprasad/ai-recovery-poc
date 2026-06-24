import { fmt } from "../utils";

export default function ModelMetaCard({ modelMeta }) {
  if (!modelMeta) return null;
  const items = [
    { label: "ROM MAE", val: modelMeta.rom_mae != null ? `${fmt(modelMeta.rom_mae)}%` : "—" },
    { label: "Pain MAE", val: modelMeta.pain_mae != null ? fmt(modelMeta.pain_mae) : "—" },
    { label: "Steps MAE", val: modelMeta.steps_mae != null ? fmt(modelMeta.steps_mae, 0) : "—" },
  ];

  return (
    <div className="card grid-full">
      <div className="card-label"><span className="accent">◆</span> Model Performance (Test MAE)</div>
      <div className="model-meta-grid">
        {items.map((it) => (
          <div key={it.label} className="meta-item">
            <div className="meta-val">{it.val}</div>
            <div className="meta-lbl">{it.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
