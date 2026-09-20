"""JOB7 -- PRIMARY xG W/D/L evaluation (R2 reference, X1, X2, X3). research_only.

Forward-chaining evaluation of the xG-fusion W/D/L family on the EXACT-bridge xG-ELIGIBLE subset only
(nonzero StatsBomb xG snapshots). Models scored (dynamic_models.xg_wdl_predictors):

  research.wdl.remaining_time_poisson_r2  (reference, parameter-free),
  research.wdl.xg_event_state_x1          (xG event-state logistic),
  research.wdl.xg_player_state_x2         (player-impact logistic on the xG subset),
  research.wdl.xg_calibrated_hybrid_x3    (fixed-form calibrated blend of r2/x1/x2; calibrators fit
                                           INSIDE training only).

If the xG subset spans only ONE competition (so a forward-chain fold cannot be formed), the job HONESTLY
emits a single-pool in-sample-free comparison is NOT possible and records threshold_blocked with the
competition span -- it never fabricates a fold. complete only when >=1 leakage-safe fold scores.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _mj_common as M  # noqa: E402
sys.path.insert(0, str(M.RJ))
import _job  # noqa: E402
sys.path.insert(0, str(M.SRC))
from wcdrawlab.research import dynamic_eval as DE, dynamic_models as DM  # noqa: E402


def main():
    rd = _job.run_dir()
    try:
        rows = M.load_xg_rows()
    except M.DataInsufficient as e:
        M.write_artifact(rd, "mj_job07_xg_primary.json",
                         M.job_envelope("JOB7", "data_insufficient", reason=str(e), start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason=str(e))
        return

    comps = sorted({r["competition"] for r in rows})
    n_matches = len(set(r["match_id"] for r in rows))
    nonzero = any(abs(r.get("cum_xg_diff", 0.0)) > 0 for r in rows)

    fc = DE.forward_chain_wdl(rows, DM.xg_wdl_predictors)
    if fc["n_folds"] < 1:
        env = M.job_envelope("JOB7", "threshold_blocked", start_ts=M.utc(), end_ts=M.utc(),
                             reason="xG-eligible subset spans <2 competitions -> no leakage-safe "
                                    "forward-chain fold; xG models NOT scored to avoid in-sample leakage",
                             xg_competitions=comps, n_xg_rows=len(rows), n_xg_matches=n_matches,
                             xg_subset_nonzero=nonzero)
        M.write_artifact(rd, "mj_job07_xg_primary.json", env)
        _job.emit("threshold_blocked",
                  reason=f"xG subset spans only {comps} -> cannot form forward-chain fold (honest skip)",
                  state_updates={"xg_forward_folds": 0, "xg_competitions": comps})
        return

    # strip per-row detail
    folds = []
    for f in fc["folds"]:
        models = {n: {k: v for k, v in m.items() if k != "rows_detail"} for n, m in f["models"].items()}
        folds.append({"test_competition": f["test_competition"], "n_train_rows": f["n_train_rows"],
                      "n_test_rows": f["n_test_rows"], "models": models})
    out = {"protocol": "forward_chain", "competition_order": fc["competition_order"],
           "n_folds": fc["n_folds"], "folds": folds, "pooled": fc["pooled"]}
    env = M.job_envelope("JOB7", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         n_xg_rows=len(rows), n_xg_matches=n_matches, xg_subset_nonzero=nonzero,
                         xg_competitions=comps, forward_chain=out)
    M.write_artifact(rd, "mj_job07_xg_primary.json", env)
    pooled = fc["pooled"]
    r2 = pooled.get("research.wdl.remaining_time_poisson_r2", {}).get("rps")
    x3 = pooled.get("research.wdl.xg_calibrated_hybrid_x3", {}).get("rps")
    _job.emit("complete",
              reason=f"xG forward-chain on {n_matches} bridge matches: r2 rps={r2:.4f} x3 rps={x3:.4f}",
              state_updates={"xg_forward_folds": fc["n_folds"],
                             "xg_pooled_rps": {k: v.get("rps") for k, v in pooled.items()}})


if __name__ == "__main__":
    main()
