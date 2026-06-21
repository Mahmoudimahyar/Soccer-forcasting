"""Run live-shadow integrity checks against the actual predictions file (read-only).
Usage: python scripts/validate_shadow_integrity.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import shadow_integrity as si  # noqa: E402

PRED = ROOT / "outputs/research/live_2026_shadow_predictions.csv"
if not PRED.exists():
    print("no predictions file yet"); sys.exit(0)
df = pd.read_csv(PRED)
out = si.run_all(df)
print(f"rows={len(df)} matches={df.match_id.nunique()} models={sorted(df.model_version.unique())}")
print(json.dumps(out, indent=2))
sys.exit(0 if out["all_ok"] else 1)
