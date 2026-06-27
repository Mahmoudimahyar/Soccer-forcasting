"""JOB6 -- PRIMARY forward-chaining W/D/L evaluation (R0,R1,R2,P1-P5). research_only.

Runs the canonical leakage-safe FORWARD-CHAINING tournament evaluation of the W/D/L family on the pre-2026
international decision-minute rows. Competitions are ordered by earliest kickoff and every model is fit ONLY
on strictly-earlier competitions, then scored on the next one (dynamic_eval.forward_chain_wdl). Models scored:

  research.wdl.static_b1_anchor_r0, research.wdl.time_score_baseline_r1, research.wdl.remaining_time_poisson_r2,
  research.wdl.player_starting_xi_p1, research.wdl.player_on_pitch_p2, research.wdl.player_substitution_delta_p3,
  research.wdl.player_composition_p4, research.wdl.player_team_state_p5.

All fitting/scaling/calibration happen INSIDE the train rows of each fold. Emits the per-fold + pooled
RPS/logloss/Brier-draw. complete when >=1 forward-chain fold scores; data_insufficient otherwise.
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


def _strip(fc):
    """Drop the heavy per-row detail; keep pooled + per-fold per-model metrics."""
    folds = []
    for f in fc["folds"]:
        models = {n: {k: v for k, v in m.items() if k != "rows_detail"} for n, m in f["models"].items()}
        folds.append({"test_competition": f["test_competition"], "n_train_comps": f["n_train_comps"],
                      "n_train_rows": f["n_train_rows"], "n_test_rows": f["n_test_rows"], "models": models})
    return {"protocol": fc["protocol"], "competition_order": fc["competition_order"],
            "n_folds": fc["n_folds"], "folds": folds, "pooled": fc["pooled"]}


def main():
    rd = _job.run_dir()
    try:
        rows = M.load_wdl_rows()
    except M.DataInsufficient as e:
        M.write_artifact(rd, "mj_job06_wdl_primary.json",
                         M.job_envelope("JOB6", "data_insufficient", reason=str(e), start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason=str(e))
        return

    fc = DE.forward_chain_wdl(rows, DM.wdl_predictors)
    if fc["n_folds"] < 1:
        M.write_artifact(rd, "mj_job06_wdl_primary.json",
                         M.job_envelope("JOB6", "data_insufficient",
                                        reason="no forward-chain fold could be formed (need >=2 competitions)",
                                        start_ts=M.utc(), end_ts=M.utc(), competition_order=fc["competition_order"]))
        _job.emit("data_insufficient", reason="insufficient competitions for forward chaining")
        return

    out = _strip(fc)
    env = M.job_envelope("JOB6", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         n_rows=len(rows), n_matches=len(set(r["match_id"] for r in rows)),
                         forward_chain=out)
    M.write_artifact(rd, "mj_job06_wdl_primary.json", env)
    pooled = out["pooled"]
    r2 = pooled.get("research.wdl.remaining_time_poisson_r2", {}).get("rps")
    p5 = pooled.get("research.wdl.player_team_state_p5", {}).get("rps")
    _job.emit("complete",
              reason=f"forward-chain W/D/L: {fc['n_folds']} folds; r2 rps={r2:.4f} p5 rps={p5:.4f}",
              state_updates={"wdl_forward_folds": fc["n_folds"],
                             "wdl_pooled_rps": {k: v.get("rps") for k, v in pooled.items()}})


if __name__ == "__main__":
    main()
