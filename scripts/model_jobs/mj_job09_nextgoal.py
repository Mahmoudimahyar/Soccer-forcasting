"""JOB9 -- NEXT-GOAL discrete-time hazard evaluation (N0-N4). research_only.

LOCO evaluation of the next-goal family P(regulation goal in next 15') on the international decision-minute
rows (dynamic_models.nextgoal_predictors), scored with the shared binary harness (Brier / logloss / ECE),
per-match Brier persisted. Models:

  research.next_goal.time_score_n0, research.next_goal.time_score_cards_subs_n1,
  research.next_goal.player_on_pitch_n2, research.next_goal.substitution_delta_n3,
  research.next_goal.xg_player_fusion_n4.

n4 uses xG columns -- on rows without xG those columns are imputed on the TRAIN mean + unknown flag inside
dynamic_models (graceful degradation), so n4 reduces toward n2 where xG is absent rather than crashing.
complete when >=2 LOCO folds score; data_insufficient otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _mj_common as M  # noqa: E402
sys.path.insert(0, str(M.RJ))
import _job  # noqa: E402
sys.path.insert(0, str(M.SRC))
import _common as C  # noqa: E402
from wcdrawlab.research import dynamic_eval as DE, dynamic_models as DM  # noqa: E402


def main():
    rd = _job.run_dir()
    try:
        rows = M.load_nextgoal_rows()
    except M.DataInsufficient as e:
        M.write_artifact(rd, "mj_job09_nextgoal.json",
                         M.job_envelope("JOB9", "data_insufficient", reason=str(e), start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason=str(e))
        return

    folds = []
    per_model_match_brier = {}
    for held, train, test in C.loco_folds(rows):
        preds = DM.nextgoal_predictors(train, target_key="next_goal_15")
        fold = {"held_competition": held, "n_train_rows": len(train), "n_test_rows": len(test), "models": {}}
        for name, fn in preds.items():
            sc = DE._score_binary(fn, test, "next_goal_15")
            fold["models"][name] = {k: v for k, v in sc.items() if k != "per_match_brier"}
            mm = per_model_match_brier.setdefault(name, {})
            for m, v in sc["per_match_brier"].items():
                mm.setdefault(m, []).append(v)
        folds.append(fold)

    if len(folds) < 2:
        M.write_artifact(rd, "mj_job09_nextgoal.json",
                         M.job_envelope("JOB9", "data_insufficient",
                                        reason=f"only {len(folds)} next-goal fold(s)", start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason="fewer than 2 next-goal LOCO folds")
        return

    pooled = {}
    for f in folds:
        for n, m in f["models"].items():
            if m.get("brier") is not None:
                pooled.setdefault(n, {"brier": [], "logloss": []})
                pooled[n]["brier"].append(m["brier"])
                if m.get("logloss") is not None:
                    pooled[n]["logloss"].append(m["logloss"])
    pooled_summary = {n: {"brier": float(np.mean(v["brier"])),
                          "logloss": float(np.mean(v["logloss"])) if v["logloss"] else None}
                      for n, v in pooled.items()}
    per_model_match_mean = {n: {m: float(np.mean(v)) for m, v in mm.items()}
                            for n, mm in per_model_match_brier.items()}
    env = M.job_envelope("JOB9", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         n_rows=len(rows), positive_rate=round(sum(r["next_goal_15"] for r in rows) /
                                                               max(1, len(rows)), 4),
                         n_folds=len(folds), folds=folds, pooled=pooled_summary,
                         per_model_match_brier=per_model_match_mean)
    M.write_artifact(rd, "mj_job09_nextgoal.json", env)
    _job.emit("complete",
              reason=f"next-goal LOCO over {len(folds)} folds; "
                     f"n1 brier={pooled_summary.get('research.next_goal.time_score_cards_subs_n1', {}).get('brier'):.4f}",
              state_updates={"nextgoal_folds": len(folds),
                             "nextgoal_pooled_brier": {n: v["brier"] for n, v in pooled_summary.items()}})


if __name__ == "__main__":
    main()
