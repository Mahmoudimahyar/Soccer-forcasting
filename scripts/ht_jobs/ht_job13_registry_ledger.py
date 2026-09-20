"""HT_JOB13 -- model registry + feature-stability registry + DECISION LEDGER.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: consolidate the run into durable, auditable registries:
  * MODEL REGISTRY (one row per T0..T7 model): id, family, fitted?, pooled RPS vs T0, beats-T0?,
    CI-excludes-0?, eligibility labels -- NONE is runtime/trade/live approved;
  * FEATURE-STABILITY REGISTRY: re-surface the frozen registry from JOB04 (kept subset + classes);
  * DECISION LEDGER -> data/reference/hierarchical_transfer_decision_ledger.{json,csv}: the auditable
    record of WHAT was decided (selected model per fold, gate decisions, accept/reject vs T0, the
    honest single-domain caveat) with provenance hashes. Every row is stamped not_runtime_approved.

Honest data_insufficient if the forward-chain artifact is absent (no decisions to record).
"""
from __future__ import annotations

import csv
import json

import _ht as H

JOB = "JOB13"

LEDGER_JSON = H.REF / "hierarchical_transfer_decision_ledger.json"
LEDGER_CSV = H.REF / "hierarchical_transfer_decision_ledger.csv"

FAMILY = {
    "research.transfer.w2_reference_t0": "reference_parameter_free",
    "research.transfer.international_only_t1": "intl_only_ridge_residual",
    "research.transfer.naive_club_pool_t2": "naive_pooled_no_domain_correction",
    "research.transfer.shared_stable_features_t3": "shared_coeff_stable_subset",
    "research.transfer.partial_pooling_t4": "hierarchical_partial_pooling_glm",
    "research.transfer.domain_weighted_t5": "domain_overlap_weighted",
    "research.transfer.selective_transfer_t6": "selective_gated_transfer",
    "research.transfer.calibrated_transfer_simulation_t7": "calibrated_mc_simulation",
}


def main():
    art = H.envelope(JOB, "running")
    fc = H.read_run_json("job07_forward_chain.json")
    if fc is None:
        art["status"] = "data_insufficient"
        H.write_json("job13_registry_ledger.json", art)
        return H.emit("data_insufficient", "forward-chain artifact (JOB07) absent -- no decisions to record")

    pooled = fc.get("pooled") or {}
    fa = H.read_run_json("job12_failure_analysis.json") or {}
    fitted = H.load_fitted_store() or {"folds": {}}
    feat_reg = H.read_ref_json("hierarchical_feature_stability_registry.json")

    # ---- model registry ----
    T = H.transfer_ids()
    model_registry = []
    for mid in T.TRANSFER_MODELS:
        if mid == T.T0_REFERENCE:
            model_registry.append({"model_id": mid, "family": FAMILY[mid], "is_reference": True,
                                   "fitted": False, "rps_vs_t0": 0.0, "beats_t0": False,
                                   "ci_excludes_zero": False,
                                   "eligibility": H.LABELS})
            continue
        m = pooled.get(mid) or {}
        model_registry.append({
            "model_id": mid, "family": FAMILY.get(mid, "unknown"), "is_reference": False,
            "fitted": m.get("status") != "no_scored_rows",
            "rps": m.get("rps"), "rps_t0": m.get("rps_t0"),
            "rps_delta_vs_t0": m.get("rps_delta_vs_t0"),
            "beats_t0": bool(m.get("beats_t0_on_rps")),
            "ci_excludes_zero": bool(m.get("ci_excludes_zero")),
            "runtime_approved": False, "trade_eligible": False, "live_eligible": False,
            "eligibility": H.LABELS,
        })

    # ---- decision ledger (per fold) ----
    ledger_rows = []
    for fold, fstore in (fitted.get("folds") or {}).items():
        gate = fstore.get("gate") or {}
        # the selected model is T6 (selective); record what it fell back to
        selected = (T.T4_PARTIAL_POOLING if gate.get("passed") else T.T1_INTERNATIONAL_ONLY)
        fc_fold = (fc.get("per_fold") or {}).get(fold, {})
        t6_score = (fc_fold.get("scores") or {}).get(T.T6_SELECTIVE_TRANSFER, {})
        ledger_rows.append({
            "fold_held_tournament": fold,
            "n_intl_train": fstore.get("n_intl_train"),
            "n_club_train": fstore.get("n_club_train"),
            "overlap_score": fstore.get("overlap_score"),
            "selective_gate_passed": bool(gate.get("passed")),
            "selective_gate_reason": gate.get("reason"),
            "selected_model_via_t6": selected,
            "t6_rps": t6_score.get("rps"),
            "t6_rps_t0": t6_score.get("rps_t0"),
            "t6_rps_delta_vs_t0": t6_score.get("rps_delta_vs_t0"),
            "decision": ("transfer_enabled" if gate.get("passed") else "fallback_intl_only"),
            "accept_for_runtime": False,
            "eligibility": H.LABELS,
        })

    ledger = {
        "schema_version": "hierarchical_transfer_decision_ledger_v1",
        "generated_ts": H.utc(),
        "labels": H.LABELS,
        "reference_model": T.T0_REFERENCE,
        "verdict": fa.get("verdict"),
        "single_domain_regime": fa.get("single_domain_regime"),
        "any_model_separated_from_t0": fa.get("statistically_separated_from_t0") or [],
        "dataset_sha256": H.sha256_file(H.DATASET_CSV),
        "model_registry": model_registry,
        "per_fold_decisions": ledger_rows,
        "global_decision": ("NO model is accepted for runtime/trade/live; all research_only. "
                            + (str(fa.get("verdict") or ""))),
    }

    LEDGER_JSON.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_JSON.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")
    if ledger_rows:
        with LEDGER_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(ledger_rows[0].keys()))
            w.writeheader()
            for r in ledger_rows:
                w.writerow(r)
    else:
        LEDGER_CSV.write_text("fold_held_tournament,decision,eligibility\n", encoding="utf-8")

    # mirror into run dir
    H.write_json("job13_decision_ledger.json", ledger)
    art.update({
        "model_registry_size": len(model_registry),
        "decision_ledger_json": str(LEDGER_JSON),
        "decision_ledger_csv": str(LEDGER_CSV),
        "n_ledger_rows": len(ledger_rows),
        "feature_stability_registry_present": feat_reg is not None,
        "feature_stability_kept_subset_size": (feat_reg or {}).get("kept_subset_size"),
        "global_decision": ledger["global_decision"],
    })
    art["status"] = "complete"
    H.write_json("job13_registry_ledger.json", art)
    H.emit("complete",
           f"registries + decision ledger written ({len(model_registry)} models, "
           f"{len(ledger_rows)} fold decisions); NONE runtime/trade/live approved",
           state_updates={"registry_ledger_ok": True, "decision_ledger": str(LEDGER_JSON)})


if __name__ == "__main__":
    main()
