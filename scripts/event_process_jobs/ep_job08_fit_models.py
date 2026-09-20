"""EPJOB8 -- FIT the e0-e9 W/D/L goal-intensity family on the FULL international population (IN-SAMPLE
fit record ONLY; selection NEVER uses an in-sample fit -- that is done out-of-sample by EPJOB9 forward-
chain / EPJOB10 LOCO). This job materializes, for traceability + the feature catalog, that every
canonical e-family fits and predicts, plus an explicitly-labelled in-sample diagnostic (apparent RPS).
Honest data_insufficient if the joined eval rows are absent.

research_only / experimental. No network/API. 2026 WC excluded by the loader.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ep_lib as L

try:
    from wcdrawlab.research.event_process import eval as E, models as M
    from wcdrawlab.research.event_process import registry as REG
except Exception as e:  # pragma: no cover
    L.emit("failed", reason=f"EP eval/models import failed: {e!r}")
    raise SystemExit(0)


def main():
    try:
        data = E.load_eval_rows()
    except E.DataInsufficient as d:
        L.emit("data_insufficient", reason=f"cannot fit e0-e9: {d}")
        return
    rows = data["snapshot_rows"]
    club = E.load_club_aux_rows()

    # Fit on the FULL international population (in-sample record only). Club rows train e8's aux rep.
    preds = M.event_process_predictors(rows, club_rows=club, include_club_transfer=bool(club))
    fits = {}
    apparent = {}
    for mid, fn in preds.items():
        REG.assert_canonical(mid)
        sc = E._score_wdl(fn, rows)
        apparent[mid] = {"in_sample_rps": sc["rps"], "in_sample_logloss": sc["logloss"], "n": sc["n"]}
        fits[mid] = {"predicts": sc["n"] > 0,
                     "in_sample_rps": round(sc["rps"], 5) if sc["rps"] is not None else None}

    n_models = len(preds)
    all_predict = all(v["predicts"] for v in fits.values())
    L.write_json("ep_fit_e0_e9.json", {
        "note": "IN-SAMPLE fit record ONLY; not used for selection (see EPJOB9 forward-chain / EPJOB10 LOCO).",
        "model_version": M.MODEL_VERSION,
        "n_rows": len(rows), "n_matches": data["n_matches"], "n_competitions": data["n_competitions"],
        "n_club_aux_rows": len(club), "club_transfer_active": bool(club),
        "models": list(preds.keys()), "fits": fits, "in_sample_diagnostics": apparent,
        "reference_model": "research.event_process.e2", "utc": L.utc(),
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
    })
    L.emit("complete" if all_predict else "failed",
           reason=f"fit e0-e9 (goal-intensity) on {len(rows)} intl rows / {data['n_matches']} matches; "
                  f"club_aux_rows={len(club)} all_models_predict={all_predict}; IN-SAMPLE record only "
                  f"(selection is out-of-sample in EPJOB9/10)",
           state_updates={"n_e_families_fit": n_models, "n_eval_rows": len(rows),
                          "club_transfer_active": bool(club)})


main()
