"""JOB13 -- STRUCTURED FAILURE ANALYSIS. research_only.

Re-runs a leakage-safe LOCO pass of the W/D/L p5 model (and r2 reference) to obtain per-row predictions, then
characterizes WHERE the dynamic models fail, across the preregistered failure dimensions:

  * worst OVERCONFIDENT misses (high prob on the wrong outcome -> largest log-loss);
  * DRAW-STATE rows (level score) reliability vs lead/trail;
  * LATE-GAME rows (minute>60);
  * RED-CARD-STATE rows (player_count_diff != 0);
  * POST-SUB rows (subs_diff != 0);
  * SPARSE-PLAYER-HISTORY rows (high prematch_impact_uncertainty / low coverage);
  * CLUB->INTERNATIONAL transfer note (club rows are auxiliary-only; quantifies the share of international
    on-pitch players whose prior history is club-sourced -> the transfer-generalization risk);
  * xG-MOMENTUM rows (|xg_momentum| large) on the xG subset;
  * COMPLEX-FEATURE-WORSENS cases (read from JOB11 ablations).

Emits concrete counts + representative rows per bucket. complete when the LOCO pass yields rows;
data_insufficient otherwise.
"""
from __future__ import annotations

import json
import math
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


def _collect_detail(rows, model_id):
    detail = []
    for held, train, test in C.loco_folds(rows):
        preds = DM.wdl_predictors(train)
        fn = preds[model_id]
        sc = DE._score_wdl(fn, test)
        detail.extend(sc["rows_detail"])
    return detail


def _repr(d):
    r = d["row"]
    return {"match_id": r["match_id"], "competition": r["competition"], "minute": r["minute"],
            "score_diff": r["score_diff"], "player_count_diff": r.get("player_count_diff", 0),
            "subs_diff": r.get("subs_diff", 0), "target": r["target_wdl"],
            "p": {k: round(v, 3) for k, v in d["p"].items()}, "logloss": round(C.logloss3(d["p"], r["target_wdl"]), 3)}


def main():
    rd = _job.run_dir()
    try:
        rows = M.load_wdl_rows()
    except M.DataInsufficient as e:
        M.write_artifact(rd, "mj_job13_failure_analysis.json",
                         M.job_envelope("JOB13", "data_insufficient", reason=str(e), start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason=str(e))
        return

    detail = _collect_detail(rows, "research.wdl.player_team_state_p5")
    for d in detail:
        d["ll"] = C.logloss3(d["p"], d["row"]["target_wdl"])

    def bucket_stats(pred):
        sub = [d for d in detail if pred(d["row"])]
        if not sub:
            return {"n": 0}
        return {"n": len(sub), "mean_logloss": float(np.mean([d["ll"] for d in sub])),
                "mean_rps": float(np.mean([d["rps"] for d in sub]))}

    analysis = {
        "worst_overconfident": [_repr(d) for d in sorted(detail, key=lambda x: -x["ll"])[:10]],
        "draw_state": bucket_stats(lambda r: int(r["score_diff"]) == 0),
        "lead_state": bucket_stats(lambda r: int(r["score_diff"]) > 0),
        "trail_state": bucket_stats(lambda r: int(r["score_diff"]) < 0),
        "late_game_gt60": bucket_stats(lambda r: int(r["minute"]) > 60),
        "red_card_state": bucket_stats(lambda r: int(r.get("player_count_diff", 0)) != 0),
        "post_sub": bucket_stats(lambda r: int(r.get("subs_diff", 0)) != 0),
        "sparse_player_history": bucket_stats(
            lambda r: float(r.get("prematch_impact_uncertainty", 1.0)) >= 0.8
            or float(r.get("prematch_impact_coverage", 0.0)) <= 0.2),
    }

    # club->international transfer note: share of international on-pitch player-history that is club-sourced
    transfer = {"note": "club rows are auxiliary player-prior history ONLY, never test rows; the prior for an "
                        "international on-pitch player may be dominated by club appearances -> transfer risk."}
    prior_audit = M.PRIORS_DIR / "dynamic_player_priors_audit.json"
    if prior_audit.exists():
        try:
            pa = json.loads(prior_audit.read_text(encoding="utf-8"))
            transfer["prior_audit_excerpt"] = {k: pa[k] for k in pa
                                               if k in ("coverage_rate", "unknown_share", "real_output")}
        except Exception as e:
            transfer["prior_audit_error"] = str(e)
    analysis["club_to_international_transfer"] = transfer

    # xG-momentum failures on the xG subset
    try:
        xrows = M.load_xg_rows()
        xdetail = []
        for held, train, test in C.loco_folds(xrows):
            preds = DM.xg_wdl_predictors(train)
            fn = preds["research.wdl.xg_calibrated_hybrid_x3"]
            sc = DE._score_wdl(fn, test)
            xdetail.extend(sc["rows_detail"])
        for d in xdetail:
            d["ll"] = C.logloss3(d["p"], d["row"]["target_wdl"])
        big_mom = [d for d in xdetail if abs(float(d["row"].get("xg_momentum", 0.0))) >= 0.3]
        analysis["xg_momentum"] = {
            "n_high_momentum": len(big_mom),
            "mean_logloss_high_momentum": (float(np.mean([d["ll"] for d in big_mom])) if big_mom else None),
            "worst_high_momentum": [_repr(d) for d in sorted(big_mom, key=lambda x: -x["ll"])[:5]],
        }
    except M.DataInsufficient as e:
        analysis["xg_momentum"] = {"note": str(e)}

    # complex-feature-worsens (from JOB11)
    abl_p = M.model_phase_dir(None) / "mj_job11_ablations.json"
    if abl_p.exists():
        try:
            abl = json.loads(abl_p.read_text(encoding="utf-8"))
            analysis["complex_feature_worsens"] = abl.get("ablations", {}).get("complex_feature_worsens", [])
        except Exception as e:
            analysis["complex_feature_worsens_error"] = str(e)

    env = M.job_envelope("JOB13", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         model_analyzed="research.wdl.player_team_state_p5", n_rows=len(detail),
                         failure_analysis=analysis)
    M.write_artifact(rd, "mj_job13_failure_analysis.json", env)
    _job.emit("complete",
              reason=f"structured failure analysis over {len(detail)} rows across "
                     f"{len([k for k in analysis if isinstance(analysis[k], dict)])} dimensions",
              state_updates={"failure_dimensions": [k for k in analysis]})


if __name__ == "__main__":
    main()
