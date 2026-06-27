"""RG_JOB08 -- SECONDARY leave-one-competition-out W/D/L with per-fold wins + paired match bootstrap.

Complements the primary forward chain (JOB07). For each held-out competition we fit the residual family on
all other competitions and score the held one, accumulating: pooled RPS / logloss / draw-Brier, the count
of folds in which each candidate beats r0 (the W2 reference), per-match RPS series, and a MATCH-LEVEL
paired bootstrap of (candidate - r0) per-match RPS deltas (95% CI). A candidate is favored when the upper
bound of that CI is < 0. Match-level bootstrap only (no row-level resampling). Reuses the shared
match_bootstrap_ci from scripts/research_jobs/_common.py.

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
    C = _rg.metrics_mod()

    rows = list(bundle["rows"])
    club = _rg.load_club_rows()

    pooled = {}
    fold_wins = {}            # candidate -> folds where it beats r0 (pooled-in-fold RPS)
    n_loco_folds = 0
    # per-match paired deltas: model -> list of (cand_rps - r0_rps) averaged per match
    paired_match_delta = {}
    per_model_match_rps = {}
    folds = []
    for held, train, test in DS.loco_folds(rows):
        n_loco_folds += 1
        try:
            preds = RI.residual_predictors(train, club_rows=club if club else None)
        except Exception as e:
            folds.append({"competition": held, "error": repr(e)})
            continue
        # per-match accumulation for this fold
        match_rps = {}  # model -> {match: (sum_rps, n)}
        fold_pool = {}
        for mid, fn in preds.items():
            mr = match_rps.setdefault(mid, {})
            fp = fold_pool.setdefault(mid, {"rps": 0.0, "ll": 0.0, "bd": 0.0, "n": 0})
            for r in test:
                y = r.get("target_wdl")
                if y not in WDL:
                    continue
                p = fn(r)
                rp = _rg.rps_wdl(p, y)
                fp["rps"] += rp; fp["ll"] += _rg.logloss_wdl(p, y); fp["bd"] += _rg.brier_draw(p, y)
                fp["n"] += 1
                m = r.get("source_match_id") or r.get("match_id")
                d = mr.setdefault(m, [0.0, 0])
                d[0] += rp; d[1] += 1
        # fold pooled + wins
        ref_fold = fold_pool.get(REF)
        ref_rps_fold = (ref_fold["rps"] / ref_fold["n"]) if (ref_fold and ref_fold["n"]) else None
        fold_rec = {"competition": held, "n_test_rows": sum(1 for r in test if r.get("target_wdl") in WDL),
                    "models": {}}
        for mid, fp in fold_pool.items():
            if not fp["n"]:
                continue
            agg = pooled.setdefault(mid, {"rps": 0.0, "ll": 0.0, "bd": 0.0, "n": 0})
            agg["rps"] += fp["rps"]; agg["ll"] += fp["ll"]; agg["bd"] += fp["bd"]; agg["n"] += fp["n"]
            mrps = fp["rps"] / fp["n"]
            fold_rec["models"][mid] = round(mrps, 5)
            if mid != REF and ref_rps_fold is not None and mrps < ref_rps_fold:
                fold_wins[mid] = fold_wins.get(mid, 0) + 1
        folds.append(fold_rec)
        # per-match paired deltas vs r0 (only matches scored by both)
        ref_mr = match_rps.get(REF, {})
        for mid, mr in match_rps.items():
            per_model_match_rps.setdefault(mid, [])
            for m, (s, n) in mr.items():
                if n:
                    per_model_match_rps[mid].append(s / n)
            if mid == REF:
                continue
            for m, (s, n) in mr.items():
                if n and m in ref_mr and ref_mr[m][1]:
                    delta = (s / n) - (ref_mr[m][0] / ref_mr[m][1])
                    paired_match_delta.setdefault(mid, []).append(delta)

    pooled_out = {m: ({"rps": round(a["rps"] / a["n"], 5), "logloss": round(a["ll"] / a["n"], 5),
                       "draw_brier": round(a["bd"] / a["n"], 5), "n_test_rows": a["n"]} if a["n"] else None)
                  for m, a in pooled.items()}
    ref_rps = (pooled_out.get(REF) or {}).get("rps")

    # paired match-level bootstrap CI of the (candidate - r0) delta; favored when upper bound < 0
    boots = {}
    for mid, deltas in paired_match_delta.items():
        lo, hi = C.match_bootstrap_ci(deltas, n=1000)
        mean_d = round(sum(deltas) / len(deltas), 5) if deltas else None
        boots[mid] = {"mean_delta_vs_r0": mean_d, "ci95": [lo, hi],
                      "favors_candidate": (hi is not None and hi < 0), "n_matches": len(deltas)}

    _rg.write_json("rg_wdl_loco_bootstrap.json", {
        "protocol": "loco_wdl_paired_bootstrap", "reference": REF, "n_folds": n_loco_folds,
        "pooled": pooled_out, "candidate_fold_wins_vs_r0": fold_wins,
        "candidate_vs_r0_bootstrap": boots, "folds": folds,
        "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })
    favored = [m for m, b in boots.items() if b["favors_candidate"]]
    _rg.emit("complete",
             reason=f"LOCO folds={n_loco_folds}; ref(r0)_rps={ref_rps}; fold_wins={fold_wins}; "
                    f"bootstrap-favored_vs_r0={favored or 'none'}",
             state_updates={"loco_folds": n_loco_folds, "loco_ref_rps": ref_rps,
                            "loco_bootstrap_favored": favored})


main()
