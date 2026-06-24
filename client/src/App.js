import { useState, useEffect } from "react";
import "./styles.css";
import { API } from "./constants";
import { C } from "./constants";

import Sidebar        from "./components/Sidebar";
import ForecastCard   from "./components/ForecastCard";
import DecisionBanner from "./components/DecisionBanner";
import EmailStatus    from "./components/EmailStatus";
import NarrativeCard  from "./components/NarrativeCard";
import DriversCard    from "./components/DriversCard";
import CohortChart    from "./components/CohortChart";
import ReasoningCard  from "./components/ReasoningCard";
import SeverityCard   from "./components/SeverityCard";
import ModelMetaCard  from "./components/ModelMetaCard";

// ── Normalise API response — handles slight key differences ──────────────────
function normalise(data) {
  const pred = data?.prediction || data;
  const forecast = pred?.forecast || {};

  // Normalise forecast: convert range array to range_low/high, confidence 0-100 to 0-1
  const normForecast = {};
  for (const [key, val] of Object.entries(forecast)) {
    normForecast[key] = {
      ...val,
      range_low:        val?.range?.[0],
      range_high:       val?.range?.[1],
      confidence:       (val?.confidence || 0) / 100,
      confidence_label: val?.label,
    };
  }

  // Normalise drivers: convert {key, label} objects to plain strings
  const rawDrivers = pred?.drivers || {};
  const normDrivers = {
    positive: (rawDrivers.positive || []).map(d => d?.label || d),
    concerns: (rawDrivers.concern  || []).map(d => d?.label || d),
  };

  // Normalise model_meta keys
  const mm = pred?.model_meta || {};
  const normMeta = {
    rom_mae:   mm.rom_test_mae,
    pain_mae:  mm.pain_test_mae,
    steps_mae: mm.steps_test_mae,
  };

  return {
    forecast:   normForecast,
    drivers:    normDrivers,
    cohort:     pred?.cohort || {},
    severity:   pred?.severity || {},
    guardrails: pred?.guardrails || {},
    insight:    pred?.insight,
    modelMeta:  normMeta,
    narrative:  data?.narrative?.narrative || data?.narrative,
    agent:      data?.agent,
  };
}

