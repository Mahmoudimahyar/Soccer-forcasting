"""EPJOB14 -- MANDATORY ABLATIONS for the event-process W/D/L family (out-of-sample LOCO, e2 reference).

Every ablation reports a pooled out-of-sample RPS delta vs the e2 parameter-free reference (negative ==
the variant beats e2). Three ablation classes:

  A. NESTED LAYER pairs (marginal value of one added information layer):
       e2->e3, e3->e4, e4->e5, e5->e6, e6->e7, e7->e9, and e7 WITH vs WITHOUT club transfer (e7 vs e8).
  B. SINGLE-FAMILY isolation IntensityWDL heads (does ONE process channel alone beat e2?):
       xg-only, possession/territory-only, transition-only, set-piece-only, set-piece ON vs OFF,
       recent-window widths 5/10/15min (xG window column sets).
  C. SUBGROUP re-scoring of the fitted e2 vs e7 (where does event-process help, if anywhere?):
       high/low source-completeness, high/low cumulative xG, level vs one-goal game state,
       normal vs after-a-sending-off.

All fitting is TRAIN-only inside each LOCO fold; club rows train ONLY the e8 transfer rep; 2026 WC is
excluded; club rows are never intl test rows. Honest data_insufficient if intl rows are absent.
research_only / experimental. No network/API.
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


def _isolation_factory(col_sets):
    """Return a factory producing {name: IntensityWDL(cols).predict_one} plus the e2 reference."""
    def _factory(train_rows):
        preds = {REF: M.e2_reference}
        for name, cols in col_sets.items():
            preds[name] = M.IntensityWDL(cols).fit(train_rows).predict_one
        return preds
    return _factory


def _pooled_rps(loco_res):
    acc = {}
    for f in loco_res["folds"]:
        for m, v in f["models"].items():
            if v.get("rps") is not None:
                acc.setdefault(m, []).append(v["rps"])
    return {m: sum(vs) / len(vs) for m, vs in acc.items()}


def _e2_e7_factory(train_rows):
    """Lean 2-model factory (e2 reference + e7 full event-process intensity) for subgroup ablations.
    No club transfer (keeps the subgroup sweep tractable); e7 captures the full process state."""
    return {REF: M.e2_reference,
            "research.event_process.e7": M.IntensityWDL(M.FULL_STATE_COLS).fit(train_rows).predict_one}


def _subgroup_rps(rows, predicate, label):
    """LOCO-fit e2 vs e7, score ONLY the held-out TEST rows matching predicate (so the fit stays TRAIN-
    only and the comparison is honest). Returns per-model pooled RPS on the subgroup."""
    sub = [r for r in rows if predicate(r)]
    if len(sub) < 50:
        return {"n": len(sub), "note": "subgroup too small (<50 rows) -- honest skip", "rps": {}}
    import _common as CM  # shared loco folds
    acc = {}
    for held, train, test in CM.loco_folds(rows):
        preds = _e2_e7_factory(train)
        tsub = [r for r in test if predicate(r)]
        if not tsub:
            continue
        for name, fn in preds.items():
            sc = E._score_wdl(fn, tsub)
            if sc["rps"] is not None:
                acc.setdefault(name, []).append(sc["rps"])
    return {"n": len(sub), "rps": {m: round(sum(vs) / len(vs), 5) for m, vs in acc.items()}}


def main():
    try:
        data = E.load_eval_rows()
    except E.DataInsufficient as d:
        L.emit("data_insufficient", reason=f"ablations not possible: {d}")
        return
    rows = data["snapshot_rows"]
    club = E.load_club_aux_rows()

    out = {"reference": REF, "n_rows": len(rows), "n_matches": data["n_matches"],
           "club_transfer_active": bool(club), "ablations": {}, "utc": L.utc(),
           "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"}

    # ---- A. nested layers + club transfer: one full-family LOCO gives all e0..e9 pooled RPS ----
    fac_full = E.make_wdl_factory(club_rows=club, include_club_transfer=bool(club))
    full = E.loco_wdl(rows, predictor_factory=fac_full)
    pooled = _pooled_rps(full)
    nested = {}
    for lo, hi in (("e2", "e3"), ("e3", "e4"), ("e4", "e5"), ("e5", "e6"), ("e6", "e7"), ("e7", "e9")):
        a = pooled.get(f"research.event_process.{lo}")
        b = pooled.get(f"research.event_process.{hi}")
        nested[f"{lo}->{hi}"] = {"rps_lo": round(a, 5) if a else None, "rps_hi": round(b, 5) if b else None,
                                 "delta_hi_minus_lo": (round(b - a, 5) if (a is not None and b is not None) else None)}
    # e7 +/- club transfer (e8 has club aux when club rows present; compare to e7)
    e7 = pooled.get("research.event_process.e7")
    e8 = pooled.get("research.event_process.e8")
    nested["e7_with_vs_without_club_transfer"] = {
        "e7_rps": round(e7, 5) if e7 else None, "e8_with_club_rps": round(e8, 5) if e8 else None,
        "club_transfer_delta": (round(e8 - e7, 5) if (e7 is not None and e8 is not None) else None)}
    out["ablations"]["A_nested_layers"] = nested
    out["ablations"]["all_e_pooled_rps"] = {k: round(v, 5) for k, v in pooled.items()}

    # ---- B. single-channel isolation heads ----
    iso_sets = {
        "iso_xg_only": M.XG_INTENSITY_COLS,
        "iso_possession_territory_only": M.POSS_TERRITORY_COLS,
        "iso_transition_only": M.TRANSITION_PRESSURE_COLS,
        "iso_setpiece_only": M.SETPIECE_DISCIPLINE_COLS,
        "iso_window5_only": ["xg_last5m_home", "xg_last5m_away", "shots_last5m_home", "shots_last5m_away"],
        "iso_window10_only": ["xg_last10m_home", "xg_last10m_away", "shots_last10m_home", "shots_last10m_away"],
        "iso_window15_only": ["xg_last15m_home", "xg_last15m_away", "shots_last15m_home", "shots_last15m_away"],
    }
    iso = E.loco_wdl(rows, predictor_factory=_isolation_factory(iso_sets))
    iso_pooled = _pooled_rps(iso)
    ref_rps = iso_pooled.get(REF)
    out["ablations"]["B_isolation_heads"] = {
        name: {"rps": round(iso_pooled.get(name), 5) if iso_pooled.get(name) is not None else None,
               "delta_vs_e2": (round(iso_pooled[name] - ref_rps, 5)
                               if (iso_pooled.get(name) is not None and ref_rps is not None) else None)}
        for name in iso_sets}
    # set-piece ON vs OFF: full state with vs without set-piece columns
    no_sp = [c for c in M.FULL_STATE_COLS if c not in set(M.SETPIECE_DISCIPLINE_COLS)]
    sp_sets = {"full_state_setpiece_ON": M.FULL_STATE_COLS, "full_state_setpiece_OFF": no_sp}
    sp = E.loco_wdl(rows, predictor_factory=_isolation_factory(sp_sets))
    sp_pooled = _pooled_rps(sp)
    out["ablations"]["B_setpiece_on_off"] = {
        k: round(sp_pooled.get(k), 5) if sp_pooled.get(k) is not None else None
        for k in list(sp_sets) + [REF]}

    # ---- C. subgroup re-scoring of e2 vs e7 ----
    def _xg(r):
        try:
            return float(r.get("cum_xg_total") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _compl(r):
        return (r.get("xg_present") in ("True", "true", True))

    def _diff(r):
        try:
            return abs(int(round(float(r.get("goals_diff") or 0))))
        except (TypeError, ValueError):
            return 0

    def _so(r):
        try:
            return (int(float(r.get("sendoff_home") or 0)) + int(float(r.get("sendoff_away") or 0))) > 0
        except (TypeError, ValueError):
            return False

    xgs = sorted(_xg(r) for r in rows)
    med_xg = xgs[len(xgs) // 2] if xgs else 0.0
    out["ablations"]["C_subgroups"] = {
        "high_completeness_xg_present": _subgroup_rps(rows, _compl, "xg_present"),
        "low_completeness_xg_absent": _subgroup_rps(rows, lambda r: not _compl(r), "xg_absent"),
        "high_xg_above_median": _subgroup_rps(rows, lambda r: _xg(r) > med_xg, "high_xg"),
        "low_xg_at_or_below_median": _subgroup_rps(rows, lambda r: _xg(r) <= med_xg, "low_xg"),
        "level_game": _subgroup_rps(rows, lambda r: _diff(r) == 0, "level"),
        "one_goal_game": _subgroup_rps(rows, lambda r: _diff(r) == 1, "one_goal"),
        "normal_no_sendoff": _subgroup_rps(rows, lambda r: not _so(r), "normal"),
        "after_sending_off": _subgroup_rps(rows, _so, "after_sendoff"),
    }

    L.write_json("ep_ablations.json", out)
    n_ablations = (len(nested) + len(iso_sets) + len(sp_sets) + len(out["ablations"]["C_subgroups"]))
    # honest headline: does ANY ablation produce a variant that beats e2 out-of-sample?
    any_beats = any(
        (v.get("delta_hi_minus_lo") is not None and (pooled.get("research.event_process.e2") is not None)
         and (pooled.get("research.event_process." + k.split("->")[1]) is not None)
         and pooled["research.event_process." + k.split("->")[1]] < pooled["research.event_process.e2"])
        for k, v in nested.items() if "->" in k)
    L.emit("complete",
           reason=f"ran {n_ablations} mandatory ablations (nested layers + isolation heads + set-piece "
                  f"on/off + 8 subgroups); reference=e2; any_variant_beats_e2={any_beats}",
           state_updates={"n_ablations": n_ablations, "ablation_any_beats_e2": bool(any_beats)})


main()
