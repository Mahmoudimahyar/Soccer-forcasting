"""JOB8 -- SECONDARY Leave-One-International-Competition-Out (LOCO) W/D/L evaluation. research_only.

The robustness companion to the forward-chaining primary: each international competition is held out as the
test fold while all OTHER international competitions train (dynamic_eval.loco_wdl). Club rows are NEVER test
rows. Produces per-fold per-model metrics, draw-channel reliability tables, and the per-match RPS series used
later by the bootstrap (JOB12) and candidate-rule evaluator (JOB14).

Models: r0,r1,r2,p1-p5 (dynamic_models.wdl_predictors). complete when >=2 LOCO folds score.
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
        rows = M.load_wdl_rows()
    except M.DataInsufficient as e:
        M.write_artifact(rd, "mj_job08_wdl_loco.json",
                         M.job_envelope("JOB8", "data_insufficient", reason=str(e), start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason=str(e))
        return

    loco = DE.loco_wdl(rows, DM.wdl_predictors)
    if loco["n_folds"] < 2:
        M.write_artifact(rd, "mj_job08_wdl_loco.json",
                         M.job_envelope("JOB8", "data_insufficient",
                                        reason=f"only {loco['n_folds']} LOCO fold(s)", start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason="fewer than 2 LOCO folds")
        return

    # persist a compact LOCO summary (folds + reliability + per-match rps kept for downstream jobs)
    folds = []
    for f in loco["folds"]:
        models = {n: {k: v for k, v in m.items() if k != "rows_detail"} for n, m in f["models"].items()}
        folds.append({"held_competition": f["held_competition"], "n_train_rows": f["n_train_rows"],
                      "n_test_rows": f["n_test_rows"], "models": models})
    out = {"protocol": "loco", "n_folds": loco["n_folds"], "folds": folds,
           "reliability": loco["reliability"], "per_model_match_rps": loco["per_model_match_rps"]}
    env = M.job_envelope("JOB8", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         n_rows=len(rows), loco=out)
    M.write_artifact(rd, "mj_job08_wdl_loco.json", env)

    # pooled mean RPS per model across folds (for the report)
    import numpy as np
    pooled = {}
    for f in folds:
        for n, m in f["models"].items():
            if m.get("rps") is not None:
                pooled.setdefault(n, []).append(m["rps"])
    pooled_mean = {n: float(np.mean(v)) for n, v in pooled.items()}
    _job.emit("complete",
              reason=f"LOCO W/D/L over {loco['n_folds']} competitions; per-match RPS series persisted",
              state_updates={"wdl_loco_folds": loco["n_folds"], "wdl_loco_pooled_rps": pooled_mean})


if __name__ == "__main__":
    main()