export default function App() {
  const [patients,     setPatients]     = useState([]);
  const [search,       setSearch]       = useState("");
  const [selected,     setSelected]     = useState(null);
  const [result,       setResult]       = useState(null);
  const [resultType,   setResultType]   = useState(null);
  const [loading,      setLoading]      = useState(false);
  const [loadingType,  setLoadingType]  = useState(null);
  const [error,        setError]        = useState(null);

  // ── Fetch patient list on mount ──────────────────────────────────────────
  useEffect(() => {
    fetch(`${API}/patients`)
      .then((r) => r.json())
      .then((d) => setPatients(Array.isArray(d) ? d : d.patients || []))
      .catch(() => setError("Cannot connect to API at localhost:3000. Is the Node server running?"));
  }, []);

  // ── Select patient — clear previous result ───────────────────────────────
  const handleSelect = (patient) => {
    setSelected(patient);
    setResult(null);
    setResultType(null);
    setError(null);
  };

  // ── Call API ─────────────────────────────────────────────────────────────
  const callPredict = async (type) => {
    if (!selected) return;
    setLoading(true);
    setLoadingType(type);
    setResult(null);
    setResultType(null);
    setError(null);

    const urls = {
      predict: `${API}/predict/${selected.patient_id}`,
      narrate: `${API}/predict/narrate/${selected.patient_id}`,
      full:    `${API}/predict/full/${selected.patient_id}`,
    };

    try {
      const res = await fetch(urls[type], { method: "POST" });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      setResult(normalise(data));
      setResultType(type);
    } catch (e) {
      setError(e.message || "Prediction failed. Check console for details.");
    } finally {
      setLoading(false);
      setLoadingType(null);
    }
  };

  // ── Filtered patient list ────────────────────────────────────────────────
  const filtered = patients.filter((p) =>
    (p.name || "").toLowerCase().includes(search.toLowerCase())
  );

  // ── Destructure result ───────────────────────────────────────────────────
  const { forecast, drivers, cohort, severity, guardrails, narrative, agent, modelMeta } = result || {};

  const hasForecast  = forecast?.rom || forecast?.pain || forecast?.steps;
  const hasNarrative = !!narrative;
  const hasAgent     = !!agent?.decision;

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <Sidebar
        patients={filtered}
        selected={selected}
        onSelect={handleSelect}
        search={search}
        onSearch={setSearch}
      />

      {/* ── Main Panel ── */}
      <main className="main">
        {!selected ? (
          <div className="empty-state">
            <div className="empty-icon">🏥</div>
            <h2>No patient selected</h2>
            <p>Choose a patient from the list to run a recovery prediction.</p>
          </div>
        ) : (
          <>
            {/* ── Header ── */}
            <div className="main-header">
              <div className="patient-title">
                <h1>{selected.name}</h1>
                <p>
                  Patient ID {selected.id}
                  {selected.age    ? ` · ${selected.age} yrs`    : ""}
                  {selected.gender ? ` · ${selected.gender}`     : ""}
                  {selected.height ? ` · ${selected.height} cm`  : ""}
                </p>
              </div>

              <div className="action-buttons">
                <button
                  className="btn btn-ghost"
                  onClick={() => callPredict("predict")}
                  disabled={loading}
                >
                  {loadingType === "predict" ? "…" : "⚡"} Predict
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => callPredict("narrate")}
                  disabled={loading}
                >
                  {loadingType === "narrate" ? "…" : "📋"} Narrate
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => callPredict("full")}
                  disabled={loading}
                >
                  {loadingType === "full" ? "Running…" : "🚀 Full Analysis"}
                </button>
              </div>
            </div>

            {/* ── Content ── */}
            <div className="content">

              {/* Loading */}
              {loading && (
                <div className="loading-wrap">
                  <div className="loading-dots">
                    <div className="dot" />
                    <div className="dot" />
                    <div className="dot" />
                  </div>
                  <div className="loading-label">
                    {loadingType === "full"
                      ? "Running full pipeline — predict → narrate → agent…"
                      : loadingType === "narrate"
                      ? "Generating clinical narrative…"
                      : "Running prediction models…"}
                  </div>
                </div>
              )}

              {/* Error */}
              {error && !loading && (
                <div className="error-banner">⚠️ {error}</div>
              )}

              {/* Results */}
              {result && !loading && (
                <>
                  {/* Decision Banner */}
                  {hasAgent && <DecisionBanner agent={agent} />}

                  {/* Email Status */}
                  <EmailStatus agent={agent} visible={resultType === "full"} />

                  {/* Forecast Cards */}
                  {hasForecast && (
                    <div className="grid-3">
                      <ForecastCard
                        label="ROM"
                        value={forecast.rom?.prediction}
                        unit="%"
                        rangeLow={forecast.rom?.range_low}
                        rangeHigh={forecast.rom?.range_high}
                        confidence={forecast.rom?.confidence}
                        confidenceLabel={forecast.rom?.confidence_label}
                        color="#4A9EF5"
                      />
                      <ForecastCard
                        label="Pain"
                        value={forecast.pain?.prediction}
                        unit="/ 10"
                        rangeLow={forecast.pain?.range_low}
                        rangeHigh={forecast.pain?.range_high}
                        confidence={forecast.pain?.confidence}
                        confidenceLabel={forecast.pain?.confidence_label}
                        color={forecast.pain?.prediction > 6 ? "#F5455C" : "#00C9A7"}
                      />
                      <ForecastCard
                        label="Steps"
                        value={forecast.steps?.prediction}
                        unit="steps/day"
                        rangeLow={forecast.steps?.range_low}
                        rangeHigh={forecast.steps?.range_high}
                        confidence={forecast.steps?.confidence}
                        confidenceLabel={forecast.steps?.confidence_label}
                        color="#F5A623"
                      />
                    </div>
                  )}

                  {/* Narrative + Drivers */}
                  <div className="grid-2">
                    {hasNarrative && <NarrativeCard narrative={narrative} />}
                    <DriversCard drivers={drivers} />
                  </div>

                  {/* Cohort */}
                  <CohortChart forecast={forecast} cohort={cohort} />

                  {/* Reasoning + Severity */}
                  <div className="grid-2">
                    {hasAgent && <ReasoningCard reasoning={agent.reasoning} />}
                    <SeverityCard severity={severity} guardrails={guardrails} />
                  </div>

                  {/* Model Meta */}
                  <ModelMetaCard modelMeta={modelMeta} />
                </>
              )}

              {/* Empty result state */}
              {!result && !loading && !error && (
                <div className="empty-state" style={{ minHeight: 300 }}>
                  <div className="empty-icon">🔬</div>
                  <h2>Ready to analyse</h2>
                  <p>
                    Click <strong>Full Analysis</strong> to run the complete pipeline,
                    or use <strong>Predict</strong> / <strong>Narrate</strong> for partial results.
                  </p>
                </div>
              )}

            </div>
          </>
        )}
      </main>
    </div>
  );
}
