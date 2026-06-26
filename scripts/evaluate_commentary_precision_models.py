"""Phase 3: leakage-safe leave-one-competition-out evaluation of the R1/R2/R4 precision ladder.
All fitting + threshold selection on TRAIN competitions only. Emits per-fold + per-class metrics
(precision, Wilson LB, timing median/p90, coverage). NO raw text in tracked outputs.
"""
import bisect
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import soccernet_features as F  # noqa: E402
from wcdrawlab.research.commentary import precision_models as PM  # noqa: E402
from wcdrawlab.research.commentary import silver_label_policy as SP  # noqa: E402

LABELS = ROOT / "data/raw/soccernet_action_labels"
ARROW = ROOT / "data/raw/commentary/soccernet_echoes/whisper_v1_en/1.0.0/soccer_net_echoes_hf_dataset-train.arrow"
WINDOW = 45.0
CLASSES = ["goal", "corner", "yellow_card", "foul", "offside", "substitution", "kickoff",
           "shot", "shot_on_target", "penalty_awarded", "red_card", "second_yellow"]


def nearest_dt(ev_times_half, t):
    """min |t - event| over a sorted list; None if empty."""
    if not ev_times_half:
        return None
    i = bisect.bisect_left(ev_times_half, t)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(ev_times_half):
            d = abs(ev_times_half[j] - t)
            best = d if best is None else min(best, d)
    return best


def assemble():
    events = F.load_label_events(LABELS)
    ech = {F.echoes_match_id(g) for g in _games()}
    overlap = sorted(ech & set(events))
    segs = F.load_echoes_segments(ARROW, overlap)
    matched = sorted(m for m in overlap if segs.get(m) and events.get(m))
    # event times per (match, half, class), sorted
    ev_idx = {}
    for m in matched:
        d = defaultdict(list)
        for e in events[m]:
            if e["canonical"] in CLASSES:
                d[(e["half"], e["canonical"])].append(e["t_s"])
        for k in d:
            d[k].sort()
        ev_idx[m] = d
    # dedup segments per match by content_hash
    seg_idx = {}
    for m in matched:
        seen = set()
        rows = []
        for s in segs[m]:
            if s["content_hash"] in seen:
                continue
            seen.add(s["content_hash"])
            rows.append(s)
        seg_idx[m] = rows
    return matched, ev_idx, seg_idx


def _games():
    import pyarrow as pa
    try:
        tbl = pa.ipc.open_file(pa.memory_map(str(ARROW), "r")).read_all()
    except Exception:
        with pa.OSFile(str(ARROW), "rb") as f:
            tbl = pa.ipc.open_stream(f).read_all()
    return tbl.column("game").to_pylist()


def label_for(ev_idx, m, half, t, cls):
    dts = ev_idx[m].get((half, cls), [])
    dt = nearest_dt(dts, t)
    return (1 if (dt is not None and dt <= WINDOW) else 0), dt


