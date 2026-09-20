"""EPJOB12 -- NEAR-TERM SCORING family h0-h3 (binary: ANY goal in the next 10' of the snapshot). LOCO
over international competitions; h0 (TRAIN base rate) is the reference. We additionally report the 5'/15'
horizons as sensitivity, since the snapshot-target table carries all three. Reports pooled + per-fold
log-loss / Brier, calibration, and the per-match-Brier paired bootstrap of each candidate vs h0.

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

PRIMARY_TARGET = "any_goal_next10m"   # spec: near-term scoring == any goal in next 10'
SENSITIVITY = ["any_goal_next5m", "any_goal_next15m"]
REFERENCE = "research.scoring.h0"
CANDIDATES = [f"research.scoring.h{i}" for i in (1, 2, 3)]


def _run(rows, target):
    return E.loco_binary(rows, M.scoring_predictors, target)


def main():
    try:
        data = E.load_eval_rows()
    except E.DataInsufficient as d:
        L.emit("data_insufficient", reason=f"near-term scoring LOCO not possible: {d}")
        return
    rows = data["snapshot_rows"]
    base_rate = sum(int(r[PRIMARY_TARGET]) for r in rows) / max(1, len(rows))

    res = _run(rows, PRIMARY_TARGET)
    if res["n_folds"] < 2:
        L.emit("data_insufficient", reason=f"scoring LOCO produced {res['n_folds']} folds (need >=2)")
        return
    pmb = res["per_model_match_brier"]
    boots = {c: E.paired_bootstrap_delta(pmb, c, REFERENCE) for c in CANDIDATES}

    sensitivity = {}
    for t in SENSITIVITY:
        r = _run(rows, t)
        sensitivity[t] = {"base_rate": round(sum(int(x[t]) for x in rows) / len(rows), 5),
                          "pooled": {m: {k: (round(v, 5) if v is not None else None) for k, v in d.items()}
                                     for m, d in r["pooled"].items()}}

    L.write_json("ep_near_term_scoring_loco.json", {
        "primary_target": PRIMARY_TARGET, "base_rate": round(base_rate, 5),
        "reference": REFERENCE, "n_folds": res["n_folds"],
        "pooled": {m: {k: (round(v, 5) if v is not None else None) for k, v in d.items()}
                   for m, d in res["pooled"].items()},
        "candidate_vs_h0_bootstrap": boots, "sensitivity_horizons": sensitivity,
        "folds": res["folds"], "n_rows": len(rows), "n_matches": data["n_matches"], "utc": L.utc(),
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
    })
    favored = [c for c, b in boots.items() if b.get("favors_candidate")]
    ref_brier = res["pooled"].get(REFERENCE, {}).get("brier")
    L.emit("complete",
           reason=f"near-term scoring (10') LOCO folds={res['n_folds']} base_rate={round(base_rate,3)} "
                  f"h0_brier={round(ref_brier,4) if ref_brier else None} favored={favored or 'none'}",
           state_updates={"scoring_folds": res["n_folds"], "scoring_base_rate": base_rate,
                          "scoring_favored": len(favored)})


main()
