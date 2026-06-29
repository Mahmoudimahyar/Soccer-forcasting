"""HT_JOB05 -- fold-specific, domain-normalized TRANSFER DATASETS (critical).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: ensure the leakage-safe, domain-normalized transfer dataset is materialised, then certify it.
  * if data/processed/domain_normalized_transfer/transfer_dataset_v1.csv is absent, build it via the
    EXISTING real builder (scripts/build_domain_normalized_transfer_dataset.py) -- offline, lake-resolved;
  * run the EXISTING real audit (scripts/audit_domain_normalized_transfer_dataset.py --strict) and parse
    its last JSON line (11 leakage invariants);
  * load the materialised rows and record per-fold counts (intl_train / intl_test matches+rows, club_train)
    and the stable-feature subset sizes -- grounded in the real CSV, hashed for provenance.

Critical job: emits failed if the dataset cannot be produced/certified (no fabricated rows ever).
"""
from __future__ import annotations

from collections import defaultdict

import _ht as H

JOB = "JOB5"


def main():
    art = H.envelope(JOB, "running")

    built = None
    if not H.dataset_present():
        built = H.run_builder("scripts/build_domain_normalized_transfer_dataset.py", timeout=21600)
        art["build_attempted"] = True
        art["build_result"] = built.get("last_json")
        art["build_stderr_tail"] = built.get("stderr_tail")

    if not H.dataset_present():
        art["status"] = "failed"
        H.write_json("job05_transfer_datasets.json", art)
        return H.emit("failed",
                      "transfer dataset could not be materialised (lake/club events not yielding rows); "
                      f"builder said: {((built or {}).get('last_json') or {}).get('reason', 'n/a')}")

    # certify via the real strict audit. The audit prints a PRETTY (multi-line) JSON to stdout and ALSO
    # writes the canonical machine-readable result to data/reference/domain_normalized_transfer_audit.json
    # AND signals strict failure via exit code 2. We use the canonical artifact + the returncode (NOT the
    # pretty stdout, which the last-JSON-line heuristic cannot parse).
    audit = H.run_builder("scripts/audit_domain_normalized_transfer_dataset.py", ["--strict"], timeout=7200)
    audit_artifact = H.read_ref_json("domain_normalized_transfer_audit.json") or {}
    invariants_ok = bool(audit_artifact.get("all_invariants_ok")) and audit.get("returncode") == 0
    audit_json = {"all_invariants_ok": audit_artifact.get("all_invariants_ok"),
                  "checks": audit_artifact.get("checks"),
                  "failed_checks": [c["check"] for c in (audit_artifact.get("checks") or [])
                                    if not c.get("ok")],
                  "returncode": audit.get("returncode")}

    # ground-truth per-fold counts from the real CSV
    rows = H.load_dataset_rows()
    n2026 = H.assert_no_2026_rows(rows)
    folds = H.fold_names(rows)
    per_fold = {}
    for fold in folds:
        part = H.split_fold(rows, fold)
        per_fold[fold] = {
            "n_intl_train_rows": len(part["intl_train"]),
            "n_club_train_rows": len(part["club_train"]),
            "n_intl_test_rows": len(part["intl_test"]),
            "n_intl_test_matches": len({r.get("match_id") for r in part["intl_test"]}),
            "n_club_train_matches": len({r.get("match_id") for r in part["club_train"]}),
        }
    subset_sizes = sorted({int(H._fnum(r.get("stable_feature_subset_size")) or 0)
                           for r in rows[:200]})
    n_test_matches = len({r.get("match_id") for r in rows if r.get("row_role") == "intl_test"})

    manifest = H.read_ref_json(str(H.BUILD_MANIFEST)) or {}
    art.update({
        "dataset_csv": str(H.DATASET_CSV),
        "dataset_sha256": H.sha256_file(H.DATASET_CSV),
        "build_manifest_present": H.BUILD_MANIFEST.exists(),
        "n_rows_total": len(rows),
        "n_folds": len(folds),
        "folds": folds,
        "per_fold": per_fold,
        "stable_feature_subset_sizes": subset_sizes,
        "n_intl_test_matches_total": n_test_matches,
        "n_2026_rows": n2026,
        "audit_all_invariants_ok": invariants_ok,
        "audit_checks": audit_json.get("checks"),
        "audit_returncode": audit.get("returncode"),
    })

    if n2026 > 0:
        art["status"] = "failed"
        H.write_json("job05_transfer_datasets.json", art)
        return H.emit("failed", f"FORBIDDEN: {n2026} completed-2026-World-Cup rows present in dataset")
    if not invariants_ok:
        art["status"] = "failed"
        H.write_json("job05_transfer_datasets.json", art)
        return H.emit("failed",
                      f"dataset leakage audit FAILED (all_invariants_ok={invariants_ok}); "
                      f"audit returncode={audit.get('returncode')}")

    art["status"] = "complete"
    H.write_json("job05_transfer_datasets.json", art)
    H.emit("complete",
           f"transfer dataset certified: {len(rows)} rows, {len(folds)} folds, "
           f"{n_test_matches} intl-test matches, stable-subset={subset_sizes}, no-2026 ok, "
           f"all_invariants_ok={invariants_ok}",
           state_updates={"transfer_dataset_ok": True, "n_rows_total": len(rows),
                          "n_folds": len(folds), "n_intl_test_matches": n_test_matches,
                          "stable_feature_subset_sizes": subset_sizes,
                          "dataset_sha256": H.sha256_file(H.DATASET_CSV)})


if __name__ == "__main__":
    main()
