"""Phase 4: apply the FROZEN preregistered gate to the R4 per-class aggregate metrics and emit the gate
decision JSON. Reproducible from the (gitignored) metrics CSV. No raw text.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import silver_label_policy as SP  # noqa: E402

METRICS = ROOT / "data/processed/commentary_precision_event_class_metrics.csv"


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    rows = [r for r in csv.DictReader(open(METRICS, encoding="utf-8")) if r["model"] == "R4"]
    classes = {}
    for r in rows:
        n = int(r["n_pred"]); k = int(r["k_correct"])
        med = _f(r["timing_median_s"]); p90 = _f(r["timing_p90_s"])
        stable = int(r["stable_folds"]); comps = int(r["competitions"])
        label, reasons = SP.gate_class(n, k, med, p90, stable, comps)
        classes[r["event_class"]] = {
            "label": label, "n_pred": n, "k_correct": k,
            "precision": round(k / n, 4) if n else None,
            "wilson_lb": round(SP.wilson_lower_bound(k, n), 4),
            "timing_median_s": med, "timing_p90_s": p90,
            "stable_folds": stable, "competitions": comps, "reasons": reasons,
        }
    approved = [c for c, v in classes.items() if v["label"] == "silver_label_approved_for_historical_research"]
    out = {"thresholds": {"min_pred": SP.T1_MIN_PREDICTIONS, "wilson_lb": SP.T2_WILSON_LB,
                          "median_s": SP.T3_MEDIAN_TIMING_S, "p90_s": SP.T4_P90_TIMING_S,
                          "min_stable_folds": SP.T5_MIN_STABLE_FOLDS},
           "classes": classes, "approved_classes": approved,
           "n_approved": len(approved), "all_outputs": "historical_weak_supervision_only / not_live_eligible"}
    (ROOT / "notes/research/commentary_silver_label_gate.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"approved classes: {approved}")
    for c, v in sorted(classes.items()):
        print(f"  {c:16} {v['label']:42} wlb={v['wilson_lb']} n={v['n_pred']} medT={v['timing_median_s']} folds={v['stable_folds']}")


if __name__ == "__main__":
    main()
