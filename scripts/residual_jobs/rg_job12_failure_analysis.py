"""RG_JOB12 -- failure analysis: WHERE the residual correction helps or hurts vs the W2 reference.

Under LOCO, scores the best available correction (selective_correction_r4, which already falls back to r0
where correction is not earned) and the pure r0 reference, then decomposes the per-row RPS DELTA
(r4 - r0; negative = correction helped) across interpretable strata:
  * regime (game-state x evidence-tier)         * game-state          * evidence-tier
  * minute bucket (0-30 / 30-60 / 60-90)         * xG availability (present / absent)
  * current-score state (level / narrow / 2+)

Surfaces the strata where the event-process correction most helps and most hurts -- the honest map of
where (if anywhere) in-play state adds value over a parameter-free clock model, and where it is noise.

research_only / experimental. No network/API. Honest data_insufficient if the panel is absent.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg

WDL = ["H", "D", "A"]


def _minute_bucket(r):
    try:
        m = float(r.get("snapshot_minute"))
    except Exception:
        return "unknown"
    if m < 30:
        return "00-30"
    if m < 60:
        return "30-60"
    return "60-90"


def _score_state(r):
    try:
        d = abs(int(round(float(r.get("goals_diff", 0)))))
    except Exception:
        return "unknown"
    return "level" if d == 0 else ("narrow_1" if d == 1 else "two_plus")


def _xg_avail(r):
    v = str(r.get("xg_present")).strip().lower()
    return "xg_present" if v == "true" else "xg_absent"


def _accumulate(strata, key, delta):
    d = strata.setdefault(key, {"sum_delta": 0.0, "n": 0, "n_helped": 0})
    d["sum_delta"] += delta
    d["n"] += 1
    if delta < 0:
        d["n_helped"] += 1


def _finalize(strata):
    out = {}
    for k, d in strata.items():
        if d["n"]:
            out[k] = {"mean_delta_r4_minus_r0": round(d["sum_delta"] / d["n"], 5), "n": d["n"],
                      "frac_rows_correction_helped": round(d["n_helped"] / d["n"], 4)}
    return out


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

    rows = list(bundle["rows"])

    by_regime, by_state, by_tier, by_minute, by_score, by_xg = {}, {}, {}, {}, {}, {}
    n_scored = 0
    sum_delta = 0.0
    n_folds = 0
    for held, train, test in DS.loco_folds(rows):
        n_folds += 1
        try:
            sc = RI.build_selective_correction_r4(train)
        except Exception:
            continue
        for r in test:
            y = r.get("target_wdl")
            if y not in WDL:
                continue
            p_r4 = sc.predict_one(r)
            p_r0 = RI.w2_reference_r0(r)
            delta = _rg.rps_wdl(p_r4, y) - _rg.rps_wdl(p_r0, y)
            sum_delta += delta
            n_scored += 1
            _accumulate(by_regime, r.get("ri_regime", "unknown"), delta)
            _accumulate(by_state, r.get("ri_game_state", r.get("ri_regime", "unknown").split("|")[0]), delta)
            _accumulate(by_tier, r.get("ri_evidence_tier",
                        (r.get("ri_regime", "unknown").split("|")[-1])), delta)
            _accumulate(by_minute, _minute_bucket(r), delta)
            _accumulate(by_score, _score_state(r), delta)
            _accumulate(by_xg, _xg_avail(r), delta)

    regime_final = _finalize(by_regime)
    # rank strata by where correction hurts most / helps most
    ranked = sorted(((k, v["mean_delta_r4_minus_r0"]) for k, v in regime_final.items()),
                    key=lambda kv: kv[1])
    helps_most = ranked[:3]
    hurts_most = list(reversed(ranked[-3:]))

    _rg.write_json("rg_failure_analysis.json", {
        "model_compared": "research.residual.selective_correction_r4 vs research.residual.w2_reference_r0",
        "metric": "per-row RPS delta (r4 - r0); negative = correction helped",
        "overall_mean_delta": round(sum_delta / n_scored, 5) if n_scored else None,
        "n_scored": n_scored, "n_folds": n_folds,
        "by_regime": regime_final, "by_game_state": _finalize(by_state),
        "by_evidence_tier": _finalize(by_tier), "by_minute_bucket": _finalize(by_minute),
        "by_score_state": _finalize(by_score), "by_xg_availability": _finalize(by_xg),
        "regime_helps_most": helps_most, "regime_hurts_most": hurts_most,
        "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })
    _rg.emit("complete",
             reason=f"failure analysis: n_scored={n_scored}; overall mean delta(r4-r0)="
                    f"{round(sum_delta / n_scored, 5) if n_scored else None}; "
                    f"helps_most={helps_most}; hurts_most={hurts_most}",
             state_updates={"fa_overall_mean_delta": round(sum_delta / n_scored, 5) if n_scored else None,
                            "fa_n_scored": n_scored})


main()
