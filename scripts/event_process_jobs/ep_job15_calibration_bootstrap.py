"""EPJOB15 -- CALIBRATION + MATCH-LEVEL BOOTSTRAP + FAILURE ANALYSIS.

Consolidates the out-of-sample W/D/L (EPJOB9/10) and binary (EPJOB11-13) artifacts and adds:
  * CALIBRATION: draw-channel reliability (slope / intercept / ECE) for the W/D/L family (from the LOCO
    artifact) + per-family binary calibration (from each binary artifact's pooled calibration);
  * MATCH-LEVEL BOOTSTRAP: 1000x paired match-bootstrap of (candidate - reference) RPS/Brier deltas with
    a 95% CI, recomputed here from the per-match series for the headline candidates;
  * FAILURE ANALYSIS: a fresh LOCO pass scoring e2 (reference) vs e7 (full event-process) on disjoint
    score-state / completeness / xG subgroups, surfacing exactly WHERE the event-process state changes
    the W/D/L RPS (positive == e7 worse than e2 there).

If a prerequisite artifact is absent, the corresponding section is reported as skipped (honest), never
fabricated. Honest data_insufficient if no eval rows exist at all. research_only / experimental.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ep_lib as L

try:
    from wcdrawlab.research.event_process import eval as E, models as M
except Exception as e:  # pragma: no cover
    L.emit("failed", reason=f"EP eval/models import failed: {e!r}")
    raise SystemExit(0)

REF = "research.event_process.e2"
WDL_CANDS = [f"research.event_process.e{i}" for i in (3, 7, 8, 9)]


def main():
    try:
        data = E.load_eval_rows()
    except E.DataInsufficient as d:
        L.emit("data_insufficient", reason=f"calibration/bootstrap not possible: {d}")
        return
    rows = data["snapshot_rows"]
    club = E.load_club_aux_rows()

    out = {"reference": REF, "n_rows": len(rows), "n_matches": data["n_matches"],
           "utc": L.utc(), "sections": {},
           "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"}

    # ---- W/D/L LOCO for calibration + per-match bootstrap (one authoritative pass) ----
    fac = E.make_wdl_factory(club_rows=club, include_club_transfer=bool(club))
    lc = E.loco_wdl(rows, predictor_factory=fac)
    out["sections"]["wdl_calibration_draw_channel"] = lc["reliability"]
    boots = {c: E.paired_bootstrap_delta(lc["per_model_match_rps"], c, REF, n=1000) for c in WDL_CANDS}
    out["sections"]["wdl_match_bootstrap_vs_e2"] = boots

    # ---- binary family calibration (pull from this run's binary artifacts if present) ----
    bins = {}
    for fname, ref in (("ep_next_goal_loco.json", "research.next_goal.q0"),
                       ("ep_near_term_scoring_loco.json", "research.scoring.h0"),
                       ("ep_discipline_loco.json", "research.discipline.y0")):
        art = L.read_json(fname)
        if art is None:
            bins[fname] = {"status": "absent_skipped", "note": "run the producing job first"}
            continue
        bins[fname] = {"reference": ref, "pooled": art.get("pooled"),
                       "base_rate": art.get("base_rate"), "gate_open": art.get("gate_open")}
    out["sections"]["binary_family_summaries"] = bins

    # ---- FAILURE ANALYSIS: e2 vs e7 RPS by disjoint subgroup ----
    def _e2_e7_factory(train):
        return {REF: M.e2_reference,
                "research.event_process.e7": M.IntensityWDL(M.FULL_STATE_COLS).fit(train).predict_one}

    def _diff(r):
        try:
            return abs(int(round(float(r.get("goals_diff") or 0))))
        except (TypeError, ValueError):
            return 0

    groups = {
        "level": lambda r: _diff(r) == 0,
        "one_goal": lambda r: _diff(r) == 1,
        "two_plus_goal": lambda r: _diff(r) >= 2,
        "xg_present": lambda r: r.get("xg_present") in ("True", "true", True),
        "first_half": lambda r: float(r.get("snapshot_minute") or 0) < 45,
        "second_half": lambda r: float(r.get("snapshot_minute") or 0) >= 45,
    }
    import _common as CM
    fail = {g: {} for g in groups}
    acc = {g: {} for g in groups}
    for held, train, test in CM.loco_folds(rows):
        preds = _e2_e7_factory(train)
        for gname, pred in groups.items():
            tsub = [r for r in test if pred(r)]
            if not tsub:
                continue
            for mid, fn in preds.items():
                sc = E._score_wdl(fn, tsub)
                if sc["rps"] is not None:
                    acc[gname].setdefault(mid, []).append(sc["rps"])
    for gname in groups:
        e2v = acc[gname].get(REF, [])
        e7v = acc[gname].get("research.event_process.e7", [])
        fail[gname] = {
            "n_folds_scored": len(e2v),
            "e2_rps": round(sum(e2v) / len(e2v), 5) if e2v else None,
            "e7_rps": round(sum(e7v) / len(e7v), 5) if e7v else None,
            "e7_minus_e2": (round(sum(e7v) / len(e7v) - sum(e2v) / len(e2v), 5)
                            if (e2v and e7v) else None),
        }
    out["sections"]["failure_analysis_e2_vs_e7_by_subgroup"] = fail

    L.write_json("ep_calibration_bootstrap_failure.json", out)
    favored = [c for c, b in boots.items() if b.get("favors_candidate")]
    L.emit("complete",
           reason=f"calibration + 1000x match-bootstrap (e3/e7/e8/e9 vs e2) + failure analysis over "
                  f"{len(groups)} subgroups; bootstrap_favored_candidates={favored or 'none'}",
           state_updates={"calibration_done": True, "bootstrap_favored": len(favored),
                          "failure_subgroups": len(groups)})


main()
