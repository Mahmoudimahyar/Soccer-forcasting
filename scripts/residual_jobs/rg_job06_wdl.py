"""RG_JOB06 -- residual W/D/L family R0-R6 (leave-one-competition-out; pooled fit-quality pass).

Builds the residual WDL family as TRAIN-fit predict_one callables via the canonical package factory and
scores every model OUT-OF-SAMPLE under LOCO (RPS / logloss / draw-Brier). r0 (W2 reference) is the anchor
every candidate must beat OUT-OF-SAMPLE or fall back to. This job is the LOCO pass; JOB07 is the primary
forward-chain pass and JOB08 the secondary LOCO-with-bootstrap pass -- here we establish the family is
fittable on real folds and emit per-model pooled metrics + per-match RPS series (consumed downstream).

  r0 w2_reference_r0 (anchor) | r1 intensity_glm_r1 | r2 competing_risk_r2 (honest skip if no builder) |
  r3 event_process_boost_r3 | r4 selective_correction_r4 (alpha=0 fallback permitted) |
  r5 calibrated_simulation_r5 | r6 club_auxiliary_transfer_r6 (club rows NEVER test rows)

research_only / experimental. No network/API. Honest data_insufficient if the panel is absent.
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

    rows = list(bundle["rows"])
    club = _rg.load_club_rows()

    # pooled accumulators + per-match RPS series (per model) for the downstream bootstrap
    pooled = {}
    per_match_rps = {}
    n_folds = 0
    all_model_ids = set()
    for held, train, test in DS.loco_folds(rows):
        n_folds += 1
        try:
            preds = RI.residual_predictors(train, club_rows=club if club else None)
        except Exception as e:
            # a fold that cannot fit the family is recorded, not silently dropped
            per_match_rps.setdefault("_fold_errors", []).append({"competition": held, "error": repr(e)})
            continue
        # group test rows by match for match-level RPS
        for mid, fn in preds.items():
            all_model_ids.add(mid)
            agg = pooled.setdefault(mid, {"rps": 0.0, "ll": 0.0, "bd": 0.0, "n": 0})
            by_match = {}
            for r in test:
                y = r.get("target_wdl")
                if y not in WDL:
                    continue
                p = fn(r)
                agg["rps"] += _rg.rps_wdl(p, y)
                agg["ll"] += _rg.logloss_wdl(p, y)
                agg["bd"] += _rg.brier_draw(p, y)
                agg["n"] += 1
                m = r.get("source_match_id") or r.get("match_id")
                d = by_match.setdefault(m, {"rps": 0.0, "n": 0})
                d["rps"] += _rg.rps_wdl(p, y); d["n"] += 1
            for m, d in by_match.items():
                if d["n"]:
                    per_match_rps.setdefault(mid, []).append(d["rps"] / d["n"])

    pooled_out = {}
    for mid, a in pooled.items():
        pooled_out[mid] = ({"rps": round(a["rps"] / a["n"], 5), "logloss": round(a["ll"] / a["n"], 5),
                            "draw_brier": round(a["bd"] / a["n"], 5), "n_test_rows": a["n"]}
                           if a["n"] else None)

    ref_rps = (pooled_out.get(REF) or {}).get("rps")
    beats = {m: (pooled_out.get(m) is not None and ref_rps is not None and pooled_out[m]["rps"] < ref_rps)
             for m in pooled_out if m != REF}
    any_beats = any(beats.values())

    _rg.write_json("rg_wdl_loco.json", {
        "protocol": "loco_wdl", "reference": REF, "n_folds": n_folds,
        "pooled": pooled_out, "beats_reference": beats,
        "per_match_rps": {k: v for k, v in per_match_rps.items() if not k.startswith("_")},
        "fold_errors": per_match_rps.get("_fold_errors", []),
        "club_transfer_active": bool(club),
        "n_rows": len(rows), "n_matches": bundle["n_matches"], "n_competitions": bundle["n_competitions"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })
    best = min(((m, v["rps"]) for m, v in pooled_out.items() if v), key=lambda kv: kv[1], default=(None, None))
    _rg.emit("complete",
             reason=f"residual WDL LOCO folds={n_folds}; models={sorted(all_model_ids)}; "
                    f"ref(r0)_rps={ref_rps}; best={best[0]}({best[1]}); any_beats_ref={any_beats}",
             state_updates={"wdl_loco_folds": n_folds, "wdl_ref_rps": ref_rps,
                            "wdl_any_beats_ref": any_beats, "residual_model_ids": sorted(all_model_ids)})


main()
