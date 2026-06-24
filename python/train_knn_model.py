import sys
import os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ==========================================
# train_knn_model.py
# Weights applied ONCE at train time only
# ==========================================

import pandas as pd
import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import joblib

# ===============================
# PATHS
# ===============================
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

def model_path(filename):
    return os.path.join(MODEL_DIR, filename)

# ===============================
# STEP 1: LOAD + CLEAN
# ===============================
df = pd.read_csv(os.path.join(BASE_DIR, "training_data.csv"))

df["prev_rom"]   = df["prev_rom"].fillna(df["rom_percent"])
df["prev_pain"]  = df["prev_pain"].fillna(df["pain_score"])
df["prev_steps"] = df["prev_steps"].fillna(df["walking_steps"])

df["survey_completed"] = df["survey_completed"].astype(int)
df["rom_change"]   = df["rom_percent"]   - df["prev_rom"]
df["pain_change"]  = df["pain_score"]    - df["prev_pain"]
df["steps_change"] = df["walking_steps"] - df["prev_steps"]
df = df.fillna(0)

# ===============================
# STEP 2: ENCODE
# ===============================
df = pd.get_dummies(df, columns=["procedure_type", "gender"], drop_first=False)

# ===============================
# STEP 3: SEPARATE TARGETS
# ===============================
targets = df[["next_week_rom", "next_week_pain", "next_week_steps"]].copy()
X = df.drop(columns=["next_week_rom", "next_week_pain", "next_week_steps"])

# ===============================
# STEP 4: APPLY WEIGHTS (train time only)
# ===============================
feature_weights = {
    "rom_percent": 2.0, "pain_score": 2.0,
    "walking_steps": 1.0, "exercise_adherence": 1.0,
    "age": 1.0, "rom_change": 2.0,
    "pain_change": 2.0, "steps_change": 1.5
}

X_weighted = X.copy()
for col in X_weighted.columns:
    if col in feature_weights:
        X_weighted[col] *= feature_weights[col]

# ===============================
# STEP 5: SCALE
# ===============================
scaler   = StandardScaler()
X_scaled = scaler.fit_transform(X_weighted)

# ===============================
# STEP 6: TRAIN KNN
# ===============================
knn_model = NearestNeighbors(n_neighbors=10, metric="euclidean")
knn_model.fit(X_scaled)

# ===============================
# STEP 7: SAVE TO models/
# Save only targets — not full df
# ===============================
knn_data = targets.reset_index(drop=True)

joblib.dump(knn_model,                    model_path("knn_model.pkl"))
joblib.dump(X_weighted.columns.tolist(),  model_path("knn_features.pkl"))
joblib.dump(knn_data,                     model_path("knn_data.pkl"))
joblib.dump(scaler,                       model_path("knn_scaler.pkl"))
joblib.dump(feature_weights,              model_path("knn_weights.pkl"))

print("KNN model saved to models/")
print(f"   Training rows: {len(X_scaled)}")
print(f"   Features: {len(X_weighted.columns)}")
