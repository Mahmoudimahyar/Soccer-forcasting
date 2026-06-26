"""Evaluate the player-impact W/D/L families (W2 reference + P1..P4) leave-one-competition-out over
international competitions, with match-level bootstrap CIs. research_only / experimental.

Models are fit INSIDE each training fold only (regularization chosen on train). Player-impact feature
columns are read per row if present and degrade gracefully (unknown indicator) when absent, so this script
runs on the existing corpus even before the player_history feature attachment has populated those columns.

Usage:
    python scripts/evaluate_player_impact_wdl.py --run-dir <dir> [--snapshots <snapshots_intl.json>]

If --snapshots is omitted the corpus is loaded and international regulation snapshots are built via
scripts/research_jobs/_common.regulation_snapshots (the inherited leakage-safe builder).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research_jobs"))

import _common as C  # noqa: E402
from wcdrawlab.research import player_impact_models as PIM  # noqa: E402


def load_rows(snapshots: Path | None) -> list:
    if snapshots and Path(snapshots).exists():
        return json.loads(Path(snapshots).read_text(encoding="utf-8"))
    fixtures, events, lineups = C.load_corpus()
    return C.regulation_snapshots(fixtures, events, lineups, international_only=True)


def evaluate(rows: list) -> dict:
    names = ["W2", "P1", "P2", "P3", "P4"]
    agg = {m: {"rps": [], "ll": [], "bd": [], "cal_draw": [], "by_match": defaultdict(list)} for m in names}
    n_folds = 0
    for held, train, test in C.loco_folds(rows):
        n_folds += 1
        preds = PIM.wdl_predictors(train)  # fit on TRAIN competitions only
        for name in names:
            fn = preds[name]
            for r in test:
                p = fn(r)
                t = r["target_wdl"]
                rp = C.rps(p, t)
                ll = C.logloss3(p, t)
                bd = C.brier_draw(p, t)
                agg[name]["rps"].append(rp)
                agg[name]["ll"].append(ll)
                agg[name]["bd"].append(bd)
                agg[name]["cal_draw"].append((p.get("D", 0.0), 1.0 if t == "D" else 0.0))
                agg[name]["by_match"][r["match_id"]].append(rp)
    out = {}
    for name in names:
        d = agg[name]
        n = len(d["rps"])
        if n == 0:
            out[name] = {"n_rows": 0}
            continue
        per_match = [sum(v) / len(v) for v in d["by_match"].values()]
        out[name] = {
            "n_rows": n,
            "n_matches": len(per_match),
            "rps": round(sum(d["rps"]) / n, 4),
            "logloss": round(sum(d["ll"]) / n, 4),
            "brier_draw": round(sum(d["bd"]) / n, 4),
            "draw_calibration": C.calibration(d["cal_draw"]),
            "rps_match_ci95": C.match_bootstrap_ci(per_match),
        }
    scored = [k for k in names if out[k].get("n_rows")]
    leader = min(scored, key=lambda k: out[k]["rps"]) if scored else None
    return {"family": "player_impact_wdl", "model_version": PIM.MODEL_VERSION,
            "n_folds": n_folds, "models": out, "leader_by_rps": leader,
            "reference_model": "W2", "research_only": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--snapshots", default=None)
    args = ap.parse_args()
    rd = Path(args.run_dir)
    rd.mkdir(parents=True, exist_ok=True)
    rows = load_rows(Path(args.snapshots) if args.snapshots else None)
    comps = sorted({r["competition"] for r in rows})
    if len(comps) < 2:
        res = {"status": "skipped", "reason": f"need >=2 international competitions for LOCO (have {comps})",
               "family": "player_impact_wdl", "research_only": True}
    else:
        res = evaluate(rows)
        res["status"] = "complete"
        res["competitions"] = comps
    (rd / "player_impact_wdl.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({"status": res.get("status"), "leader_by_rps": res.get("leader_by_rps"),
                      "out": str(rd / "player_impact_wdl.json")}))


if __name__ == "__main__":
    main()
