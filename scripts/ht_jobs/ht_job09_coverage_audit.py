"""HT_JOB09 -- transfer-COVERAGE / OVERLAP / FALLBACK audit.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: audit how much TRANSFER actually happened and whether the selective fallback behaved correctly.
  * coverage: per-fold counts of intl-train vs club-aux-train rows, the domain-overlap score, the kept
    stable-feature subset, and per-row availability over the kept subset;
  * fallback: for each fold report the selective gate decision (T6 -> T4 if passed, else -> T1) and assert
    that when club evidence is absent the gate FALLS BACK to international-only (no harmful transfer);
  * isolation re-assert (raw not git-tracked; no root in collector; no forbidden imports).

This is the audit that certifies the transfer machinery is honest about HOW LITTLE/MUCH cross-domain
evidence it had. Honest data_insufficient if the dataset/fitted store is absent.
"""
from __future__ import annotations

import _ht as H

JOB = "JOB9"


def main():
    art = H.envelope(JOB, "running")
    if not H.dataset_present():
        art["status"] = "data_insufficient"
        H.write_json("job09_coverage_audit.json", art)
        return H.emit("data_insufficient", "transfer dataset absent -- cannot audit coverage")

    rows = H.load_dataset_rows()
    feat_cols = H.discover_feat_cols(rows)
    store = H.load_fitted_store() or {"folds": {}}
    folds = H.fold_names(rows)

    per_fold = {}
    fallbacks_ok = True
    for fold in folds:
        part = H.split_fold(rows, fold)
        n_intl_tr = len(part["intl_train"]); n_club_tr = len(part["club_train"])
        n_intl_te = len(part["intl_test"])
        overlap = H._fnum((part["intl_train"] or part["intl_test"] or [{}])[0].get("domain_overlap_score"))
        # availability over kept subset on test rows
        avail = {"available_verified": 0, "available_partial": 0, "unavailable": 0}
        for r in part["intl_test"]:
            a = r.get("availability") or "unavailable"
            avail[a] = avail.get(a, 0) + 1
        gate = ((store.get("folds") or {}).get(fold) or {}).get("gate") or {}
        # fallback correctness: if no club rows -> gate must NOT have passed (fall back to intl-only)
        expected_fallback = (n_club_tr == 0)
        gate_passed = bool(gate.get("passed"))
        fallback_correct = (not gate_passed) if expected_fallback else True
        if not fallback_correct:
            fallbacks_ok = False
        per_fold[fold] = {
            "n_intl_train_rows": n_intl_tr, "n_club_train_rows": n_club_tr,
            "n_intl_test_rows": n_intl_te, "domain_overlap_score": overlap,
            "kept_subset_size": len(feat_cols), "test_availability": avail,
            "gate": gate, "expected_fallback_to_intl_only": expected_fallback,
            "fallback_correct": fallback_correct,
            "transfer_active": gate_passed and n_club_tr > 0,
        }

    n_club_total = sum(1 for r in rows if (r.get("domain") or "international") == "club")
    iso = H.isolation_report()
    coverage_class = ("intl_only_no_club_evidence" if n_club_total == 0 else "cross_domain")

    art.update({
        "coverage_class": coverage_class,
        "n_club_rows_total": n_club_total,
        "kept_stable_feature_subset": [c[len("feat_"):] for c in feat_cols],
        "per_fold": per_fold,
        "all_fallbacks_correct": fallbacks_ok,
        "isolation": iso,
    })

    iso_bad = (iso["roots_in_collector"] or iso["forbidden_imports"]
               or iso["raw_git_tracked"] != "(none)")
    if iso_bad:
        art["status"] = "failed"
        H.write_json("job09_coverage_audit.json", art)
        return H.emit("failed", f"isolation violation during coverage audit: {iso}")
    if not fallbacks_ok:
        art["status"] = "failed"
        H.write_json("job09_coverage_audit.json", art)
        return H.emit("failed", "selective fallback INCORRECT: a fold with no club evidence let the "
                                "transfer gate pass (would be harmful transfer)")

    art["status"] = "complete"
    H.write_json("job09_coverage_audit.json", art)
    H.emit("complete",
           f"coverage audit ok: class={coverage_class}; club_rows={n_club_total}; "
           f"all selective fallbacks correct",
           state_updates={"coverage_audit_ok": True, "coverage_class": coverage_class,
                          "n_club_rows_total": n_club_total})


if __name__ == "__main__":
    main()
