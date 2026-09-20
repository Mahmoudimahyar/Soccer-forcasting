"""Phase 5 (reproducibility): committed, deterministic reproduction of (a) the full 6-fold
leave-one-competition-out per-competition table and (b) the language-variant comparison
(whisper_v1 original vs whisper_v1_en English) that the evaluation report cites.

Run:  python scripts/run_soccernet_folds.py
Writes gitignored per-competition CSV + a TRACKED comparison summary (notes/). No raw text.
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

LABELS = ROOT / "data/raw/soccernet_action_labels"
WINDOW = 45.0


def arrow(variant):
    return ROOT / f"data/raw/commentary/soccernet_echoes/{variant}/1.0.0/soccer_net_echoes_hf_dataset-train.arrow"


def load(variant, events):
    import pyarrow as pa
    ap = arrow(variant)
    if not ap.exists():
        return None, None
    try:
        tbl = pa.ipc.open_file(pa.memory_map(str(ap), "r")).read_all()
    except Exception:
        with pa.OSFile(str(ap), "rb") as f:
            tbl = pa.ipc.open_stream(f).read_all()
    ech = {F.echoes_match_id(g) for g in tbl.column("game").to_pylist()}
    overlap = sorted(ech & set(events))
    segs = F.load_echoes_segments(ap, overlap)
    matched = sorted(m for m in overlap if segs.get(m) and events.get(m))
    return matched, segs


def main():
    events = F.load_label_events(LABELS)
    out = {"window_s": WINDOW, "language_comparison": {}, "note": "no raw text; LOCO match-level splits"}

    # (b) language comparison: same held-out competition (spain_laliga) under both variants
    for variant in ("whisper_v1", "whisper_v1_en"):
        matched, segs = load(variant, events)
        if not matched:
            out["language_comparison"][variant] = "variant_arrow_absent"
            continue
        comps = sorted({m.split("/")[0] for m in matched})
        held = "spain_laliga" if "spain_laliga" in comps else comps[-1]
        test = [m for m in matched if m.split("/")[0] == held]
        train = [m for m in matched if m.split("/")[0] != held]
        off = A.estimate_train_offset(events, segs, train, window_s=WINDOW)
        r = A.evaluate(events, segs, test, window_s=WINDOW, offset_s=off)
        out["language_comparison"][variant] = {
            "held_out": held, "n_matched": len(matched), "n_test": len(test),
            "goal_recall_L1": round(r["goal"]["recall_L1"], 4) if r["goal"]["recall_L1"] is not None else None,
            "goal_precision_L1": round(r["goal"]["precision_L1"], 4) if r["goal"]["precision_L1"] is not None else None,
        }

    # (a) per-competition 6-fold table on the English variant
    matched, segs = load("whisper_v1_en", events)
    rows = []
    if matched:
        comps = sorted({m.split("/")[0] for m in matched})
        for held in comps:
            test = [m for m in matched if m.split("/")[0] == held]
            train = [m for m in matched if m.split("/")[0] != held]
            off = A.estimate_train_offset(events, segs, train, window_s=WINDOW)
            r = A.evaluate(events, segs, test, window_s=WINDOW, offset_s=off)
            for t in ("goal", "corner", "yellow_card"):
                d = r[t]
                rows.append([held, len(test), t, d["n_events"],
                             _r(d["recall_L1"]), _r(d["precision_L1"]),
                             round(d["timing_mae"], 1) if d["timing_mae"] else None])
        cpath = ROOT / "data/processed/soccernet_alignment_per_competition.csv"
        cpath.parent.mkdir(parents=True, exist_ok=True)
        with open(cpath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["held_out_competition", "n_test_games", "event", "n_events",
                        "recall_L1", "precision_L1", "timing_mae_s"])
            w.writerows(rows)
    out["per_competition_rows"] = len(rows)
    (ROOT / "notes/research/soccernet_language_and_fold_comparison.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


def _r(x):
    return round(x, 4) if isinstance(x, float) else x


if __name__ == "__main__":
    main()
