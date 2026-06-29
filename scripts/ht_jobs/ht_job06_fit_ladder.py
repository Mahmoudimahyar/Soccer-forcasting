"""HT_JOB06 -- fit the T0..T7 transfer LADDER (TRAIN rows only).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: for each OUTER TEMPORAL FOLD (held-out international tournament), fit the whole ladder on that
fold's TRAINING rows ONLY (intl-train [+ club-aux-train when present]):
  * T0  reference (parameter-free; no fit)
  * T1  international-only ridge Poisson residual
  * T2  naive pooled ridge residual (no domain correction)  [negative control]
  * T3  shared-coefficient ridge on the stable-feature subset
  * T4  hierarchical partial-pooling GLM (shared slope + per-domain intercept)
  * T5  domain-overlap weighted ridge residual
  * T6  selective (gated) transfer (T4 if gate passes, else T1)
  * T7  calibrated MC simulation of the selected model

The held-out test rows are NEVER passed to a fitter (only their match-ids are recorded). Fitted
coefficients + the per-fold selective gate decision are persisted to the run dir for the eval jobs.
Honest data_insufficient if the dataset is absent.
"""
from __future__ import annotations

import json

import _ht as H

JOB = "JOB6"


def _serialize(m) -> dict:
    return {"model_id": m.model_id, "coef": m.coef, "intercept": m.intercept,
            "feature_names": m.feature_names, "domain_intercepts": m.domain_intercepts,
            "alpha": m.alpha, "n_train": m.n_train, "calibration": m.calibration,
            "notes": {k: v for k, v in (m.notes or {}).items() if k != "train_means"},
            "train_means": (m.notes or {}).get("train_means")}


def main():
    art = H.envelope(JOB, "running")
    if not H.dataset_present():
        art["status"] = "data_insufficient"
        H.write_json("job06_fit_ladder.json", art)
        return H.emit("data_insufficient", "transfer dataset absent -- cannot fit the ladder")

    from wcdrawlab.research.transfer import hierarchical_models as HM

    rows = H.load_dataset_rows()
    feat_cols = H.discover_feat_cols(rows)
    folds = H.fold_names(rows)
    if not folds:
        art["status"] = "data_insufficient"
        H.write_json("job06_fit_ladder.json", art)
        return H.emit("data_insufficient", "no folds in materialised dataset")

    fitted_store = {"schema_version": "hierarchical_transfer_fitted_v1", "ts": H.utc(),
                    "labels": H.LABELS, "feature_cols": feat_cols, "folds": {}}
    fold_summ = []
    for fold in folds:
        part = H.split_fold(rows, fold)
        intl_train, club_train = part["intl_train"], part["club_train"]
        if not intl_train:
            fold_summ.append({"fold": fold, "status": "skipped", "reason": "no intl-train rows"})
            continue
        overlap = H._fnum(intl_train[0].get("domain_overlap_score"))
        overlap = overlap if overlap is not None else 1.0
        ladder = HM.fit_ladder(intl_train, club_train, feat_cols, overlap_score=overlap, alpha=1.0)
        gate = ladder["_gate"]
        models = {mid: _serialize(m) for mid, m in ladder.items()
                  if mid not in ("_gate", "_feat_cols")}
        fitted_store["folds"][fold] = {
            "n_intl_train": len(intl_train), "n_club_train": len(club_train),
            "overlap_score": overlap,
            "gate": {"passed": gate.passed, "reason": gate.reason, "n_club": gate.n_club_train},
            "models": models,
        }
        fold_summ.append({
            "fold": fold, "status": "fitted", "n_intl_train": len(intl_train),
            "n_club_train": len(club_train), "gate_passed": gate.passed, "gate_reason": gate.reason,
            "t1_n_train": ladder[HM.T1_INTERNATIONAL_ONLY].n_train,
            "t4_domain_intercepts": ladder[HM.T4_PARTIAL_POOLING].domain_intercepts,
            "t7_calibration": ladder[HM.T7_CALIBRATED_SIMULATION].calibration,
        })

    # persist the fitted store (used by JOB07/08/10/11)
    store_path = H.art_dir() / "fitted_ladder.json"
    store_path.write_text(json.dumps(fitted_store, default=str), encoding="utf-8")

    n_fitted = sum(1 for s in fold_summ if s.get("status") == "fitted")
    art.update({"n_folds": len(folds), "n_folds_fitted": n_fitted, "feature_cols": feat_cols,
                "fold_summary": fold_summ, "fitted_store": str(store_path)})
    if n_fitted == 0:
        art["status"] = "data_insufficient"
        H.write_json("job06_fit_ladder.json", art)
        return H.emit("data_insufficient", "no fold could be fitted (no intl-train rows)")
    art["status"] = "complete"
    H.write_json("job06_fit_ladder.json", art)
    H.emit("complete",
           f"fitted T0-T7 ladder on {n_fitted}/{len(folds)} folds; "
           f"gate_passed_folds={[s['fold'] for s in fold_summ if s.get('gate_passed')]}",
           state_updates={"ladder_fitted": True, "n_folds_fitted": n_fitted})


if __name__ == "__main__":
    main()
