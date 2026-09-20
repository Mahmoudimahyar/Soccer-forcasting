"""EPJOB11 -- NEXT-GOAL hazard family q0-q4 (binary: a regulation goal by EITHER side within the next
15' of the snapshot). LOCO over international competitions; q0 (TRAIN base rate) is the reference. Reports
pooled + per-fold log-loss / Brier, calibration, and the per-match-Brier paired bootstrap of each
candidate vs q0.

Honest data_insufficient if the joined intl eval rows are absent. 2026 WC excluded by the loader.
research_only / experimental. No network/API.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ep_lib as L

try:
    from wcdrawlab.research.event_process import eval as E, models as M
except Exception as e:  # pragma: no cover
    L.emit("failed", reason=f"EP eval/models import failed: {e!r}")
    raise SystemExit(0)

TARGET = "next_goal_any_15"
REFERENCE = "research.next_goal.q0"
CANDIDATES = [f"research.next_goal.q{i}" for i in (1, 2, 3, 4)]


def main():
    try:
        data = E.load_eval_rows()
    except E.DataInsufficient as d:
        L.emit("data_insufficient", reason=f"next-goal LOCO not possible: {d}")
        return
    rows = data["snapshot_rows"]
    base_rate = sum(int(r[TARGET]) for r in rows) / max(1, len(rows))

    res = E.loco_binary(rows, M.next_goal_predictors, TARGET)
    if res["n_folds"] < 2:
        L.emit("data_insufficient", reason=f"next-goal LOCO produced {res['n_folds']} folds (need >=2)")
        return
    pmb = res["per_model_match_brier"]
    boots = {c: E.paired_bootstrap_delta(pmb, c, REFERENCE) for c in CANDIDATES}

    L.write_json("ep_next_goal_loco.json", {
        "target": TARGET, "horizon_min": E.NEXT_GOAL_HORIZON, "base_rate": round(base_rate, 5),
        "reference": REFERENCE, "n_folds": res["n_folds"],
        "pooled": {m: {k: (round(v, 5) if v is not None else None) for k, v in d.items()}
                   for m, d in res["pooled"].items()},
        "candidate_vs_q0_bootstrap": boots, "folds": res["folds"],
        "n_rows": len(rows), "n_matches": data["n_matches"], "utc": L.utc(),
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
    })
    favored = [c for c, b in boots.items() if b.get("favors_candidate")]
    ref_brier = res["pooled"].get(REFERENCE, {}).get("brier")
    L.emit("complete",
           reason=f"next-goal LOCO folds={res['n_folds']} base_rate={round(base_rate,3)} "
                  f"q0_brier={round(ref_brier,4) if ref_brier else None} favored={favored or 'none'}",
           state_updates={"next_goal_folds": res["n_folds"], "next_goal_base_rate": base_rate,
                          "next_goal_favored": len(favored)})


main()
