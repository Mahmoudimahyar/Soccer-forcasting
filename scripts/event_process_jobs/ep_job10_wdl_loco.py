"""EPJOB10 -- SECONDARY leave-one-international-competition-out (LOCO) W/D/L evaluation.

Holds out one international competition at a time, fits the e0-e9 goal-intensity family on the rest, and
scores on the held-out competition. Reports per-fold + per-model RPS/logloss/draw-Brier, the per-model
per-match RPS series (for the match-level bootstrap), draw-channel reliability (slope/intercept/ECE), and
the paired bootstrap of each candidate vs the e2 reference. LOCO complements the forward chain: a robust
candidate must hold up under BOTH protocols and not be driven by a single tournament.

Honest data_insufficient if the joined intl eval rows are absent. 2026 WC excluded by the loader.
research_only / experimental. No network/API.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ep_lib as L

try:
    from wcdrawlab.research.event_process import eval as E
except Exception as e:  # pragma: no cover
    L.emit("failed", reason=f"EP eval import failed: {e!r}")
    raise SystemExit(0)

REFERENCE = "research.event_process.e2"
CANDIDATES = [f"research.event_process.e{i}" for i in (3, 4, 5, 6, 7, 8, 9)]


def _pooled_from_folds(folds, metric):
    acc = {}
    for f in folds:
        for m, v in f["models"].items():
            if v.get(metric) is not None:
                acc.setdefault(m, []).append(v[metric])
    return {m: (sum(vs) / len(vs)) for m, vs in acc.items()}


def main():
    try:
        data = E.load_eval_rows()
    except E.DataInsufficient as d:
        L.emit("data_insufficient", reason=f"LOCO W/D/L not possible: {d}")
        return
    rows = data["snapshot_rows"]
    club = E.load_club_aux_rows()
    factory = E.make_wdl_factory(club_rows=club, include_club_transfer=bool(club))

    lc = E.loco_wdl(rows, predictor_factory=factory)
    if lc["n_folds"] < 2:
        L.emit("data_insufficient",
               reason=f"LOCO produced {lc['n_folds']} folds (need >=2 intl competitions)")
        return

    pooled_rps = _pooled_from_folds(lc["folds"], "rps")
    ref_rps = pooled_rps.get(REFERENCE)
    boots = {cand: E.paired_bootstrap_delta(lc["per_model_match_rps"], cand, REFERENCE)
             for cand in CANDIDATES}
    # fold-wins: in how many held-out comps does the candidate beat e2?
    fold_wins = {cand: 0 for cand in CANDIDATES}
    for f in lc["folds"]:
        ref = f["models"].get(REFERENCE, {}).get("rps")
        for cand in CANDIDATES:
            cv = f["models"].get(cand, {}).get("rps")
            if ref is not None and cv is not None and cv < ref:
                fold_wins[cand] += 1

    L.write_json("ep_wdl_loco.json", {
        "protocol": "loco", "reference": REFERENCE, "n_folds": lc["n_folds"],
        "pooled_rps": {m: round(v, 5) for m, v in pooled_rps.items()},
        "pooled_logloss": {m: round(v, 5) for m, v in _pooled_from_folds(lc["folds"], "logloss").items()},
        "reliability_draw_channel": lc["reliability"],
        "candidate_vs_e2_bootstrap": boots, "candidate_fold_wins_vs_e2": fold_wins,
        "n_rows": len(rows), "n_matches": data["n_matches"], "club_transfer_active": bool(club),
        "folds": lc["folds"], "utc": L.utc(),
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
    })
    favored = [c for c, b in boots.items() if b.get("favors_candidate")]
    L.emit("complete",
           reason=f"LOCO folds={lc['n_folds']} ref(e2)_rps={round(ref_rps,4) if ref_rps else None} "
                  f"candidates_bootstrap_favored={favored or 'none'} (CI upper<0)",
           state_updates={"wdl_loco_folds": lc["n_folds"], "wdl_loco_ref_rps": ref_rps,
                          "wdl_loco_favored_candidates": len(favored)})


main()
