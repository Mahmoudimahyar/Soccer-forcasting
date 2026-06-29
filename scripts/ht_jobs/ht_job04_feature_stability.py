"""HT_JOB04 -- freeze the FEATURE-STABILITY REGISTRY.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: freeze the per-feature stability decision that the transfer ladder is bound to. A feature is
TRANSFER-ELIGIBLE iff it survives the stable-feature gate the dataset builder applied (populated in BOTH
domains' training rows + not domain-shifted beyond tolerance). With club events absent locally the gate is
the single-domain availability gate; the registry records each feature's CLASS (kept / always_excluded /
insufficient_data) + the reason, and the per-fold subset (which is identical across folds in this build).

The frozen registry is written to data/reference/hierarchical_feature_stability_registry.{json,csv} and
mirrored into the run dir. It surfaces (and reconciles with) the existing Phase-2
feature_stability_registry.* product. Honest data_insufficient if the dataset is absent.
"""
from __future__ import annotations

import csv
from typing import Dict, List

import _ht as H

JOB = "JOB4"

REG_JSON = H.REF / "hierarchical_feature_stability_registry.json"
REG_CSV = H.REF / "hierarchical_feature_stability_registry.csv"

ALWAYS_EXCLUDED = ["poss_actions_home", "poss_actions_away", "n_events_observed"]


def main():
    art = H.envelope(JOB, "running")
    existing = H.read_ref_json("feature_stability_registry.json")

    if not H.dataset_present():
        art["status"] = "data_insufficient"
        art["existing_phase2_registry_present"] = existing is not None
        H.write_json("job04_feature_stability.json", art)
        return H.emit("data_insufficient",
                      "materialised transfer dataset absent -- cannot freeze the stability registry from "
                      "the real kept subset")

    rows = H.load_dataset_rows()
    feat_cols = H.discover_feat_cols(rows)              # the kept stable-feature subset (feat_*)
    kept_bare = [c[len("feat_"):] for c in feat_cols]

    # candidate universe = the dataset builder's candidate list (from the canonical module)
    DND = H.dnd()
    candidate = list(getattr(DND, "CANDIDATE_TRANSFER_FEATURE_COLS", kept_bare))
    excluded = list(getattr(DND, "ALWAYS_EXCLUDED_DOMAIN_SHIFTED_COLS", ALWAYS_EXCLUDED))

    n_club = sum(1 for r in rows if (r.get("domain") or "international") == "club")
    single_domain = n_club == 0

    registry: List[dict] = []
    for c in candidate:
        if c in excluded:
            cls, reason = "always_excluded", "domain_shifted_logging_density_or_provenance"
        elif c in kept_bare:
            cls, reason = "transfer_eligible", ("kept_single_domain_availability_gate" if single_domain
                                                else "kept_cross_domain_gate")
        else:
            cls, reason = "insufficient_data", "not_in_kept_subset"
        registry.append({"feature": c, "class": cls, "reason": reason,
                         "transfer_eligible": cls == "transfer_eligible",
                         "single_domain_gate": single_domain})
    for c in excluded:
        if c not in [r["feature"] for r in registry]:
            registry.append({"feature": c, "class": "always_excluded",
                             "reason": "domain_shifted_logging_density_or_provenance",
                             "transfer_eligible": False, "single_domain_gate": single_domain})

    frozen = {
        "schema_version": "hierarchical_feature_stability_registry_v1",
        "generated_ts": H.utc(),
        "labels": H.LABELS,
        "reference_model": "research.transfer.w2_reference_t0",
        "single_domain_train": single_domain,
        "n_transfer_eligible": sum(1 for r in registry if r["transfer_eligible"]),
        "n_always_excluded": sum(1 for r in registry if r["class"] == "always_excluded"),
        "n_insufficient_data": sum(1 for r in registry if r["class"] == "insufficient_data"),
        "kept_subset": kept_bare,
        "kept_subset_size": len(kept_bare),
        "features": registry,
        "dataset_sha256": H.sha256_file(H.DATASET_CSV),
    }
    # freeze to data/reference (canonical) + mirror into the run dir
    REG_JSON.parent.mkdir(parents=True, exist_ok=True)
    REG_JSON.write_text(__import__("json").dumps(frozen, indent=2), encoding="utf-8")
    with REG_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["feature", "class", "reason", "transfer_eligible",
                                          "single_domain_gate"])
        w.writeheader()
        for r in registry:
            w.writerow(r)

    art.update({
        "existing_phase2_registry_present": existing is not None,
        "frozen_registry_json": str(REG_JSON),
        "frozen_registry_csv": str(REG_CSV),
        "n_transfer_eligible": frozen["n_transfer_eligible"],
        "kept_subset_size": frozen["kept_subset_size"],
        "single_domain_train": single_domain,
    })
    H.write_json("job04_feature_stability.json", {**art, "registry": frozen})
    art["status"] = "complete"
    H.emit("complete",
           f"feature-stability registry frozen: {frozen['n_transfer_eligible']} transfer-eligible, "
           f"{frozen['n_always_excluded']} always-excluded (single_domain={single_domain})",
           state_updates={"feature_stability_frozen": True,
                          "n_transfer_eligible": frozen["n_transfer_eligible"],
                          "kept_subset_size": frozen["kept_subset_size"]})


if __name__ == "__main__":
    main()
