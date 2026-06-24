import { avatarColor, initials } from "../utils";

export default function Sidebar({ patients, selected, onSelect, search, onSearch }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <div className="logo-icon">🫀</div>
          <div className="logo-text">RecoveryAI</div>
        </div>
        <div className="logo-sub">Clinical Decision Support</div>
      </div>

      <div className="search-wrap">
        <div className="search-box">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            placeholder="Search patients…"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="patient-list">
        <div className="list-label">Patients ({patients.length})</div>
        {patients.map((p) => {
          const [bgC, fgC] = avatarColor(p.name);
          return (
            <div
              key={p.id}
              className={`patient-item ${selected?.id === p.id ? "active" : ""}`}
              onClick={() => onSelect(p)}
            >
              <div className="patient-avatar" style={{ background: bgC, color: fgC }}>
                {initials(p.name)}
              </div>
              <div className="patient-info">
                <div className="patient-name">{p.name}</div>
                <div className="patient-meta">
                  {p.age || "—"}y · {p.gender || "—"} · ID {p.patient_id}
                </div>
              </div>
            </div>
          );
        })}
        {patients.length === 0 && (
          <div style={{ padding: "16px 18px", fontSize: 12, color: "#4A6174" }}>
            No patients found.
          </div>
        )}
      </div>
    </aside>
  );
}
