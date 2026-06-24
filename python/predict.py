# ==========================================
# predict.py
# Called by Node via child_process.spawn
# Reads input JSON from stdin
# Writes output JSON to stdout
# ==========================================

import sys
import json
import pandas as pd
import numpy as np
import joblib
import shap
import os

# ==========================================
# PATHS
# ==========================================
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'models')

def model_path(filename):
    return os.path.join(MODEL_DIR, filename)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ==========================================
# GUARDRAILS — Input Validation
# ==========================================

VALID_PROCEDURES = [
    "Hip Replacement",
    "Knee Replacement",
    "Shoulder Surgery",
    "ACL Surgery"
]

# Clinical boundary: max realistic week-over-week change
MAX_ROM_CHANGE_PER_WEEK   = 20.0   # % — more than this is clinically improbable
MAX_PAIN_CHANGE_PER_WEEK  = 4.0    # points — sudden drop/spike over 4 is suspicious
MAX_STEPS_CHANGE_PER_WEEK = 3000   # steps — realistic daily activity ramp

# Data freshness: if input week is far behind expected week, warn
def check_data_freshness(current_week, program_start_date=None):
    """
    If current_week is provided but seems stale relative to
    program duration, flag it. For POC we use a simple rule:
    week > 12 is unusually long and may indicate stale data.
    """
    warnings = []
    if current_week > 12:
        warnings.append(
            f"Week {current_week} is beyond typical program length (12 weeks). "
            f"Prediction accuracy may be reduced — model was trained on weeks 1-12."
        )
    return warnings


def validate_input(data):
    errors = []

    # --- Required fields ---
    if not isinstance(data.get("rom_percent"), (int, float)):
        errors.append("rom_percent must be a number")
    elif not (0 <= data["rom_percent"] <= 100):
        errors.append(f"rom_percent out of range: {data['rom_percent']} (expected 0-100)")

    if not isinstance(data.get("pain_score"), (int, float)):
        errors.append("pain_score must be a number")
    elif not (0 <= data["pain_score"] <= 10):
        errors.append(f"pain_score out of range: {data['pain_score']} (expected 0-10)")

    if not isinstance(data.get("walking_steps"), (int, float)):
        errors.append("walking_steps must be a number")
    elif data["walking_steps"] < 0:
        errors.append("walking_steps cannot be negative")

    if not isinstance(data.get("exercise_adherence"), (int, float)):
        errors.append("exercise_adherence must be a number")
    elif not (0 <= data["exercise_adherence"] <= 100):
        errors.append(f"exercise_adherence out of range: {data['exercise_adherence']} (expected 0-100)")

    if data.get("procedure_type") not in VALID_PROCEDURES:
        errors.append(f"Unknown procedure_type: {data.get('procedure_type')}. Valid: {VALID_PROCEDURES}")

    if not isinstance(data.get("current_week"), int) or data["current_week"] < 1:
        errors.append("current_week must be an integer >= 1")

    return errors


# ==========================================
# GUARDRAILS — Clinical Boundary Check
# Catches unrealistic week-over-week changes
# that the model should not act on blindly
# ==========================================

def check_clinical_boundaries(data):
    """
    Detects improbable week-over-week changes.
    These don't block prediction but are flagged
    in the output so the doctor is aware.
    """
    warnings = []

    prev_rom   = data.get("prev_rom")
    prev_pain  = data.get("prev_pain")
    prev_steps = data.get("prev_steps")

    # Only check if prev values are available (not week 1)
    if prev_rom is not None and prev_rom != data["rom_percent"]:
        rom_change = abs(data["rom_percent"] - prev_rom)
        if rom_change > MAX_ROM_CHANGE_PER_WEEK:
            warnings.append(
                f"Unusually large ROM change detected: {rom_change:.1f}% in one week "
                f"(max expected: {MAX_ROM_CHANGE_PER_WEEK}%). Verify sensor data."
            )

    if prev_pain is not None and prev_pain != data["pain_score"]:
        pain_change = abs(data["pain_score"] - prev_pain)
        if pain_change > MAX_PAIN_CHANGE_PER_WEEK:
            warnings.append(
                f"Unusually large pain change detected: {pain_change:.1f} points in one week "
                f"(max expected: {MAX_PAIN_CHANGE_PER_WEEK}). Verify patient-reported data."
            )

    if prev_steps is not None and prev_steps != data["walking_steps"]:
        steps_change = abs(data["walking_steps"] - prev_steps)
        if steps_change > MAX_STEPS_CHANGE_PER_WEEK:
            warnings.append(
                f"Unusually large activity change detected: {int(steps_change)} steps in one week "
                f"(max expected: {MAX_STEPS_CHANGE_PER_WEEK}). Verify wearable data."
            )

    return warnings


