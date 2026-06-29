"""HT_JOB02 -- cross-domain event-process INVENTORY + contract.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: surface the Phase-1 cross-domain inventory (international event lake + club auxiliary corpus)
and assert the transfer CONTRACT that the rest of the queue depends on:
  * the international event-lake cohort manifest exists and reports a non-zero count;
  * the club auxiliary manifest exists (auxiliary training domain);
  * the domain inventory product (data/reference/domain_event_process_inventory.{json,csv}) exists.

If the Phase-1 inventory product is absent, the job rebuilds it via the EXISTING real builder
(scripts/build_domain_event_process_inventory.py) as a read-only subprocess and parses its last JSON line.
Honest skip if neither the product nor the builder can produce an inventory (never fabricates counts).
"""
from __future__ import annotations

import csv
from pathlib import Path

import _ht as H

JOB = "JOB2"

INV_JSON = H.REF / "domain_event_process_inventory.json"
INV_CSV = H.REF / "domain_event_process_inventory.csv"
INTL_COHORT_JSON = H.REF / "international_event_lake_cohort_manifest.json"
INTL_COHORT_CSV = H.REF / "international_event_lake_cohort_manifest.csv"
CLUB_MANIFEST_CSV = H.REF / "event_process_auxiliary_manifest.csv"
CLUB_MANIFEST_JSON = H.REF / "event_process_auxiliary_manifest.json"


def _count_csv_rows(p: Path) -> int:
    if not p.exists():
        return 0
    try:
        with p.open("r", encoding="utf-8", newline="") as f:
            return sum(1 for _ in csv.reader(f)) - 1  # minus header
    except Exception:
        return 0


def _inventory_counts():
    inv = H.read_ref_json("domain_event_process_inventory.json")
    if not inv:
        return None
    # the inventory json is large; summarise the domains present + per-domain match counts
    by_domain = {}
    rows = inv.get("rows") if isinstance(inv, dict) else None
    if isinstance(rows, list):
        for r in rows:
            d = r.get("domain") or "unknown"
            by_domain[d] = by_domain.get(d, 0) + 1
    summary = inv.get("summary") if isinstance(inv, dict) else None
    return {"by_domain_rowcount": by_domain or None, "summary": summary,
            "top_keys": sorted(list(inv.keys()))[:20] if isinstance(inv, dict) else None}


def main():
    art = H.envelope(JOB, "running")

    # try to surface the existing inventory product; rebuild via the real builder if absent
    rebuilt = None
    if not INV_JSON.exists():
        rebuilt = H.run_builder("scripts/build_domain_event_process_inventory.py", timeout=7200)

    intl_cohort = _count_csv_rows(INTL_COHORT_CSV)
    club_manifest = _count_csv_rows(CLUB_MANIFEST_CSV)
    inv_counts = _inventory_counts()

    contract = {
        "international_event_lake_cohort_manifest_present": INTL_COHORT_JSON.exists(),
        "n_international_cohort_matches": intl_cohort,
        "club_auxiliary_manifest_present": CLUB_MANIFEST_CSV.exists(),
        "n_club_auxiliary_matches": club_manifest,
        "domain_inventory_present": INV_JSON.exists(),
        "domain_inventory_sha256": H.sha256_file(INV_JSON),
    }
    art.update({
        "contract": contract,
        "inventory_summary": inv_counts,
        "rebuild_attempted": rebuilt is not None,
        "rebuild_result": (rebuilt.get("last_json") if rebuilt else None),
        "source_manifests": {
            "intl_cohort_csv": str(INTL_COHORT_CSV),
            "club_manifest_csv": str(CLUB_MANIFEST_CSV),
            "domain_inventory_json": str(INV_JSON),
        },
    })

    if not INTL_COHORT_JSON.exists() or intl_cohort <= 0:
        art["status"] = "data_insufficient"
        H.write_json("job02_domain_inventory.json", art)
        return H.emit("data_insufficient",
                      "international event-lake cohort manifest absent/empty -- cannot proceed without "
                      "the primary international test population")

    if not INV_JSON.exists():
        art["status"] = "data_insufficient"
        H.write_json("job02_domain_inventory.json", art)
        return H.emit("data_insufficient",
                      "domain event-process inventory product absent and could not be rebuilt locally")

    art["status"] = "complete"
    H.write_json("job02_domain_inventory.json", art)
    H.emit("complete",
           f"inventory ok: intl_cohort={intl_cohort} matches, club_aux_manifest={club_manifest} matches "
           f"(auxiliary training only)",
           state_updates={"n_international_cohort_matches": intl_cohort,
                          "n_club_auxiliary_matches": club_manifest,
                          "domain_inventory_ok": True})


if __name__ == "__main__":
    main()
