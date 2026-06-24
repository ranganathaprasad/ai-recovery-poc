import sys
import os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ==========================================
# train_steps_model.py
# ==========================================

import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split, cross_val_score
import joblib
import json

# ===============================
# PATHS
# ===============================
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

def model_path(filename):
    return os.path.join(MODEL_DIR, filename)

TARGET = "next_week_steps"

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
# STEP 3: FEATURES + TARGET
# ===============================
drop_cols = ["next_week_rom", "next_week_pain", "next_week_steps"]
X = df.drop(columns=drop_cols)
y = df[TARGET]

feature_columns = X.columns.tolist()

# ===============================
# STEP 4: TRAIN / TEST SPLIT
# ===============================
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# ===============================
# STEP 5: MAIN MODEL
# ===============================
model = XGBRegressor(
    n_estimators=250, learning_rate=0.05, max_depth=6,
    subsample=0.8, colsample_bytree=0.8, random_state=42, eval_metric="mae"
)
model.fit(X_train, y_train)

# ===============================
# STEP 6: QUANTILE MODELS
# ===============================
model_low = XGBRegressor(
    n_estimators=250, learning_rate=0.05, max_depth=6, subsample=0.8,
    objective="reg:quantileerror", quantile_alpha=0.1, random_state=42
)
model_low.fit(X_train, y_train)

model_high = XGBRegressor(
    n_estimators=250, learning_rate=0.05, max_depth=6, subsample=0.8,
    objective="reg:quantileerror", quantile_alpha=0.9, random_state=42
)
model_high.fit(X_train, y_train)

# ===============================
# STEP 7: EVALUATION
# ===============================
train_mae = mean_absolute_error(y_train, model.predict(X_train))
test_mae  = mean_absolute_error(y_test,  model.predict(X_test))

cv_scores = cross_val_score(
    XGBRegressor(n_estimators=250, learning_rate=0.05, max_depth=6, random_state=42),
    X, y, cv=5, scoring="neg_mean_absolute_error"
)
cv_mae = -cv_scores.mean()
cv_std =  cv_scores.std()

procedure_cols = [c for c in X_test.columns if c.startswith("procedure_type_")]
eval_by_procedure = {}
X_test_r = X_test.reset_index(drop=True)
y_test_r = y_test.reset_index(drop=True)

for col in procedure_cols:
    mask = X_test_r[col] == 1
    if mask.sum() > 0:
        proc_name = col.replace("procedure_type_", "")
        eval_by_procedure[proc_name] = round(float(mean_absolute_error(y_test_r[mask], model.predict(X_test_r[mask]))), 3)

eval_results = {
    "target": TARGET,
    "train_mae": round(float(train_mae), 3),
    "test_mae":  round(float(test_mae),  3),
    "cv_mae":    round(float(cv_mae),    3),
    "cv_std":    round(float(cv_std),    3),
    "train_size": int(len(X_train)),
    "test_size":  int(len(X_test)),
    "mae_by_procedure": eval_by_procedure
}

print(f"\n{'='*40}")
print(f"STEPS MODEL EVALUATION")
print(f"{'='*40}")
print(f"Train MAE : {train_mae:.3f}")
print(f"Test MAE  : {test_mae:.3f}  (honest - held out test set)")
print(f"CV MAE    : {cv_mae:.3f} +/- {cv_std:.3f}")
print(f"\nPer-procedure test MAE:")
for proc, mae in eval_by_procedure.items():
    print(f"  {proc}: {mae}")

# ===============================
# STEP 8: SAVE TO models/
# ===============================
joblib.dump(model,           model_path("steps_model.pkl"))
joblib.dump(feature_columns, model_path("steps_features.pkl"))
joblib.dump(float(test_mae), model_path("steps_mae.pkl"))
joblib.dump(model_low,       model_path("steps_q_low.pkl"))
joblib.dump(model_high,      model_path("steps_q_high.pkl"))

with open(model_path("steps_eval.json"), "w") as f:
    json.dump(eval_results, f, indent=2)

print(f"\nSteps model saved to models/")