# ==========================================
# GUARDRAILS — Output Clamping
# Model predictions must stay in valid ranges
# ==========================================

def clamp_output(rom_pred, pain_pred, steps_pred):
    rom_pred   = max(0.0, min(100.0, rom_pred))
    pain_pred  = max(0.0, min(10.0, pain_pred))
    steps_pred = max(0.0, steps_pred)
    return rom_pred, pain_pred, steps_pred


def clamp_intervals(low, high, min_val, max_val):
    return max(min_val, low), min(max_val, high)


# ==========================================
# CONFIDENCE — Quantile interval width
# ==========================================

CONFIDENCE_FLOOR = 0.40

def compute_confidence(pred, low, high, target_range):
    interval_width = abs(high - low)
    conf = 1.0 - (interval_width / target_range)
    return max(0.0, min(1.0, conf))

def confidence_label(conf):
    if conf < CONFIDENCE_FLOOR:
        return "Insufficient Data"
    elif conf >= 0.85:
        return "High"
    elif conf >= 0.70:
        return "Medium"
    else:
        return "Low"


# ==========================================
# LOAD MODELS
# ==========================================

def load_models():
    required = [
        "rom_model.pkl", "rom_features.pkl", "rom_mae.pkl",
        "rom_q_low.pkl", "rom_q_high.pkl",
        "pain_model.pkl", "pain_features.pkl", "pain_mae.pkl",
        "pain_q_low.pkl", "pain_q_high.pkl",
        "steps_model.pkl", "steps_features.pkl", "steps_mae.pkl",
        "steps_q_low.pkl", "steps_q_high.pkl",
        "knn_model.pkl", "knn_features.pkl", "knn_data.pkl",
        "knn_scaler.pkl", "knn_weights.pkl"
    ]
    for f in required:
        if not os.path.exists(model_path(f)):
            raise FileNotFoundError(f"Model file not found: {model_path(f)}. Run train_all.py first.")

    m = {}
    m["rom"]           = joblib.load(model_path("rom_model.pkl"))
    m["rom_features"]  = joblib.load(model_path("rom_features.pkl"))
    m["rom_mae"]       = joblib.load(model_path("rom_mae.pkl"))
    m["rom_q_low"]     = joblib.load(model_path("rom_q_low.pkl"))
    m["rom_q_high"]    = joblib.load(model_path("rom_q_high.pkl"))

    m["pain"]          = joblib.load(model_path("pain_model.pkl"))
    m["pain_features"] = joblib.load(model_path("pain_features.pkl"))
    m["pain_mae"]      = joblib.load(model_path("pain_mae.pkl"))
    m["pain_q_low"]    = joblib.load(model_path("pain_q_low.pkl"))
    m["pain_q_high"]   = joblib.load(model_path("pain_q_high.pkl"))

    m["steps"]          = joblib.load(model_path("steps_model.pkl"))
    m["steps_features"] = joblib.load(model_path("steps_features.pkl"))
    m["steps_mae"]      = joblib.load(model_path("steps_mae.pkl"))
    m["steps_q_low"]    = joblib.load(model_path("steps_q_low.pkl"))
    m["steps_q_high"]   = joblib.load(model_path("steps_q_high.pkl"))

    m["knn"]          = joblib.load(model_path("knn_model.pkl"))
    m["knn_features"] = joblib.load(model_path("knn_features.pkl"))
    m["knn_data"]     = joblib.load(model_path("knn_data.pkl"))
    m["knn_scaler"]   = joblib.load(model_path("knn_scaler.pkl"))
    m["knn_weights"]  = joblib.load(model_path("knn_weights.pkl"))

    return m


# ==========================================
# HELPERS
# ==========================================

def build_feature_row(data, features):
    row = {col: data.get(col, 0) for col in features}
    df = pd.DataFrame([row])
    return df[features].astype(float)


def get_shap_drivers(explainer, input_df):
    shap_values = explainer(input_df)
    feature_impact = list(zip(input_df.columns, shap_values.values[0]))

    important = [
        "rom_percent", "pain_score", "walking_steps",
        "exercise_adherence", "rom_change", "pain_change", "steps_change"
    ]

    filtered = [(f, float(v)) for f, v in feature_impact if f in important]
    if not filtered:
        return []

    max_abs = max(abs(v) for _, v in filtered)
    threshold = max_abs * 0.15

    filtered = sorted(filtered, key=lambda x: abs(x[1]), reverse=True)
    return [(f, v) for f, v in filtered if abs(v) > threshold][:4]


# ==========================================
# MAIN
# ==========================================

