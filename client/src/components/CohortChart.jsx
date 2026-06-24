import { metricColor, fmt } from "../utils";

function CohortRow({ label, metric, patientVal, cohortVal, unit }) {
  const max = Math.max(patientVal || 0, cohortVal || 0) * 1.25 || 100;
  const pPct = ((patientVal || 0) / max) * 100;
  const cPct = ((cohortVal || 0) / max) * 100;
  const color = metricColor(metric, patientVal, cohortVal);

  return (
    <div className="cohort-row">
      <div className="cohort-lbl">{label}</div>
      <div className="cohort-bar-wrap">
        <div className="cohort-bar-fill" style={{ width: `${pPct}%`, background: color }} />
        <div
          className="cohort-marker"
          style={{ left: `${cPct}%` }}
          title={`Cohort avg: ${fmt(cohortVal)} ${unit}`}
        />
      </div>
      <div className="cohort-val">
        {fmt(patientVal)}
        <span style={{ color: "#4A6174" }}> / {fmt(cohortVal)}</span>
      </div>
    </div>
  );
}

export default function CohortChart({ forecast, cohort }) {
  if (!cohort?.averages) return null;
  const avg = cohort.averages;

  return (
    <div className="card grid-full">
      <div className="card-label">
        <span className="accent">◆</span> Cohort Comparison
        <span style={{ marginLeft: "auto", fontSize: 10, color: "#4A6174", textTransform: "none", letterSpacing: 0 }}>
          vs {cohort.similar_patients_count || 10} similar patients
        </span>
      </div>

      <div className="cohort-legend">
        <span>
          <span style={{ display: "inline-block", width: 20, height: 4, borderRadius: 2, background: "#00C9A7", marginRight: 4 }} />
          Patient prediction
        </span>
        <span>
          <span style={{ display: "inline-block", width: 2, height: 12, background: "#7A94A8", marginRight: 4 }} />
          Cohort average
        </span>
      </div>

      <CohortRow label="ROM" metric="rom"
        patientVal={forecast?.rom?.prediction} cohortVal={avg.rom} unit="%" />
      <CohortRow label="Pain" metric="pain"
        patientVal={forecast?.pain?.prediction} cohortVal={avg.pain} unit="/10" />
      <CohortRow label="Steps" metric="steps"
        patientVal={forecast?.steps?.prediction} cohortVal={avg.steps} unit="steps" />
    </div>
  );
}
