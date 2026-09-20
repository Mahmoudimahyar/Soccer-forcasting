"""Phase 5: read-only audit of the alignment metrics/coverage CSVs (flags coverage + claim issues)."""
import csv, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def main():
    m = ROOT / "data/processed/soccernet_alignment_metrics.csv"
    if not m.exists():
        print("no metrics yet -> run run_soccernet_alignment.py"); return
    rows = list(csv.DictReader(open(m, encoding="utf-8")))
    cal = [r for r in rows if r.get("calibration") == "calibrated"]
    print(f"{len(cal)} event-type rows (calibrated). Flags:")
    for r in cal:
        ne = r.get("n_events"); rec = r.get("recall_L1"); pre = r.get("precision_L1")
        if ne and ne.isdigit() and int(ne) > 0:
            print(f"  {r['event_type']:16} n_events={ne:>5} recall_L1={rec or '-':>7} precision_L1={pre or '-':>7} mae_s={r.get('timing_mae_s') or '-'}")
if __name__ == "__main__":
    main()
