"""HT_JOB08 -- secondary leave-one-competition-out (LOCO) evaluation.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: a secondary robustness check. Hold out one INTERNATIONAL competition (e.g. "FIFA World Cup
2022") at a time; train the ladder on the OTHER international competitions' rows (+ club-aux training rows
when present), respecting the no-2026 guard; score the held-out competition's rows vs T0. This complements
the temporal forward chain (JOB07) by testing generalisation ACROSS competitions rather than forward in
time. CLUB rows are training-only and never a test row.

Honest data_insufficient if the dataset is absent or fewer than two international competitions exist.
"""
from __future__ import annotations

import _ht as H

JOB = "JOB8"


def main():
    art = H.envelope(JOB, "running")
    if not H.dataset_present():
        art["status"] = "data_insufficient"
        H.write_json("job08_loco.json", art)
        return H.emit("data_insufficient", "transfer dataset absent -- cannot run LOCO")

    from wcdrawlab.research.transfer import hierarchical_models as HM
    C = H.common()

    rows = H.load_dataset_rows()
    feat_cols = H.discover_feat_cols(rows)
    # build the international primary population (training rows union of test rows == all intl rows),
    # de-duplicated to one row-set keyed by (competition, match, minute). Club rows kept separately.
    intl = [r for r in rows if (r.get("domain") or "international") == "international"]
    club = [r for r in rows if (r.get("domain") or "international") == "club"]
    # de-dup intl rows across folds (the same intl match appears as train in some folds, test in others)
    seen = set()
    intl_uniq = []
    for r in intl:
        key = (r.get("competition_label"), r.get("match_id"), r.get("snapshot_minute"),
               r.get("row_role"))
        # prefer a single physical snapshot: key on (comp, match, minute) only
        k2 = (r.get("competition_label"), r.get("match_id"), r.get("snapshot_minute"))
        if k2 in seen:
            continue
        seen.add(k2)
        intl_uniq.append(r)

    comps = sorted({r.get("competition_label") for r in intl_uniq if r.get("competition_label")})
    if len(comps) < 2:
        art["status"] = "data_insufficient"
        art["n_competitions"] = len(comps)
        H.write_json("job08_loco.json", art)
        return H.emit("data_insufficient", f"need >=2 international competitions for LOCO (have {len(comps)})")

    model_ids = list(H.transfer_ids().TRANSFER_MODELS)[1:]
    per_comp = {}
    pooled = {mid: {"pm": [], "pm0": [], "n": 0, "rps_w": 0.0, "rps_w_t0": 0.0} for mid in model_ids}

    for held in comps:
        train_intl = [r for r in intl_uniq if r.get("competition_label") != held]
        test_intl = [r for r in intl_uniq if r.get("competition_label") == held]
        if H.assert_no_2026_rows(test_intl) > 0 or H.assert_no_2026_rows(train_intl) > 0:
            per_comp[held] = {"status": "skipped", "reason": "2026 row present (forbidden)"}
            continue
        if not train_intl or not test_intl:
            per_comp[held] = {"status": "skipped", "reason": "empty train/test"}
            continue
        overlap = H._fnum(train_intl[0].get("domain_overlap_score"))
        overlap = overlap if overlap is not None else 1.0
        ladder = HM.fit_ladder(train_intl, club, feat_cols, overlap_score=overlap, alpha=1.0)
        comp_scores = {}
        for mid in model_ids:
            md = {"model_id": ladder[mid].model_id, "coef": ladder[mid].coef,
                  "intercept": ladder[mid].intercept, "feature_names": ladder[mid].feature_names,
                  "domain_intercepts": ladder[mid].domain_intercepts, "alpha": ladder[mid].alpha,
                  "n_train": ladder[mid].n_train, "calibration": ladder[mid].calibration,
                  "train_means": (ladder[mid].notes or {}).get("train_means")}
            s = H.score_model_on_rows(md, test_intl, feat_cols, mid)
            if s.get("n", 0) == 0:
                continue
            comp_scores[mid] = {k: s[k] for k in ("n", "n_matches", "rps", "rps_t0",
                                                  "rps_delta_vs_t0", "logloss3", "draw_brier")}
            p = pooled[mid]
            p["pm"] += s["per_match_rps"]; p["pm0"] += s["per_match_rps_t0"]; p["n"] += s["n"]
            p["rps_w"] += s["rps"] * s["n"]; p["rps_w_t0"] += s["rps_t0"] * s["n"]
        per_comp[held] = {"status": "scored", "n_train": len(train_intl), "n_test": len(test_intl),
                          "gate": {"passed": ladder["_gate"].passed, "reason": ladder["_gate"].reason},
                          "scores": comp_scores}

    pooled_out = {}
    for mid in model_ids:
        p = pooled[mid]
        if p["n"] == 0:
            pooled_out[mid] = {"status": "no_scored_rows"}
            continue
        deltas = [a - b for a, b in zip(p["pm"], p["pm0"])]
        lo, hi = C.match_bootstrap_ci(deltas, n=1000)
        rps = p["rps_w"] / p["n"]; rps_t0 = p["rps_w_t0"] / p["n"]
        pooled_out[mid] = {"n": p["n"], "n_matches": len(p["pm"]), "rps": round(rps, 6),
                           "rps_t0": round(rps_t0, 6), "rps_delta_vs_t0": round(rps - rps_t0, 6),
                           "rps_delta_ci95": [lo, hi], "beats_t0_on_rps": rps < rps_t0,
                           "ci_excludes_zero": (lo is not None and hi is not None and (hi < 0 or lo > 0))}

    art.update({"loco_population": "international_only", "competitions": comps,
                "per_competition": per_comp, "pooled": pooled_out})
    art["status"] = "complete"
    H.write_json("job08_loco.json", art)
    H.emit("complete", f"LOCO eval complete across {len(comps)} competitions",
           state_updates={"loco_ok": True, "n_competitions": len(comps)})


if __name__ == "__main__":
    main()