def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "No input received on stdin"}))
        sys.exit(1)

    try:
        input_data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {str(e)}"}))
        sys.exit(1)

    # --- Layer 1: Input validation ---
    errors = validate_input(input_data)
    if errors:
        print(json.dumps({"error": "Validation failed", "details": errors}))
        sys.exit(1)

    # --- Layer 2: Clinical boundary check ---
    clinical_warnings = check_clinical_boundaries(input_data)

    # --- Layer 3: Data freshness check ---
    freshness_warnings = check_data_freshness(input_data["current_week"])

    all_warnings = clinical_warnings + freshness_warnings

    # Build flat feature dict
    procedure = input_data["procedure_type"]
    gender    = input_data.get("gender", "Male")

    flat = {
        "current_week":       input_data["current_week"],
        "rom_percent":        input_data["rom_percent"],
        "pain_score":         input_data["pain_score"],
        "walking_steps":      input_data["walking_steps"],
        "exercise_adherence": input_data["exercise_adherence"],
        "survey_completed":   int(input_data.get("survey_completed", 1)),
        "age":                input_data.get("age", 45),
        "prev_rom":           input_data.get("prev_rom", input_data["rom_percent"]),
        "prev_pain":          input_data.get("prev_pain", input_data["pain_score"]),
        "prev_steps":         input_data.get("prev_steps", input_data["walking_steps"]),
    }

    flat["rom_change"]   = flat["rom_percent"]   - flat["prev_rom"]
    flat["pain_change"]  = flat["pain_score"]    - flat["prev_pain"]
    flat["steps_change"] = flat["walking_steps"] - flat["prev_steps"]

    for p in VALID_PROCEDURES:
        flat[f"procedure_type_{p}"] = 1 if procedure == p else 0

    for g in ["Female", "Male"]:
        flat[f"gender_{g}"] = 1 if gender == g else 0

    # Load models
    try:
        m = load_models()
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    # Build inputs
    rom_input   = build_feature_row(flat, m["rom_features"])
    pain_input  = build_feature_row(flat, m["pain_features"])
    steps_input = build_feature_row(flat, m["steps_features"])

    # Predictions
    rom_pred   = float(m["rom"].predict(rom_input)[0])
    pain_pred  = float(m["pain"].predict(pain_input)[0])
    steps_pred = float(m["steps"].predict(steps_input)[0])

    # Quantile intervals
    rom_low    = float(m["rom_q_low"].predict(rom_input)[0])
    rom_high   = float(m["rom_q_high"].predict(rom_input)[0])
    pain_low   = float(m["pain_q_low"].predict(pain_input)[0])
    pain_high  = float(m["pain_q_high"].predict(pain_input)[0])
    steps_low  = float(m["steps_q_low"].predict(steps_input)[0])
    steps_high = float(m["steps_q_high"].predict(steps_input)[0])

    # --- Layer 4: Output clamping ---
    rom_pred, pain_pred, steps_pred = clamp_output(rom_pred, pain_pred, steps_pred)
    rom_low,   rom_high   = clamp_intervals(rom_low,   rom_high,   0.0,  100.0)
    pain_low,  pain_high  = clamp_intervals(pain_low,  pain_high,  0.0,   10.0)
    steps_low, steps_high = clamp_intervals(steps_low, steps_high, 0.0, 99999)

    # Confidence
    rom_conf   = compute_confidence(rom_pred,   rom_low,   rom_high,   100.0)
    pain_conf  = compute_confidence(pain_pred,  pain_low,  pain_high,   10.0)
    steps_conf = compute_confidence(steps_pred, steps_low, steps_high, 5000.0)

    # KNN cohort
    knn_input = build_feature_row(flat, m["knn_features"])
    for col in knn_input.columns:
        if col in m["knn_weights"]:
            knn_input[col] *= m["knn_weights"][col]

    knn_scaled = m["knn_scaler"].transform(knn_input)
    _, indices = m["knn"].kneighbors(knn_scaled)
    similar    = m["knn_data"].iloc[indices[0]]

    avg_rom   = float(similar["next_week_rom"].mean())
    avg_pain  = float(similar["next_week_pain"].mean())
    avg_steps = float(similar["next_week_steps"].mean())

    # SHAP
    rom_explainer   = shap.TreeExplainer(m["rom"])
    pain_explainer  = shap.TreeExplainer(m["pain"])
    steps_explainer = shap.TreeExplainer(m["steps"])

    rom_drivers   = get_shap_drivers(rom_explainer,   rom_input)
    pain_drivers  = get_shap_drivers(pain_explainer,  pain_input)
    steps_drivers = get_shap_drivers(steps_explainer, steps_input)

    driver_map = {}
    for f, v in rom_drivers + pain_drivers + steps_drivers:
        driver_map[f] = driver_map.get(f, 0) + v
    top_drivers = sorted(driver_map.items(), key=lambda x: abs(x[1]), reverse=True)[:4]

    # Positive / concern
    positive = []
    concern  = []

    rom_change   = flat["rom_change"]
    pain_change  = flat["pain_change"]
    steps_change = flat["steps_change"]

    if flat["rom_percent"] > avg_rom or rom_change > 0:
        positive.append({"key": "mobility",   "label": f"Mobility improving (ROM: {round(flat['rom_percent'],1)}, change: {rom_change:+.1f})"})
    else:
        concern.append( {"key": "mobility",   "label": f"Mobility needs attention (ROM: {round(flat['rom_percent'],1)}, change: {rom_change:+.1f})"})

    if steps_pred > avg_steps or steps_change > 0:
        positive.append({"key": "activity",   "label": f"Activity increasing (Steps: {int(flat['walking_steps'])}, change: {int(steps_change):+d})"})
    else:
        concern.append( {"key": "activity",   "label": f"Activity low (Steps: {int(flat['walking_steps'])}, change: {int(steps_change):+d})"})

    if pain_pred < avg_pain or pain_change < 0:
        positive.append({"key": "pain",       "label": f"Pain reducing (Score: {round(flat['pain_score'],1)}, change: {pain_change:+.1f})"})
    else:
        concern.append( {"key": "pain",       "label": f"Pain elevated (Score: {round(flat['pain_score'],1)}, change: {pain_change:+.1f})"})

    if flat["exercise_adherence"] >= 70:
        positive.append({"key": "adherence",  "label": f"Good exercise adherence ({flat['exercise_adherence']}%)"})
    else:
        concern.append( {"key": "adherence",  "label": f"Low exercise adherence ({flat['exercise_adherence']}%)"})

    # Insight
    if pain_change < 0 and rom_change > 0:
        insight = "Recovery is progressing well — mobility is improving and pain is decreasing."
    elif pain_change < 0 and rom_change <= 0:
        insight = "Pain is improving but mobility needs more attention. Encourage ROM exercises."
    elif pain_change >= 0 and rom_change > 0:
        insight = "Mobility is improving but pain remains elevated. Monitor pain management."
    else:
        insight = "Recovery shows mixed signals. Close monitoring and clinician review recommended."

    # Severity flag for agent
    is_severe = (
        flat["pain_score"] >= 8 or
        (pain_pred > avg_pain and pain_change >= 0) or
        (flat["exercise_adherence"] < 40 and flat["current_week"] > 2) or
        (flat["rom_percent"] < avg_rom * 0.7)
    )

    output = {
        "input_summary": {
            "patient_id":     input_data.get("patient_id"),
            "procedure_type": procedure,
            "current_week":   flat["current_week"],
            "age":            flat["age"],
            "gender":         gender
        },
        "forecast": {
            "rom":   {"prediction": round(rom_pred,2),   "range": [round(rom_low,2),   round(rom_high,2)],   "confidence": round(rom_conf*100,1),   "label": confidence_label(rom_conf),   "unit": "%"},
            "pain":  {"prediction": round(pain_pred,2),  "range": [round(pain_low,2),  round(pain_high,2)],  "confidence": round(pain_conf*100,1),  "label": confidence_label(pain_conf),  "unit": "/10"},
            "steps": {"prediction": int(steps_pred),     "range": [int(steps_low),     int(steps_high)],     "confidence": round(steps_conf*100,1), "label": confidence_label(steps_conf), "unit": "steps/day"}
        },
        "insight": insight,
        "drivers": {
            "positive": positive,
            "concern":  concern
        },
        "cohort": {
            "similar_patients_count": len(similar),
            "averages":   {"rom": round(avg_rom,2), "pain": round(avg_pain,2), "steps": int(avg_steps)},
            "comparison": {
                "rom":      "Above average" if rom_pred > avg_rom else "Below average",
                "pain":     ("Low and improving"   if pain_pred < avg_pain and pain_change < 0
                        else "Low but increasing"  if pain_pred < avg_pain
                        else "Higher but improving" if pain_pred > avg_pain and pain_change < 0
                        else "Higher than average"),
                "activity": "Above average" if steps_pred > avg_steps else "Below average"
            }
        },
        "severity": {
            "is_severe": is_severe,
            "flags":     [c["label"] for c in concern]
        },
        "guardrails": {
            "warnings":         all_warnings,
            "has_warnings":     len(all_warnings) > 0,
            "input_validated":  True,
            "output_clamped":   True
        },
        "model_meta": {
            "rom_test_mae":   m["rom_mae"],
            "pain_test_mae":  m["pain_mae"],
            "steps_test_mae": m["steps_mae"]
        }
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
