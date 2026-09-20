"""JOB11 -- MANDATORY ABLATIONS. research_only.

Runs the preregistered ablation ladder by REAL re-evaluation (LOCO) and by reading the forward-chain results,
isolating the marginal value of each feature block:

  WDL ladder (vs the r2 remaining-time-Poisson reference):
    + pre-match starting-XI impact            (r2 -> p1)
    + current on-pitch impact                 (p1 -> p2)
    + substitution-delta history              (p2 -> p3)
    + composition / continuity                (p3 -> p4)
    + full team-state (cards/red/subs)        (p4 -> p5)
  xG ladder (xG-eligible subset, vs r2):
    + xG event-state                          (r2 -> x1)
    + player-impact on xG subset              (r2 -> x2)
    + calibrated hybrid blend                 (r2 -> x3)
  next-goal ladder (vs n0 base rate):
    + cards/subs                              (n0 -> n1)
    + on-pitch impact                         (n1 -> n2)
    + sub delta                               (n2 -> n3)
    + xG player fusion                        (n2 -> n4)
  "complex-feature-worsens" detector: any ladder step whose mean metric gets WORSE is flagged (these feed the
  structured failure analysis in JOB13).

Each ablation delta is the pooled-mean metric difference across LOCO folds (negative = the added block
helps). complete when at least the WDL ladder evaluates; honest data_insufficient if rows are unavailable.
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


def _pooled_rps(rows, factory):
    per = {}
    for held, train, test in C.loco_folds(rows):
        preds = factory(train)
        for n, fn in preds.items():
            sc = DE._score_wdl(fn, test)
            if sc["rps"] is not None:
                per.setdefault(n, []).append(sc["rps"])
    return {n: float(np.mean(v)) for n, v in per.items()}


def _pooled_brier(rows, factory, target):
    per = {}
    for held, train, test in C.loco_folds(rows):
        preds = factory(train)
        for n, fn in preds.items():
            sc = DE._score_binary(fn, test, target)
            if sc["brier"] is not None:
                per.setdefault(n, []).append(sc["brier"])
    return {n: float(np.mean(v)) for n, v in per.items()}


def _ladder(metric_map, steps):
    out = []
    for label, a, b in steps:
        if a in metric_map and b in metric_map:
            out.append({"step": label, "from": a, "to": b,
                        "from_metric": metric_map[a], "to_metric": metric_map[b],
                        "delta": metric_map[b] - metric_map[a],
                        "helps": metric_map[b] < metric_map[a]})
    return out


def main():
    rd = _job.run_dir()
    try:
        wdl = M.load_wdl_rows()
    except M.DataInsufficient as e:
        M.write_artifact(rd, "mj_job11_ablations.json",
                         M.job_envelope("JOB11", "data_insufficient", reason=str(e), start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason=str(e))
        return

    wdl_rps = _pooled_rps(wdl, DM.wdl_predictors)
    wdl_steps = [
        ("+prematch_xi (r2->p1)", "research.wdl.remaining_time_poisson_r2", "research.wdl.player_starting_xi_p1"),
        ("+onpitch (p1->p2)", "research.wdl.player_starting_xi_p1", "research.wdl.player_on_pitch_p2"),
        ("+sub_delta (p2->p3)", "research.wdl.player_on_pitch_p2", "research.wdl.player_substitution_delta_p3"),
        ("+composition (p3->p4)", "research.wdl.player_substitution_delta_p3", "research.wdl.player_composition_p4"),
        ("+team_state (p4->p5)", "research.wdl.player_composition_p4", "research.wdl.player_team_state_p5"),
    ]
    ablations = {"wdl_ladder_rps": _ladder(wdl_rps, wdl_steps), "wdl_pooled_rps": wdl_rps}

    # xG ladder (subset)
    try:
        xrows = M.load_xg_rows()
        xg_rps = _pooled_rps(xrows, DM.xg_wdl_predictors)
        xg_steps = [
            ("+xg_event (r2->x1)", "research.wdl.remaining_time_poisson_r2", "research.wdl.xg_event_state_x1"),
            ("+player (r2->x2)", "research.wdl.remaining_time_poisson_r2", "research.wdl.xg_player_state_x2"),
            ("+calibrated_blend (r2->x3)", "research.wdl.remaining_time_poisson_r2",
             "research.wdl.xg_calibrated_hybrid_x3"),
        ]
        ablations["xg_ladder_rps"] = _ladder(xg_rps, xg_steps)
        ablations["xg_pooled_rps"] = xg_rps
    except M.DataInsufficient as e:
        ablations["xg_note"] = str(e)

    # next-goal ladder
    ng_brier = _pooled_brier(wdl, lambda tr: DM.nextgoal_predictors(tr, "next_goal_15"), "next_goal_15")
    ng_steps = [
        ("+cards_subs (n0->n1)", "research.next_goal.time_score_n0", "research.next_goal.time_score_cards_subs_n1"),
        ("+onpitch (n1->n2)", "research.next_goal.time_score_cards_subs_n1", "research.next_goal.player_on_pitch_n2"),
        ("+sub_delta (n2->n3)", "research.next_goal.player_on_pitch_n2", "research.next_goal.substitution_delta_n3"),
        ("+xg_fusion (n2->n4)", "research.next_goal.player_on_pitch_n2", "research.next_goal.xg_player_fusion_n4"),
    ]
    ablations["nextgoal_ladder_brier"] = _ladder(ng_brier, ng_steps)
    ablations["nextgoal_pooled_brier"] = ng_brier

    # complex-feature-worsens detector across all ladders
    worsens = []
    for key in ("wdl_ladder_rps", "xg_ladder_rps", "nextgoal_ladder_brier"):
        for s in ablations.get(key, []):
            if not s["helps"]:
                worsens.append({"ladder": key, **{k: s[k] for k in ("step", "delta")}})
    ablations["complex_feature_worsens"] = worsens

    env = M.job_envelope("JOB11", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         n_wdl_rows=len(wdl), ablations=ablations)
    M.write_artifact(rd, "mj_job11_ablations.json", env)
    _job.emit("complete",
              reason=f"ablation ladders evaluated; {len(worsens)} step(s) where complexity worsens metric",
              state_updates={"ablation_worsens_count": len(worsens)})


if __name__ == "__main__":
    main()
