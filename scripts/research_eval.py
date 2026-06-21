"""Research-only convenience evaluator: prints per-fold + mean composite for a given config.
Usage: python scripts/research_eval.py [config_path]  (default dev selection config)
Does not modify the frozen evaluator; just calls run_experiment and prints a compact table.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.research.runner import run_experiment  # noqa: E402

cfg = sys.argv[1] if len(sys.argv) > 1 else "configs/research_dev.yaml"
res = run_experiment("data/processed/research_modeling_table.csv", cfg, "outputs/research/_scratch")
print(f"# config={cfg}")
for f in res.folds:
    if not f.get("skipped"):
        print(f"  {f['fold']:<34} rps={f['rps']:.4f} ll={f['log_loss']:.4f} "
              f"dBrier={f['draw_brier']:.4f} dECE={f['draw_calibration_error']:.4f} J={f['composite']:.4f}")
    else:
        print(f"  {f['fold']:<34} SKIPPED ({f.get('reason')})")
s = res.summary
print(f"  >>> MEAN  rps={s['rps']:.4f} ll={s['log_loss']:.4f} dBrier={s['draw_brier']:.4f} "
      f"dECE={s['draw_calibration_error']:.4f}  COMPOSITE={s['composite']:.4f}")
