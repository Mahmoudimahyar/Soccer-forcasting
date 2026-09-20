"""HT_JOB11 -- CALIBRATION + match-bootstrap + RELIABILITY + domain-shift diagnostics.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work, on the held-out international test rows of the forward-chain folds (vs T0):
  * CALIBRATION: per-model draw-probability reliability (slope / intercept / ECE, 10 bins) using the
    shared harness calibration(), for T0 and the selective T6 + calibrated T7;
  * MATCH-LEVEL BOOTSTRAP (unit = match): 95% CI of each model's pooled RPS and of (model - T0) RPS;
  * RELIABILITY table: binned predicted-vs-observed draw rate for T0 and T6/T7;
  * DOMAIN-SHIFT diagnostics: re-state the single-domain vs cross-domain coverage (club rows absent ->
    the cross-domain shift statistics are honestly data_insufficient, not fabricated).

Honest data_insufficient if the fitted store/dataset is absent.
"""
from __future__ import annotations

import _ht as H

JOB = "JOB11"


def _reliability(pairs, bins=10):
    """pairs=[(p_draw, is_draw)]. Returns per-bin (mean_pred, obs_rate, n)."""
    out = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        sub = [(p, y) for (p, y) in pairs if (p >= lo and (p < hi or (i == bins - 1 and p <= hi)))]
        if sub:
            mp = sum(p for p, _ in sub) / len(sub)
            obs = sum(y for _, y in sub) / len(sub)
            out.append({"bin": [round(lo, 2), round(hi, 2)], "mean_pred": round(mp, 4),
                        "obs_rate": round(obs, 4), "n": len(sub)})
    return out


def main():
    art = H.envelope(JOB, "running")
    store = H.load_fitted_store()
    if store is None or not H.dataset_present():
        art["status"] = "data_insufficient"
        H.write_json("job11_calibration_bootstrap.json", art)
        return H.emit("data_insufficient", "fitted store or dataset absent -- run JOB05/JOB06 first")

    from wcdrawlab.research.transfer import hierarchical_models as HM
    C = H.common()
    rows = H.load_dataset_rows()
    feat_cols = store.get("feature_cols") or H.discover_feat_cols(rows)

    T = H.transfer_ids()
    focus_models = [T.T1_INTERNATIONAL_ONLY, T.T4_PARTIAL_POOLING, T.T6_SELECTIVE_TRANSFER,
                    T.T7_CALIBRATED_SIMULATION]

    # accumulate predicted-draw pairs + per-match RPS across folds
    draw_pairs = {mid: [] for mid in focus_models}
    draw_pairs_t0 = []
    pm = {mid: {"rps": [], "rps0": []} for mid in focus_models}

    for fold, fstore in (store.get("folds") or {}).items():
        part = H.split_fold(rows, fold)
        test_rows = part["intl_test"]
        if not test_rows:
            continue
        tgt = H.wdl_target(test_rows)
        mids_match = H.match_ids(test_rows)
        t0_probs = HM.reference_wdl_rows(test_rows)
        for p0, t in zip(t0_probs, tgt):
            if t in ("H", "D", "A"):
                draw_pairs_t0.append((p0["D"], 1.0 if t == "D" else 0.0))
        for mid in focus_models:
            md = (fstore.get("models") or {}).get(mid)
            if md is None:
                continue
            s = H.score_model_on_rows(md, test_rows, feat_cols, mid)
            if s.get("n", 0) == 0:
                continue
            pm[mid]["rps"] += s["per_match_rps"]; pm[mid]["rps0"] += s["per_match_rps_t0"]
            # reconstruct draw probs for reliability
            m = H._model_from_dict(md)
            X, _n, _t = HM.build_design(test_rows, feat_cols, train_means=md.get("train_means"))
            domains = [str(r.get("domain") or "international") for r in test_rows]
            if mid == T.T7_CALIBRATED_SIMULATION:
                probs = HM.mc_simulate_wdl(test_rows, m.predict_residual(X, domains))
            elif not m.coef:
                probs = HM.reference_wdl_rows(test_rows)
            else:
                probs = HM.predict_wdl_rows(test_rows, m.predict_residual(X, domains))
            for p, t in zip(probs, tgt):
                if t in ("H", "D", "A"):
                    draw_pairs[mid].append((p["D"], 1.0 if t == "D" else 0.0))

    calib = {"research.transfer.w2_reference_t0":
             {"calibration": C.calibration(draw_pairs_t0),
              "reliability": _reliability(draw_pairs_t0), "n": len(draw_pairs_t0)}}
    bootstrap = {}
    for mid in focus_models:
        if draw_pairs[mid]:
            calib[mid] = {"calibration": C.calibration(draw_pairs[mid]),
                          "reliability": _reliability(draw_pairs[mid]), "n": len(draw_pairs[mid])}
        if pm[mid]["rps"]:
            lo, hi = C.match_bootstrap_ci(pm[mid]["rps"], n=1000)
            deltas = [a - b for a, b in zip(pm[mid]["rps"], pm[mid]["rps0"])]
            dlo, dhi = C.match_bootstrap_ci(deltas, n=1000)
            mean_rps = sum(pm[mid]["rps"]) / len(pm[mid]["rps"])
            mean_rps0 = sum(pm[mid]["rps0"]) / len(pm[mid]["rps0"])
            bootstrap[mid] = {"n_matches": len(pm[mid]["rps"]),
                              "rps_mean": round(mean_rps, 6), "rps_ci95": [lo, hi],
                              "rps_t0_mean": round(mean_rps0, 6),
                              "rps_delta_vs_t0_mean": round(mean_rps - mean_rps0, 6),
                              "rps_delta_ci95": [dlo, dhi],
                              "delta_ci_excludes_zero": (dlo is not None and dhi is not None
                                                         and (dhi < 0 or dlo > 0))}

    n_club = sum(1 for r in rows if (r.get("domain") or "international") == "club")
    domain_shift = {
        "single_domain_train": n_club == 0,
        "n_club_rows": n_club,
        "cross_domain_shift_statistics": ("computed" if n_club > 0 else "data_insufficient"),
        "reason": (None if n_club > 0 else
                   "club event corpus not materialised locally -> SMD/variance-ratio/Wasserstein require "
                   "a real club distribution and are NOT fabricated"),
    }

    art.update({"calibration": calib, "match_bootstrap": bootstrap, "domain_shift": domain_shift,
                "reference_model": "research.transfer.w2_reference_t0"})
    art["status"] = "complete"
    H.write_json("job11_calibration_bootstrap.json", art)
    H.emit("complete",
           f"calibration + match-bootstrap + reliability done for {len(bootstrap)} focus models; "
           f"domain_shift={'single_domain' if n_club == 0 else 'cross_domain'}",
           state_updates={"calibration_bootstrap_ok": True})


if __name__ == "__main__":
    main()
