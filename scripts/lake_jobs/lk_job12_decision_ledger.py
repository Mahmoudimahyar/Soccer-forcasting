"""LK_JOB12 -- decision ledger + reproducibility + source-quality consolidation.

Consolidates, with NO recompute and NO fabrication, the REAL products already on disk into a single
decision package:
  * DECISION LEDGER -- the locked candidate verdict from the model rerun
    (international_event_lake_model_decision_ledger.json): reference_only / accepted / rejected /
    data_insufficient, with the rule-by-rule pass/fail.
  * REPRODUCIBILITY -- the deterministic-recompute audit
    (international_event_lake_reproducibility_audit.json) + the input cohort lake-hash provenance.
  * SOURCE QUALITY -- derived DIRECTLY from the lake index (raw-backed): per-object event_count,
    xg/possession/location availability, ingestion_mode (copied_local vs retrieved_official), source_url
    host (must be the official open-data host for retrieved objects), and the competition/season mix.

Writes data/reference/international_event_lake_decision_package.json. Emits the consolidated verdict. This
job never changes a model decision; it only assembles + audits provenance. A source object whose recorded
source_url is NOT the official host is flagged (defence in depth) -- but the engine only ever records the
official template, so this should be empty.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk


def main():
    L = _lk.lake_engine()
    try:
        lake = L.Lake.resolve()
        index = L.read_index(lake)
    except Exception as e:
        _lk.emit("failed", reason=f"lake_resolve_failed: {e!r}")
        return

    ledger = _lk.read_ref_json("international_event_lake_model_decision_ledger.json") or {}
    audit = _lk.read_ref_json("international_event_lake_reproducibility_audit.json") or {}
    cohort = _lk.read_ref_json("international_event_lake_cohort_manifest.json") or {}
    power = _lk.read_ref_json("international_event_lake_power_analysis.json") or {}

    # ---- source quality straight from the lake index (raw-backed) --------------------------------
    n_obj = len(index)
    n_xg = sum(1 for r in index.values() if r.get("xg_available"))
    n_poss = sum(1 for r in index.values() if r.get("possession_available"))
    n_loc = sum(1 for r in index.values() if r.get("location_available"))
    total_events = sum(int(r.get("event_count") or 0) for r in index.values())
    ingestion_modes = Counter(r.get("ingestion_mode") or "unknown" for r in index.values())
    comp_mix = Counter(r.get("competition_label") or "unknown" for r in index.values())

    # official-source provenance check for retrieved objects (copied_local objects record the template too)
    non_official = [sb for sb, r in index.items()
                    if r.get("source_url") and _lk.OFFICIAL_HOST not in str(r.get("source_url"))]

    verdict = ledger.get("verdict") or ledger.get("decision") or "data_insufficient"

    package = {
        "decision_ledger": {
            "verdict": verdict,
            "reference_model": ledger.get("reference_model"),
            "candidate_model": ledger.get("candidate_model"),
            "rules": ledger.get("rules"),
            "reason": ledger.get("reason"),
        },
        "reproducibility": {
            "deterministic": audit.get("deterministic"),
            "recompute_hash": audit.get("recompute_hash") or audit.get("hash"),
            "cohort_lake_root": cohort.get("lake_root"),
            "n_cohort_matches": cohort.get("n_cohort_matches"),
            "n_index_objects": cohort.get("n_index_objects"),
        },
        "source_quality": {
            "lake_objects": n_obj, "total_events": total_events,
            "objects_with_xg": n_xg, "objects_with_possession": n_poss,
            "objects_with_location": n_loc,
            "xg_fraction": round(n_xg / n_obj, 4) if n_obj else None,
            "ingestion_modes": dict(ingestion_modes),
            "competition_mix": dict(comp_mix),
            "non_official_source_objects": non_official,
            "official_source_only": not non_official,
            "official_host": _lk.OFFICIAL_HOST,
        },
        "power": {"observed_M_matches": power.get("observed_M_matches"),
                  "bootstrap_unit": "match_clustered"},
        "labels": _lk.LABELS, "utc": _lk.utc(),
    }
    out_path = _lk.REF / "international_event_lake_decision_package.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    out_path.write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
    _lk.write_json("lk_decision_package.json", package)

    # defence in depth: a non-official recorded source is a provenance breach
    if non_official:
        _lk.emit("failed",
                 reason=f"PROVENANCE breach: {len(non_official)} lake objects record a non-official "
                        f"source_url (must be {_lk.OFFICIAL_HOST}) -- fail closed: {non_official[:10]}")
        return

    _lk.emit("complete",
             reason=f"decision package consolidated: verdict={verdict} objects={n_obj} xg={n_xg} "
                    f"events={total_events} ingestion={dict(ingestion_modes)} official_source_only=True "
                    f"repro_deterministic={audit.get('deterministic')}",
             state_updates={"decision_verdict": verdict, "decision_package_done": True,
                            "source_official_only": True})


main()
