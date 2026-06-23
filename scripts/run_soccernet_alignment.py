"""Phase 5: leakage-safe REAL commentary-to-event alignment evaluation on the SoccerNet-Echoes <-> labels
overlap. Match-level splits only (no commentary row from a test match ever appears in training/calibration).
Latency offset estimated on TRAIN matches only. Writes tracked aggregate metrics (no raw text).
research_only / historical_weak_supervision_only / not_live_eligible.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import soccernet_features as F  # noqa: E402
from wcdrawlab.research.commentary import soccernet_alignment as A  # noqa: E402

ARROW = ROOT / "data/raw/commentary/soccernet_echoes/whisper_v1/1.0.0/soccer_net_echoes_hf_dataset-train.arrow"
LABELS = ROOT / "data/raw/soccernet_action_labels"
WINDOW = 45.0  # preregistered candidate window (s); chosen before evaluation


def competition(mid):
    return mid.split("/")[0]


def main():
    events = F.load_label_events(LABELS)
    # echoes corpus match ids (match-level) intersect with label matches
    import pyarrow as pa
    try:
        tbl = pa.ipc.open_file(pa.memory_map(str(ARROW), "r")).read_all()
    except Exception:
        with pa.OSFile(str(ARROW), "rb") as f:
            tbl = pa.ipc.open_stream(f).read_all()
    echoes_mids = {F.echoes_match_id(g) for g in tbl.column("game").to_pylist()}
    overlap = sorted(echoes_mids & set(events.keys()))
    print(f"label matches={len(events)} echoes matches={len(echoes_mids)} OVERLAP={len(overlap)}")
    if not overlap:
        print("NO OVERLAP -> feasibility blocked at data level");
        Path(ROOT / "data/processed/soccernet_alignment_metrics.csv").write_text("no_overlap\n", encoding="utf-8")
        return
    segs = F.load_echoes_segments(ARROW, overlap)
    matched = sorted([m for m in overlap if segs.get(m) and events.get(m)])
    comps = sorted({competition(m) for m in matched})
    print(f"matched (events+commentary) games={len(matched)} competitions={comps}")

    # split: leave-one-competition-out if >=2 comps, else grouped 70/30 by match (deterministic)
    if len(comps) >= 2:
        split_method = "leave_one_competition_out"
        test_comp = comps[-1]
        test_ids = [m for m in matched if competition(m) == test_comp]
        train_ids = [m for m in matched if competition(m) != test_comp]
    else:
        split_method = "grouped_match_70_30"
        k = max(1, int(len(matched) * 0.3))
        test_ids, train_ids = matched[-k:], matched[:-k]
    feasibility_only = len(matched) < 20

    offset = A.estimate_train_offset(events, segs, train_ids, window_s=WINDOW)
    rows_uncal = A.evaluate(events, segs, test_ids, window_s=WINDOW, offset_s=0.0)
    rows_cal = A.evaluate(events, segs, test_ids, window_s=WINDOW, offset_s=offset)

    # write metrics csv (per type, both calibrated/uncalibrated)
    mpath = ROOT / "data/processed/soccernet_alignment_metrics.csv"
    with open(mpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["calibration", "event_type", "n_events", "n_claims", "recall_L0", "recall_L1",
                    "precision_L1", "f1_L1", "n_pairs", "timing_median_abs_s", "timing_mae_s", "dt_signed_median_s"])
        for tag, rows in (("uncalibrated", rows_uncal), ("calibrated", rows_cal)):
            for t, r in rows.items():
                w.writerow([tag, t, r["n_events"], r["n_claims"],
                            _f(r["recall_L0"]), _f(r["recall_L1"]), _f(r["precision_L1"]), _f(r["f1_L1"]),
                            r["n_pairs"], _f(r["timing_median_abs"]), _f(r["timing_mae"]), _f(r["dt_signed_median"])])
    # coverage csv (per matched game)
    cpath = ROOT / "data/processed/soccernet_alignment_coverage.csv"
    with open(cpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["match_id", "competition", "split", "n_events", "n_segments"])
        for m in matched:
            split = "test" if m in test_ids else "train"
            w.writerow([m, competition(m), split, len(events.get(m, [])), len(segs.get(m, []))])

    summary = {"overlap_matches": len(overlap), "matched_games": len(matched), "competitions": comps,
               "split_method": split_method, "n_train": len(train_ids), "n_test": len(test_ids),
               "train_latency_offset_s": round(offset, 2), "window_s": WINDOW,
               "feasibility_only": feasibility_only,
               "goal_recall_L1_uncal": _f(rows_uncal.get("goal", {}).get("recall_L1")),
               "goal_recall_L1_cal": _f(rows_cal.get("goal", {}).get("recall_L1")),
               "goal_precision_L1_cal": _f(rows_cal.get("goal", {}).get("precision_L1"))}
    Path(ROOT / "data/processed/soccernet_alignment_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("summary:", json.dumps(summary))


def _f(x):
    return round(x, 4) if isinstance(x, float) else ("" if x is None else x)


if __name__ == "__main__":
    main()
