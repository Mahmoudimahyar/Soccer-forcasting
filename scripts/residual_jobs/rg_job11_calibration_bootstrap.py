"""RG_JOB11 -- calibration + match-level bootstrap + reliability + intensity diagnostics (LOCO).

For every residual W/D/L model, under LOCO out-of-sample, this job computes:
  * RELIABILITY on the DRAW channel (predicted-vs-empirical draw rate, 10-bin ECE + logit slope/intercept)
    -- the draw channel is the hardest to calibrate and the candidate-promotion rule forbids degrading it;
  * a MATCH-LEVEL paired bootstrap of (candidate - r0) per-match RPS (95% CI; favored iff upper bound < 0);
  * INTENSITY diagnostics for the side-specific rates: pooled predicted vs observed remaining goals
    (home/away), so an intensity that is mis-scaled vs the W2 reference is visible.

Match-level bootstrap only (no row-level resampling). Reuses scripts/research_jobs/_common.py
(calibration, match_bootstrap_ci). research_only / experimental. No network/API.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg

REF = "research.residual.w2_reference_r0"
WDL = ["H", "D", "A"]


def main():
    try:
        bundle = _rg.load_rows()
    except Exception as e:
        from wcdrawlab.research.residual_intensity import datasets as DS
        if isinstance(e, DS.DataInsufficient):
            _rg.emit("data_insufficient", reason=f"panel unavailable: {e}")
            return
        _rg.emit("failed", reason=f"load error: {e!r}")
        return

    import wcdrawlab.research.residual_intensity as RI
    from wcdrawlab.research.residual_intensity import datasets as DS
    C = _rg.metrics_mod()

    rows = list(bundle["rows"])
    club = _rg.load_club_rows()

    # draw-channel reliability pairs + per-match RPS + intensity prediction accumulation
    draw_pairs = {}              # model -> [(p_draw, is_draw)]
    per_match_rps = {}           # model -> {match: [sum, n]}
    intensity_pred = {"obs_home": 0.0, "obs_away": 0.0, "pred_home_i1": 0.0, "pred_away_i1": 0.0,
                      "pred_home_w2": 0.0, "pred_away_w2": 0.0, "n": 0}
    n_folds = 0
    for held, train, test in DS.loco_folds(rows):
        n_folds += 1
        try:
            preds = RI.residual_predictors(train, club_rows=club if club else None)
        except Exception:
            continue
        i1_heads = RI.build_intensity_glm_r1(train)
        for mid, fn in preds.items():
            dp = draw_pairs.setdefault(mid, [])
            mr = per_match_rps.setdefault(mid, {})
            for r in test:
                y = r.get("target_wdl")
                if y not in WDL:
                    continue
                p = fn(r)
                dp.append((float(p.get("D", 0.0)), 1.0 if y == "D" else 0.0))
                m = r.get("source_match_id") or r.get("match_id")
                d = mr.setdefault(m, [0.0, 0])
                d[0] += _rg.rps_wdl(p, y); d[1] += 1
        # intensity diagnostics on labeled rows
        for r in test:
            if r.get("rem_goals_home") is None or r.get("rem_goals_away") is None:
                continue
            lh1, la1 = i1_heads._raw_intensities(r)
            lhw, law = RI.w2_intensities(r)
            intensity_pred["obs_home"] += float(r["rem_goals_home"])
            intensity_pred["obs_away"] += float(r["rem_goals_away"])
            intensity_pred["pred_home_i1"] += lh1; intensity_pred["pred_away_i1"] += la1
            intensity_pred["pred_home_w2"] += lhw; intensity_pred["pred_away_w2"] += law
            intensity_pred["n"] += 1

    # reliability (draw channel)
    reliability = {}
    for mid, pairs in draw_pairs.items():
        reliability[mid] = C.calibration(pairs)

    # paired bootstrap vs r0
    ref_mr = per_match_rps.get(REF, {})
    boots = {}
    for mid, mr in per_match_rps.items():
        if mid == REF:
            continue
        deltas = []
        for m, (s, n) in mr.items():
            if n and m in ref_mr and ref_mr[m][1]:
                deltas.append(s / n - ref_mr[m][0] / ref_mr[m][1])
        lo, hi = C.match_bootstrap_ci(deltas, n=1000)
        boots[mid] = {"mean_delta_vs_r0": round(sum(deltas) / len(deltas), 5) if deltas else None,
                      "ci95": [lo, hi], "favors_candidate": (hi is not None and hi < 0),
                      "n_matches": len(deltas)}

    n = intensity_pred["n"]
    intensity_diag = None
    if n:
        intensity_diag = {
            "n_labeled_test_rows": n,
            "mean_observed_remaining_home": round(intensity_pred["obs_home"] / n, 4),
            "mean_observed_remaining_away": round(intensity_pred["obs_away"] / n, 4),
            "mean_pred_i1_home": round(intensity_pred["pred_home_i1"] / n, 4),
            "mean_pred_i1_away": round(intensity_pred["pred_away_i1"] / n, 4),
            "mean_pred_w2_home": round(intensity_pred["pred_home_w2"] / n, 4),
            "mean_pred_w2_away": round(intensity_pred["pred_away_w2"] / n, 4),
        }

    ref_ece = (reliability.get(REF) or {}).get("ece")
    _rg.write_json("rg_calibration_bootstrap.json", {
        "protocol": "loco_calibration_bootstrap", "reference": REF, "n_folds": n_folds,
        "draw_channel_reliability": reliability, "reference_draw_ece": ref_ece,
        "candidate_vs_r0_bootstrap": boots,
        "intensity_diagnostics": intensity_diag,
        "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })
    favored = [m for m, b in boots.items() if b["favors_candidate"]]
    _rg.emit("complete",
             reason=f"calibration+bootstrap LOCO folds={n_folds}; ref(r0)_draw_ECE={ref_ece}; "
                    f"bootstrap-favored_vs_r0={favored or 'none'}; "
                    f"intensity_diag={'yes' if intensity_diag else 'no_labels'}",
             state_updates={"cal_ref_draw_ece": ref_ece, "cal_bootstrap_favored": favored,
                            "cal_folds": n_folds})


main()
