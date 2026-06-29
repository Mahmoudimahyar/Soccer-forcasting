"""HT_JOB07 -- PRIMARY forward-chain international evaluation (T0..T7 vs T0 reference).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: the primary, leakage-safe evaluation. The outer temporal folds ARE the forward chain: each
held-out international tournament is scored by a ladder fitted STRICTLY BEFORE its first kickoff (JOB06).
Every model's W/D/L forecast on the held-out INTERNATIONAL TEST rows is scored against the T0 reference on
RPS / three-way log loss / draw-Brier, pooled across folds and per-fold. CLUB rows are never test rows.

The candidate comparison is ALWAYS vs T0 (never a weaker anchor). Honest data_insufficient if the fitted
store or dataset is absent.
"""
from __future__ import annotations

import _ht as H

JOB = "JOB7"


def main():
    art = H.envelope(JOB, "running")
    store = H.load_fitted_store()
    if store is None or not H.dataset_present():
        art["status"] = "data_insufficient"
        H.write_json("job07_forward_chain.json", art)
        return H.emit("data_insufficient", "fitted ladder store or dataset absent -- run JOB05/JOB06 first")

    rows = H.load_dataset_rows()
    feat_cols = store.get("feature_cols") or H.discover_feat_cols(rows)
    C = H.common()

    model_ids = list(H.transfer_ids().TRANSFER_MODELS)[1:]  # T1..T7 (T0 is the reference)
    per_fold = {}
    pooled = {mid: {"per_match_rps": [], "per_match_rps_t0": [], "n": 0,
                    "rps_w": 0.0, "ll_w": 0.0, "brier_w": 0.0,
                    "rps_w_t0": 0.0, "ll_w_t0": 0.0, "brier_w_t0": 0.0} for mid in model_ids}

    for fold, fstore in (store.get("folds") or {}).items():
        part = H.split_fold(rows, fold)
        test_rows = part["intl_test"]
        if not test_rows:
            per_fold[fold] = {"status": "no_test_rows"}
            continue
        fold_scores = {}
        for mid in model_ids:
            md = (fstore.get("models") or {}).get(mid)
            if md is None:
                continue
            s = H.score_model_on_rows(md, test_rows, feat_cols, mid)
            if s.get("n", 0) == 0:
                continue
            fold_scores[mid] = {k: s[k] for k in
                                ("n", "n_matches", "rps", "logloss3", "draw_brier",
                                 "rps_t0", "logloss3_t0", "draw_brier_t0",
                                 "rps_delta_vs_t0", "logloss3_delta_vs_t0")}
            p = pooled[mid]
            p["per_match_rps"] += s["per_match_rps"]; p["per_match_rps_t0"] += s["per_match_rps_t0"]
            p["n"] += s["n"]
            p["rps_w"] += s["rps"] * s["n"]; p["ll_w"] += s["logloss3"] * s["n"]
            p["brier_w"] += s["draw_brier"] * s["n"]
            p["rps_w_t0"] += s["rps_t0"] * s["n"]; p["ll_w_t0"] += s["logloss3_t0"] * s["n"]
            p["brier_w_t0"] += s["draw_brier_t0"] * s["n"]
        per_fold[fold] = {"status": "scored", "gate": fstore.get("gate"),
                          "n_test_rows": len(test_rows), "scores": fold_scores}

    # pooled metrics + match-level bootstrap CI of (model - T0) RPS
    pooled_out = {}
    best = None
    for mid in model_ids:
        p = pooled[mid]
        if p["n"] == 0:
            pooled_out[mid] = {"status": "no_scored_rows"}
            continue
        deltas = [a - b for a, b in zip(p["per_match_rps"], p["per_match_rps_t0"])]
        lo, hi = C.match_bootstrap_ci(deltas, n=1000)
        rps = p["rps_w"] / p["n"]; rps_t0 = p["rps_w_t0"] / p["n"]
        pooled_out[mid] = {
            "n": p["n"], "n_matches": len(p["per_match_rps"]),
            "rps": round(rps, 6), "logloss3": round(p["ll_w"] / p["n"], 6),
            "draw_brier": round(p["brier_w"] / p["n"], 6),
            "rps_t0": round(rps_t0, 6), "logloss3_t0": round(p["ll_w_t0"] / p["n"], 6),
            "rps_delta_vs_t0": round(rps - rps_t0, 6),
            "rps_delta_ci95": [lo, hi],
            "beats_t0_on_rps": rps < rps_t0,
            "ci_excludes_zero": (lo is not None and hi is not None and (hi < 0 or lo > 0)),
        }
        if pooled_out[mid].get("beats_t0_on_rps") and (best is None
                                                       or rps < pooled_out[best]["rps"]):
            best = mid

    art.update({"primary_population": "international_test_rows_only",
                "reference_model": "research.transfer.w2_reference_t0",
                "per_fold": per_fold, "pooled": pooled_out, "best_model_vs_t0": best,
                "n_folds_scored": sum(1 for v in per_fold.values() if v.get("status") == "scored")})
    art["status"] = "complete"
    H.write_json("job07_forward_chain.json", art)
    H.emit("complete",
           f"forward-chain eval complete; best_vs_t0={best}; "
           f"folds_scored={art['n_folds_scored']}",
           state_updates={"forward_chain_ok": True, "best_model_vs_t0": best})


if __name__ == "__main__":
    main()
