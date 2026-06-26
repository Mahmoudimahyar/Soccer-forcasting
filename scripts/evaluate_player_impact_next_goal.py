"""Evaluate the player-impact NEXT-GOAL families (N0 base-rate, N1 hazard, N2 +on-pitch impact,
N3 +sub delta) leave-one-competition-out over international competitions, match-level bootstrap CIs.
research_only / experimental.

Models are fit INSIDE each training fold only (regularization chosen on train). Player-impact feature
columns degrade gracefully (unknown indicator) when absent.

Usage:
    python scripts/evaluate_player_impact_next_goal.py --run-dir <dir> [--snapshots <snapshots_intl.json>]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research_jobs"))

import _common as C  # noqa: E402
from wcdrawlab.research import player_impact_models as PIM  # noqa: E402

TARGET = "next_goal_15"


def load_rows(snapshots: Path | None) -> list:
    if snapshots and Path(snapshots).exists():
        return json.loads(Path(snapshots).read_text(encoding="utf-8"))
    fixtures, events, lineups = C.load_corpus()
    return C.regulation_snapshots(fixtures, events, lineups, international_only=True)


def evaluate(rows: list) -> dict:
    names = ["N0", "N1", "N2", "N3"]
    agg = {m: {"brier": [], "ll": [], "cal": [], "by_match": defaultdict(list)} for m in names}
    base_rate = sum(int(r[TARGET]) for r in rows) / max(1, len(rows))
    n_folds = 0
    for held, train, test in C.loco_folds(rows):
        n_folds += 1
        preds = PIM.nextgoal_predictors(train, target_key=TARGET)  # fit on TRAIN only
        for name in names:
            fn = preds[name]
            for r in test:
                p = min(max(float(fn(r)), 1e-9), 1 - 1e-9)
                y = int(r[TARGET])
                br = (p - y) ** 2
                ll = -(y * math.log(p) + (1 - y) * math.log(1 - p))
                agg[name]["brier"].append(br)
                agg[name]["ll"].append(ll)
                agg[name]["cal"].append((p, y))
                agg[name]["by_match"][r["match_id"]].append(br)
    out = {}
    for name in names:
        d = agg[name]
        n = len(d["brier"])
        if n == 0:
            out[name] = {"n_rows": 0}
            continue
        per_match = [sum(v) / len(v) for v in d["by_match"].values()]
        out[name] = {
            "n_rows": n,
            "n_matches": len(per_match),
            "brier": round(sum(d["brier"]) / n, 4),
            "logloss": round(sum(d["ll"]) / n, 4),
            "calibration": C.calibration(d["cal"]),
            "brier_match_ci95": C.match_bootstrap_ci(per_match),
        }
    scored = [k for k in names if out[k].get("n_rows")]
    leader = min(scored, key=lambda k: out[k]["brier"]) if scored else None
    return {"family": "player_impact_next_goal", "model_version": PIM.MODEL_VERSION,
            "base_rate": round(base_rate, 4), "n_folds": n_folds, "models": out,
            "leader_by_brier": leader, "research_only": True}


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
               "family": "player_impact_next_goal", "research_only": True}
    else:
        res = evaluate(rows)
        res["status"] = "complete"
        res["competitions"] = comps
    (rd / "player_impact_next_goal.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({"status": res.get("status"), "leader_by_brier": res.get("leader_by_brier"),
                      "out": str(rd / "player_impact_next_goal.json")}))


if __name__ == "__main__":
    main()
