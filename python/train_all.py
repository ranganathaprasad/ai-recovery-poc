# ==========================================
# train_all.py
# Run this once to train all models
# Usage: python train_all.py
# ==========================================

import subprocess
import sys
import json
import os

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

scripts = [
    ("ROM Model",   "train_rom_model.py"),
    ("Pain Model",  "train_pain_model.py"),
    ("Steps Model", "train_steps_model.py"),
    ("KNN Model",   "train_knn_model.py"),
]

print("=" * 50)
print("TRAINING ALL MODELS")
print("=" * 50)

for name, script in scripts:
    print(f"\n>> Running {name}...")
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        encoding="utf-8",       # force UTF-8 when reading subprocess output
        errors="replace"        # don't crash on any stray characters
    )
    if result.returncode != 0:
        print(f"FAILED: {name}")
        print(result.stderr)
        sys.exit(1)
    print(result.stdout)

# ==========================================
# PRINT COMBINED EVAL SUMMARY
# ==========================================
print("\n" + "=" * 50)
print("EVALUATION SUMMARY")
print("=" * 50)

eval_files = ["rom_eval.json", "pain_eval.json", "steps_eval.json"]
for f in eval_files:
    if os.path.exists(f):
        with open(f) as fp:
            ev = json.load(fp)
        print(f"\n{ev['target'].upper()}")
        print(f"  Test MAE  : {ev['test_mae']}   (held-out, honest)")
        print(f"  CV MAE    : {ev['cv_mae']} +/- {ev['cv_std']}")
        print(f"  Per procedure:")
        for proc, mae in ev.get("mae_by_procedure", {}).items():
            print(f"    {proc}: {mae}")

print("\nAll models trained and saved")
print("Next: python predict.py  (or called by Node API)")
