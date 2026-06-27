"""JOB12 -- CALIBRATION + MATCH-LEVEL BOOTSTRAP + RELIABILITY. research_only.

Consumes the persisted LOCO W/D/L result (JOB8) and re-derives, leakage-safe:

  RELIABILITY / ECE   -- draw-channel reliability tables sliced by minute / score-state / player-count /
                         sub-state / coverage (dynamic_eval.reliability_tables), already produced inside the
                         LOCO run and re-summarized here as overall + per-slice ECE per model.
  MATCH-LEVEL BOOTSTRAP-- paired match-level bootstrap of (candidate - reference) RPS deltas for the
                         preregistered comparisons, using the per-MATCH RPS series (unit of resampling = the
                         match, not the row) via dynamic_eval.paired_bootstrap_delta.

Comparisons (candidate vs reference):
  p5 vs r2, p1 vs r2, r1 vs r0  (full corpus), and x3 vs r2, x2 vs r2  (xG subset, from JOB7 per-match rps).

complete when the LOCO artifact is present and >=1 bootstrap comparison is computable; data_insufficient
(honest) if the upstream LOCO artifact is missing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _mj_common as M  # noqa: E402
sys.path.insert(0, str(M.RJ))
import _job  # noqa: E402
sys.path.insert(0, str(M.SRC))
from wcdrawlab.research import dynamic_eval as DE  # noqa: E402


def _load(name):
    p = M.model_phase_dir(None) / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    rd = _job.run_dir()
    loco_art = _load("mj_job08_wdl_loco.json")
    if not loco_art or "loco" not in loco_art:
        M.write_artifact(rd, "mj_job12_calibration_bootstrap.json",
                         M.job_envelope("JOB12", "data_insufficient",
                                        reason="LOCO artifact (mj_job08) missing -> cannot bootstrap",
                                        start_ts=M.utc(), end_ts=M.utc()))
        _job.emit("data_insufficient", reason="upstream LOCO artifact missing")
        return

    pmr = loco_art["loco"]["per_model_match_rps"]
    reliability = loco_art["loco"].get("reliability", {})

    # overall + per-slice ECE summary per model (draw channel)
    rel_summary = {}
    for model, tbl in reliability.items():
        rel_summary[model] = {
            "overall_ece": tbl.get("_overall_ece"),
            "minute_bucket_ece": {b: v.get("ece") for b, v in tbl.get("minute_bucket", {}).items()},
            "score_state_ece": {b: v.get("ece") for b, v in tbl.get("score_state", {}).items()},
            "coverage_ece": {b: v.get("ece") for b, v in tbl.get("coverage", {}).items()},
        }

    # full-corpus paired match-level bootstraps
    comparisons = [
        ("research.wdl.player_team_state_p5", "research.wdl.remaining_time_poisson_r2"),
        ("research.wdl.player_starting_xi_p1", "research.wdl.remaining_time_poisson_r2"),
        ("research.wdl.time_score_baseline_r1", "research.wdl.static_b1_anchor_r0"),
        ("research.wdl.remaining_time_poisson_r2", "research.wdl.time_score_baseline_r1"),
    ]
    boots = {}
    for cand, ref in comparisons:
        boots[f"{cand.split('.')[-1]}_vs_{ref.split('.')[-1]}"] = DE.paired_bootstrap_delta(pmr, cand, ref)

    # xG-subset bootstraps from JOB7's forward-chain per-match rps (if present)
    xg_art = _load("mj_job07_xg_primary.json")
    xg_boots = {}
    if xg_art and xg_art.get("status") == "complete":
        # rebuild per-match rps for the xG subset directly (forward-chain folds carry it only transiently);
        # use the loco harness on the xG subset for a match-level series.
        try:
            xrows = M.load_xg_rows()
            from wcdrawlab.research import dynamic_models as DM
            xloco = DE.loco_wdl(xrows, DM.xg_wdl_predictors)
            xpmr = xloco["per_model_match_rps"]
            for cand, ref in [("research.wdl.xg_calibrated_hybrid_x3", "research.wdl.remaining_time_poisson_r2"),
                              ("research.wdl.xg_player_state_x2", "research.wdl.remaining_time_poisson_r2")]:
                xg_boots[f"{cand.split('.')[-1]}_vs_{ref.split('.')[-1]}"] = \
                    DE.paired_bootstrap_delta(xpmr, cand, ref)
        except Exception as e:
            xg_boots["note"] = f"xG bootstrap unavailable: {e}"

    env = M.job_envelope("JOB12", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         reliability_summary=rel_summary,
                         match_level_bootstrap=boots, xg_match_level_bootstrap=xg_boots,
                         bootstrap_note="negative mean_delta / ci95 upper<0 => candidate better; "
                                        "resampling unit is the MATCH")
    M.write_artifact(rd, "mj_job12_calibration_bootstrap.json", env)
    favored = [k for k, v in {**boots, **xg_boots}.items()
               if isinstance(v, dict) and v.get("favors_candidate")]
    _job.emit("complete",
              reason=f"reliability+match-level bootstrap done; candidate-favored comparisons: {favored}",
              state_updates={"bootstrap_favored": favored})


if __name__ == "__main__":
    main()