def main():
    matched, ev_idx, seg_idx = assemble()
    comps = sorted({m.split("/")[0] for m in matched})
    print(f"matched={len(matched)} comps={comps}", flush=True)

    fold_rows = []          # per (fold, class, model)
    agg = defaultdict(lambda: {"n": 0, "k": 0, "timings": [], "folds": set(), "comps": set()})  # (model,cls)

    for held in comps:
        train_m = [m for m in matched if m.split("/")[0] != held]
        test_m = [m for m in matched if m.split("/")[0] == held]
        # training matrix
        tr_text, tr_norm = [], []
        tr_y = {c: [] for c in CLASSES}
        tr_meta = []
        for m in train_m:
            for s in seg_idx[m]:
                tr_text.append(s["text"]); tr_norm.append(s["norm"])
                for c in CLASSES:
                    y, _ = label_for(ev_idx, m, s["half"], s["t_s"], c)
                    tr_y[c].append(y)
        pm = PM.PrecisionModels().fit(tr_text, tr_y)
        Xtr = pm.vec.transform(tr_text)
        # select R4 thresholds on TRAIN (R3 confidence)
        thr = {}
        for c in CLASSES:
            mdl = pm.models.get(c)
            probs = list(mdl.predict_proba(Xtr)[:, 1]) if mdl is not None else [0.0] * len(tr_text)
            conf = [(pm.alpha * p + (1 - pm.alpha) * PM.r1_rule_score(nt, c)) if PM.r1_rule_score(nt, c) > 0 else 0.0
                    for p, nt in zip(probs, tr_norm)]
            t_, _, _ = SP.select_threshold(conf, tr_y[c])
            thr[c] = t_
        # test
        te_text, te_norm, te_meta = [], [], []
        for m in test_m:
            for s in seg_idx[m]:
                te_text.append(s["text"]); te_norm.append(s["norm"]); te_meta.append((m, s["half"], s["t_s"]))
        Xte = pm.vec.transform(te_text) if te_text else None
        for c in CLASSES:
            mdl = pm.models.get(c)
            probs = list(mdl.predict_proba(Xte)[:, 1]) if (mdl is not None and Xte is not None) else [0.0] * len(te_text)
            # ground-truth + timing per test segment for class c
            for model_name in ("R1", "R2", "R4"):
                n = k = 0; timings = []
                for idx, (p, nt) in enumerate(zip(probs, te_norm)):
                    rule = PM.r1_rule_score(nt, c)
                    conf = (pm.alpha * p + (1 - pm.alpha) * rule) if rule > 0 else 0.0
                    if model_name == "R1":
                        emit = rule > 0
                    elif model_name == "R2":
                        emit = p >= 0.5
                    else:
                        emit = conf >= thr[c] and rule > 0
                    if not emit:
                        continue
                    m_, half_, t_ = te_meta[idx]
                    y, dt = label_for(ev_idx, m_, half_, t_, c)
                    n += 1; k += y
                    if y and dt is not None:
                        timings.append(dt)
                prec = k / n if n else None
                med = statistics.median(timings) if timings else None
                p90 = (sorted(timings)[max(0, int(0.9 * len(timings)) - 1)] if timings else None)
                fold_rows.append([held, c, model_name, n, k, _r(prec),
                                  _r(SP.wilson_lower_bound(k, n)), _r(med), _r(p90)])
                a = agg[(model_name, c)]
                a["n"] += n; a["k"] += k; a["timings"] += timings; a["comps"].add(held)
                if n >= SP.T5_MIN_FOLD_PREDS and SP.wilson_lower_bound(k, n) >= SP.T2_WILSON_LB:
                    a["folds"].add(held)
        print(f"  fold {held} done", flush=True)

    # write per-fold csv
    fp = ROOT / "data/processed/commentary_precision_outer_fold_metrics.csv"
    fp.parent.mkdir(parents=True, exist_ok=True)
    with open(fp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["held_out", "event_class", "model", "n_pred", "k_correct",
                                       "precision", "wilson_lb", "timing_median_s", "timing_p90_s"]); w.writerows(fold_rows)
    # aggregate per (model,class)
    arows = []
    for (model_name, c), a in sorted(agg.items()):
        n, k = a["n"], a["k"]
        med = statistics.median(a["timings"]) if a["timings"] else None
        p90 = (sorted(a["timings"])[max(0, int(0.9 * len(a["timings"])) - 1)] if a["timings"] else None)
        arows.append([model_name, c, n, k, _r(k / n if n else None), _r(SP.wilson_lower_bound(k, n)),
                      _r(med), _r(p90), len(a["folds"]), len(a["comps"])])
    cp = ROOT / "data/processed/commentary_precision_event_class_metrics.csv"
    with open(cp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["model", "event_class", "n_pred", "k_correct", "precision",
                                       "wilson_lb", "timing_median_s", "timing_p90_s", "stable_folds", "competitions"]); w.writerows(arows)
    # quick R4 summary
    print("\nR4 per-class aggregate:")
    for r in arows:
        if r[0] == "R4":
            print(f"  {r[1]:16} n={r[2]:>5} prec={r[4]} wilsonLB={r[5]} medT={r[6]} p90T={r[7]} folds={r[8]} comps={r[9]}")


def _r(x):
    return round(x, 4) if isinstance(x, float) else x


if __name__ == "__main__":
    main()
