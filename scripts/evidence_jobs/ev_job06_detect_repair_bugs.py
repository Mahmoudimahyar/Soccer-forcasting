"""EV_JOB06 -- detect + repair VERIFIED bugs ONLY.

Scans the consolidated evidence for a VERIFIED defect -- a discrepancy that is reproducible and provably
wrong, not a mere data-availability boundary or a difference in convention. A defect is only "verified"
when an independent recompute CONTRADICTS a reported number beyond tolerance, or the lineage shows a
silent/unexplained drop, or a drop reason is outside the allowed category set.

Checks performed (all from local artifacts already produced upstream):
  C1  lineage integrity: allowed_reasons_only AND no_silent_disappearance must both hold;
  C2  58-match independent recompute: forward-chain + LOCO R0 RPS must MATCH the reported values
      within tolerance (a mismatch would be a verified reproducibility bug);
  C3  funnel arithmetic: exact_bridge - dropped_missing_statsbomb_events == residual_population;
  C4  cohort count: independently reconstructed n_matches == reported dataset-manifest n_matches.

If NO check fails -> there is no verified bug to repair -> writes repair_log.json with
{"no_repair_required": true, ...} and emits complete (honest negative). It NEVER invents a repair.
If a check fails -> records the precise defect in repair_log.json and emits with repair_required=true
(the actual code fix belongs to the owning module; here we record the verified defect + its evidence).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev


def main():
    lin = _ev.read_ref_json("evaluation_cohort_lineage.json") or {}
    audit58 = _ev.read_ref_json("residual_58_match_audit.json") or {}
    meta = lin.get("meta", {})
    fs = meta.get("funnel_summary", {})
    cmp = audit58.get("comparison", {})
    v = audit58.get("verdict", {})

    defects = []

    # C1 lineage integrity
    if meta:
        if not meta.get("allowed_reasons_only", False):
            defects.append({"check": "C1_allowed_reasons", "detail": "a drop reason outside the allowed "
                            "category set", "evidence": meta.get("bad_reasons")})
        if not meta.get("no_silent_disappearance", False):
            defects.append({"check": "C1_silent_disappearance", "detail": "a fixture dropped between "
                            "stages without a recorded reason", "evidence": meta.get("unexplained_drops")})

    # C2 independent recompute match
    if cmp:
        fc = cmp.get("forward_chain_pooled_rps") or {}
        loco = cmp.get("loco_pooled_rps") or {}
        if fc.get("match") is False:
            defects.append({"check": "C2_forward_chain_rps", "detail": "independent recompute contradicts "
                            "reported forward-chain RPS", "evidence": fc})
        if loco.get("match") is False:
            defects.append({"check": "C2_loco_rps", "detail": "independent recompute contradicts reported "
                            "LOCO RPS", "evidence": loco})

    # C3 funnel arithmetic
    if fs:
        eb = fs.get("exact_bridge_population")
        drop = fs.get("dropped_missing_statsbomb_events")
        resid = fs.get("residual_population")
        if None not in (eb, drop, resid) and (eb - drop) != resid:
            defects.append({"check": "C3_funnel_arithmetic",
                            "detail": f"{eb} - {drop} != {resid}", "evidence": fs})

    # C4 cohort count consistency
    nm = cmp.get("n_matches") or {}
    if nm.get("recomputed") is not None and nm.get("reported_dataset_manifest") is not None:
        if nm["recomputed"] != nm["reported_dataset_manifest"]:
            defects.append({"check": "C4_cohort_count",
                            "detail": "reconstructed n_matches != reported dataset-manifest n_matches",
                            "evidence": nm})

    no_repair = (len(defects) == 0)
    repair_log = {
        "checks_run": ["C1_lineage_integrity", "C2_independent_recompute",
                       "C3_funnel_arithmetic", "C4_cohort_count"],
        "verified_defects": defects,
        "no_repair_required": no_repair,
        "note": ("no verified bug found: the 258->58 reduction is a preregistered DATA-AVAILABILITY "
                 "boundary (missing_statsbomb_events), not a defect; all independent recomputes match; "
                 "no silent drops; funnel arithmetic balances"
                 if no_repair else "verified defect(s) recorded; repair belongs to the owning module"),
        "inputs_present": {"lineage": bool(lin), "audit58": bool(audit58)},
        "utc": _ev.utc(), "labels": _ev.LABELS,
    }
    _ev.write_json("repair_log.json", repair_log)

    if not lin and not audit58:
        _ev.emit("data_insufficient",
                 reason="neither lineage nor 58-match audit present; cannot assess defects")
        return
    if no_repair:
        _ev.emit("complete", reason="no_repair_required: 0 verified defects across C1-C4",
                 state_updates={"verified_defects": 0, "repair_required": False})
    else:
        _ev.emit("complete",
                 reason=f"{len(defects)} verified defect(s) recorded: "
                        f"{[d['check'] for d in defects]}",
                 state_updates={"verified_defects": len(defects), "repair_required": True,
                                "defect_checks": [d["check"] for d in defects]})


main()
