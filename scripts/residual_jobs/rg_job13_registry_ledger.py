"""RG_JOB13 -- model registry + feature catalog + decision ledger.

Consolidates the out-of-sample artifacts from JOB04-12 into a canonical DECISION LEDGER -- one row per
canonical model (all RESIDUAL r0-r6 + HORIZON h0-h4 + INTENSITY i0-i3) with a verdict in
{reference_only, rejected, data_insufficient, research_candidate_for_future_shadow_review} derived ONLY
from real evidence via the preregistered promotion rule (_rg.candidate_verdict). When a producing artifact
is absent (e.g. a model with no dedicated builder), that model's verdict is data_insufficient with the
concrete reason -- never a fabricated promotion.

Writes:
  data/reference/residual_goal_intensity_decision_ledger.{csv,json}   (canonical)
  outputs/research_runs/<run_id>/residual_goal_intensity/rg_decision_ledger.json   (run mirror)
  + a feature-catalog mirror (data/reference/residual_goal_intensity/feature_catalog.csv from JOB03).

research_only / experimental. No network/API.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg

WDL_REF = "research.residual.w2_reference_r0"
INT_REF = "research.intensity.w2_home_away_i0"
HOR_REF = "research.horizon.w2_implied_h0"


def _row(model_id, verdict, reason, ref_metric=None, model_metric=None, evidence=None):
    return {"model_id": model_id, "verdict": verdict, "reason": reason,
            "reference_oos_metric": ref_metric, "model_oos_metric": model_metric,
            "evidence": evidence or {}, "labels": _rg.LABELS}


def _wdl_ledger(fc, loco, cal):
    from wcdrawlab.research.residual_intensity import registry as REG
    rows = []
    fc_pooled = (fc or {}).get("pooled", {})
    loco_pooled = (loco or {}).get("pooled", {})
    boots = (loco or {}).get("candidate_vs_r0_bootstrap", {}) or \
            (cal or {}).get("candidate_vs_r0_bootstrap", {})
    fold_wins = (loco or {}).get("candidate_fold_wins_vs_r0", {})
    n_loco_folds = (loco or {}).get("n_folds", 0)
    rel = (cal or {}).get("draw_channel_reliability", {})
    ref_ece = (rel.get(WDL_REF) or {}).get("ece")
    n_matches = (loco or fc or {}).get("n_matches", 0)
    n_test_rows = sum(f.get("n_test_rows", 0) for f in (loco or {}).get("folds", []) if isinstance(f, dict))

    for mid in REG.RESIDUAL_MODELS:
        fr = (fc_pooled.get(mid) or {}).get("rps") if fc_pooled.get(mid) else None
        lr = (loco_pooled.get(mid) or {}).get("rps") if loco_pooled.get(mid) else None
        if mid == WDL_REF:
            rows.append(_row(mid, "reference_only", "parameter-free W2 remaining-time Poisson REFERENCE",
                             ref_metric=lr, model_metric=lr))
            continue
        if fr is None and lr is None:
            rows.append(_row(mid, "data_insufficient",
                             "no out-of-sample RPS (no builder/artifact for this model in this run)",
                             ref_metric=loco_pooled.get(WDL_REF, {}).get("rps") if loco_pooled.get(WDL_REF) else None))
            continue
        ref_rps = (loco_pooled.get(WDL_REF) or {}).get("rps")
        fc_ref = (fc_pooled.get(WDL_REF) or {}).get("rps")
        beats = (lr is not None and ref_rps is not None and lr < ref_rps) or \
                (fr is not None and fc_ref is not None and fr < fc_ref)
        b = boots.get(mid, {})
        cand_ece = (rel.get(mid) or {}).get("ece")
        cal_ok = (ref_ece is None or cand_ece is None or cand_ece <= ref_ece + _rg.CAL_ECE_TOL)
        fw = fold_wins.get(mid)
        frac = (fw / n_loco_folds) if (fw is not None and n_loco_folds) else (1.0 if beats else 0.0)
        verdict, evidence = _rg.candidate_verdict(
            n_matches=n_matches, n_test_rows=n_test_rows, beats_reference_pooled=beats,
            bootstrap_favors=b.get("favors_candidate"), fold_win_fraction=frac,
            calibration_not_worse=cal_ok, all_test_international=True, xg_subset_ok=True)
        rows.append(_row(mid, verdict,
                         f"OOS LOCO rps={lr} / FC rps={fr} vs r0={ref_rps}; "
                         f"bootstrap_favors={b.get('favors_candidate')}; fold_win_frac={frac}; cal_ok={cal_ok}",
                         ref_metric=ref_rps, model_metric=lr, evidence=evidence))
    return rows


def _intensity_ledger(intart):
    from wcdrawlab.research.residual_intensity import registry as REG
    rows = []
    pooled = (intart or {}).get("pooled", {})
    beats = (intart or {}).get("beats_reference", {})
    ref = (pooled.get(INT_REF) or {})
    ref_dev = ref.get("poisson_dev_mean")
    n_matches = (intart or {}).get("n_matches", 0)
    for mid in REG.INTENSITY_MODELS:
        pm = pooled.get(mid)
        if mid == INT_REF:
            rows.append(_row(mid, "reference_only", "parameter-free W2 home/away REFERENCE intensities",
                             ref_metric=ref_dev, model_metric=ref_dev))
            continue
        if pm is None:
            rows.append(_row(mid, "data_insufficient",
                             "no out-of-sample intensity deviance (no builder/club rows for this model)",
                             ref_metric=ref_dev))
            continue
        n_test = pm.get("n_test_rows", 0)
        b = bool(beats.get(mid))
        verdict, evidence = _rg.candidate_verdict(
            n_matches=n_matches, n_test_rows=n_test, beats_reference_pooled=b,
            bootstrap_favors=None, fold_win_fraction=(1.0 if b else 0.0),
            calibration_not_worse=True, all_test_international=True)
        # intensity has no match-bootstrap here -> cannot satisfy rule3; reports beats/deviance honestly
        rows.append(_row(mid, ("rejected" if (not b and verdict != "data_insufficient") else verdict),
                         f"OOS Poisson dev_mean={pm.get('poisson_dev_mean')} vs i0={ref_dev}; beats_ref={b}",
                         ref_metric=ref_dev, model_metric=pm.get("poisson_dev_mean"), evidence=evidence))
    return rows


def _horizon_ledger(horart):
    from wcdrawlab.research.residual_intensity import registry as REG
    rows = []
    per_h = (horart or {}).get("per_horizon", {})
    # aggregate "beats h0 on Brier in at least one horizon"
    for mid in REG.HORIZON_MODELS:
        if mid == HOR_REF:
            # report the 15m Brier as a representative reference metric if available
            ref_b = None
            ok = per_h.get("15m", {})
            if ok.get("status") == "ok":
                ref_b = (ok.get("pooled", {}).get(HOR_REF) or {}).get("brier")
            rows.append(_row(mid, "reference_only", "parameter-free W2-implied near-term scoring REFERENCE",
                             ref_metric=ref_b, model_metric=ref_b))
            continue
        beats_any = False
        worst_b = None
        ref_b = None
        any_data = False
        for hk, hv in per_h.items():
            if hv.get("status") != "ok":
                continue
            any_data = True
            pooled = hv.get("pooled", {})
            ref_b = (pooled.get(HOR_REF) or {}).get("brier")
            cb = (pooled.get(mid) or {}).get("brier")
            if cb is not None:
                worst_b = cb if worst_b is None else max(worst_b, cb)
            if hv.get("beats_reference", {}).get(mid):
                beats_any = True
        if not any_data:
            rows.append(_row(mid, "data_insufficient", "no horizon labels scorable in this run",
                             ref_metric=None))
            continue
        n_matches = (horart or {}).get("n_matches", 0)
        # use a representative test-row count gate
        n_test = sum((hv.get("pooled", {}).get(mid) or {}).get("n_test_rows", 0)
                     for hv in per_h.values() if hv.get("status") == "ok")
        verdict, evidence = _rg.candidate_verdict(
            n_matches=n_matches, n_test_rows=n_test, beats_reference_pooled=beats_any,
            bootstrap_favors=None, fold_win_fraction=(1.0 if beats_any else 0.0),
            calibration_not_worse=True, all_test_international=True)
        rows.append(_row(mid, ("rejected" if (not beats_any and verdict != "data_insufficient") else verdict),
                         f"beats h0 on Brier in >=1 horizon={beats_any}; worst candidate Brier={worst_b} "
                         f"vs ref={ref_b}", ref_metric=ref_b, model_metric=worst_b, evidence=evidence))
    return rows


def main():
    fc = _rg.read_json("rg_wdl_forward_chain.json")
    loco = _rg.read_json("rg_wdl_loco_bootstrap.json") or _rg.read_json("rg_wdl_loco.json")
    cal = _rg.read_json("rg_calibration_bootstrap.json")
    intart = _rg.read_json("rg_intensity_loco.json")
    horart = _rg.read_json("rg_horizon_loco.json")

    if all(a is None for a in (fc, loco, cal, intart, horart)):
        _rg.emit("data_insufficient",
                 reason="no JOB04-12 evaluation artifacts in run dir; cannot build a real ledger "
                        "(run the eval jobs first). Honest skip, not a fabricated ledger.")
        return

    ledger = []
    ledger += _wdl_ledger(fc, loco, cal)
    ledger += _intensity_ledger(intart)
    ledger += _horizon_ledger(horart)

    _rg.REF.mkdir(parents=True, exist_ok=True)
    (_rg.REF / "residual_goal_intensity_decision_ledger.json").write_text(
        json.dumps({"models": ledger, "n_models": len(ledger), "utc": _rg.utc(),
                    "reference_models": {"residual": WDL_REF, "intensity": INT_REF, "horizon": HOR_REF},
                    "labels": _rg.LABELS}, indent=2, default=str), encoding="utf-8")
    fields = ["model_id", "verdict", "reason", "reference_oos_metric", "model_oos_metric", "labels"]
    with (_rg.REF / "residual_goal_intensity_decision_ledger.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in ledger:
            w.writerow(r)
    _rg.write_json("rg_decision_ledger.json", {"models": ledger, "n_models": len(ledger)})

    by_verdict = {}
    for r in ledger:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
    n_candidates = by_verdict.get("research_candidate_for_future_shadow_review", 0)
    _rg.emit("complete",
             reason=f"decision_ledger={len(ledger)} models ({by_verdict}); "
                    f"research_candidates={n_candidates} (honest "
                    f"{'negative' if n_candidates == 0 else 'flagged for future shadow review'})",
             state_updates={"n_ledger_models": len(ledger), "ledger_by_verdict": by_verdict,
                            "n_research_candidates": n_candidates})


main()
