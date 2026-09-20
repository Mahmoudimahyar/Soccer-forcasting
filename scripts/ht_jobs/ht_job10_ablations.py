"""HT_JOB10 -- mandatory ABLATIONS + club-family removal.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: re-fit + re-score the transfer ladder on the held-out international test rows under controlled
ablations, each vs the SAME T0 reference, on the forward-chain folds:
  * A0  full stable-feature subset (the reference configuration)
  * A1  xG-family removed (drop feat_cum_xg* / feat_xg_* -- tests whether xG carried the signal)
  * A2  chance-quality + shot family removed (shots / shots_on_target / box_entries / final_third)
  * A3  possession/territory family removed (poss_share / field_tilt / recoveries / turnovers / corners)
  * A4  state-only (NO stable features at all -> pure score/time design; isolates feature contribution)
  * A5  CLUB-FAMILY REMOVAL: drop all club-aux training rows and re-fit (the explicit transfer-removal
        control). When club rows are already absent locally this is a NO-OP and is recorded as such.

Each ablation reports pooled RPS vs T0. Honest data_insufficient if the dataset is absent.
"""
from __future__ import annotations

import _ht as H

JOB = "JOB10"

XG_FAM = ["feat_cum_xg_diff", "feat_cum_xg_total", "feat_xg_last5m_diff", "feat_xg_last10m_diff"]
SHOT_FAM = ["feat_shots_diff", "feat_shots_on_target_diff", "feat_box_entries_diff",
            "feat_final_third_actions_diff"]
POSS_FAM = ["feat_poss_share_diff", "feat_field_tilt_home", "feat_recoveries_diff",
            "feat_turnovers_diff", "feat_corners_diff"]


def _score_config(rows, all_feat, drop_feats, drop_club, label):
    from wcdrawlab.research.transfer import hierarchical_models as HM
    C = H.common()
    feat_cols = [c for c in all_feat if c not in set(drop_feats)]
    model_ids = list(H.transfer_ids().TRANSFER_MODELS)[1:]
    pooled = {mid: {"pm": [], "pm0": [], "n": 0, "rps_w": 0.0, "rps_w_t0": 0.0} for mid in model_ids}
    folds = H.fold_names(rows)
    n_club_used = 0
    for fold in folds:
        part = H.split_fold(rows, fold)
        intl_train, test_rows = part["intl_train"], part["intl_test"]
        club_train = [] if drop_club else part["club_train"]
        n_club_used += len(club_train)
        if not intl_train or not test_rows:
            continue
        overlap = H._fnum(intl_train[0].get("domain_overlap_score"))
        overlap = overlap if overlap is not None else 1.0
        ladder = HM.fit_ladder(intl_train, club_train, feat_cols, overlap_score=overlap, alpha=1.0)
        for mid in model_ids:
            md = {"model_id": ladder[mid].model_id, "coef": ladder[mid].coef,
                  "intercept": ladder[mid].intercept, "feature_names": ladder[mid].feature_names,
                  "domain_intercepts": ladder[mid].domain_intercepts, "alpha": ladder[mid].alpha,
                  "n_train": ladder[mid].n_train, "calibration": ladder[mid].calibration,
                  "train_means": (ladder[mid].notes or {}).get("train_means")}
            s = H.score_model_on_rows(md, test_rows, feat_cols, mid)
            if s.get("n", 0) == 0:
                continue
            p = pooled[mid]
            p["pm"] += s["per_match_rps"]; p["pm0"] += s["per_match_rps_t0"]; p["n"] += s["n"]
            p["rps_w"] += s["rps"] * s["n"]; p["rps_w_t0"] += s["rps_t0"] * s["n"]
    out = {"label": label, "n_features": len(feat_cols), "dropped": list(drop_feats),
           "club_removed": drop_club, "n_club_train_used": n_club_used, "models": {}}
    for mid in model_ids:
        p = pooled[mid]
        if p["n"] == 0:
            out["models"][mid] = {"status": "no_rows"}
            continue
        rps = p["rps_w"] / p["n"]; rps_t0 = p["rps_w_t0"] / p["n"]
        out["models"][mid] = {"n": p["n"], "rps": round(rps, 6), "rps_t0": round(rps_t0, 6),
                              "rps_delta_vs_t0": round(rps - rps_t0, 6), "beats_t0": rps < rps_t0}
    return out


def main():
    art = H.envelope(JOB, "running")
    if not H.dataset_present():
        art["status"] = "data_insufficient"
        H.write_json("job10_ablations.json", art)
        return H.emit("data_insufficient", "transfer dataset absent -- cannot run ablations")

    rows = H.load_dataset_rows()
    all_feat = H.discover_feat_cols(rows)
    n_club_total = sum(1 for r in rows if (r.get("domain") or "international") == "club")

    ablations = []
    ablations.append(_score_config(rows, all_feat, [], False, "A0_full"))
    ablations.append(_score_config(rows, all_feat, XG_FAM, False, "A1_no_xg"))
    ablations.append(_score_config(rows, all_feat, SHOT_FAM, False, "A2_no_shot_family"))
    ablations.append(_score_config(rows, all_feat, POSS_FAM, False, "A3_no_possession_family"))
    ablations.append(_score_config(rows, all_feat, all_feat, False, "A4_state_only"))
    ablations.append(_score_config(rows, all_feat, [], True,
                                   "A5_club_family_removed" + ("_noop" if n_club_total == 0 else "")))

    art.update({"n_club_rows_total": n_club_total,
                "club_removal_is_noop": n_club_total == 0,
                "reference_model": "research.transfer.w2_reference_t0",
                "ablations": ablations})
    art["status"] = "complete"
    H.write_json("job10_ablations.json", art)
    H.emit("complete",
           f"ran {len(ablations)} ablations (incl club-family removal "
           f"{'NO-OP: no club rows' if n_club_total == 0 else 'active'})",
           state_updates={"ablations_ok": True, "n_ablations": len(ablations)})


if __name__ == "__main__":
    main()
