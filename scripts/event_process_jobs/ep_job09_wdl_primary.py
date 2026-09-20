"""EPJOB9 -- PRIMARY forward-chaining W/D/L evaluation of the e0-e9 goal-intensity family.

Forward-chaining over INTERNATIONAL competitions ordered by kickoff: for competition c_k, fit on all
EARLIER competitions only, score on c_k. This is the primary out-of-sample protocol; e2 (parameter-free
remaining-time Poisson) is the REFERENCE every richer family must beat. We record pooled + per-fold RPS /
logloss / draw-Brier for every canonical model, and the paired match-level bootstrap of each candidate
vs e2 (lower RPS is better; negative delta favors the candidate).

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


def main():
    try:
        data = E.load_eval_rows()
    except E.DataInsufficient as d:
        L.emit("data_insufficient", reason=f"forward-chain W/D/L not possible: {d}")
        return
    rows = data["snapshot_rows"]
    club = E.load_club_aux_rows()
    factory = E.make_wdl_factory(club_rows=club, include_club_transfer=bool(club))

    fc = E.forward_chain_wdl(rows, predictor_factory=factory)
    if fc["n_folds"] < 1:
        L.emit("data_insufficient",
               reason=f"forward-chain produced {fc['n_folds']} folds (need >=1 ordered intl competition)")
        return

    # paired bootstrap (per-match RPS) needs LOCO's per-match series; compute a lightweight LOCO here too
    lc = E.loco_wdl(rows, predictor_factory=factory)
    boots = {}
    for cand in CANDIDATES:
        boots[cand] = E.paired_bootstrap_delta(lc["per_model_match_rps"], cand, REFERENCE)

    pooled = fc["pooled"]
    ref_rps = pooled.get(REFERENCE, {}).get("rps")
    beats_ref = {cand: (pooled.get(cand, {}).get("rps") is not None and ref_rps is not None
                        and pooled[cand]["rps"] < ref_rps) for cand in CANDIDATES}
    any_beats = any(beats_ref.values())

    L.write_json("ep_wdl_forward_chain.json", {
        "protocol": "forward_chain", "reference": REFERENCE,
        "competition_order": fc["competition_order"], "n_folds": fc["n_folds"],
        "pooled_rps": {m: (round(v["rps"], 5) if v.get("rps") is not None else None)
                       for m, v in pooled.items()},
        "pooled_logloss": {m: (round(v["logloss"], 5) if v.get("logloss") is not None else None)
                           for m, v in pooled.items()},
        "beats_reference_pooled": beats_ref,
        "candidate_vs_e2_bootstrap": boots,
        "n_rows": len(rows), "n_matches": data["n_matches"], "club_transfer_active": bool(club),
        "folds": fc["folds"], "utc": L.utc(),
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
    })
    best = min(((m, v["rps"]) for m, v in pooled.items() if v.get("rps") is not None),
               key=lambda kv: kv[1], default=(None, None))
    L.emit("complete",
           reason=f"forward-chain folds={fc['n_folds']} ref(e2)_rps={round(ref_rps,4) if ref_rps else None} "
                  f"best={best[0]}({round(best[1],4) if best[1] else None}) any_candidate_beats_e2={any_beats}",
           state_updates={"wdl_forward_folds": fc["n_folds"], "wdl_ref_rps": ref_rps,
                          "wdl_any_candidate_beats_ref": any_beats})


main()
