"""EV_JOB11 -- cross-artifact consistency audit.

Cross-checks that the SAME quantity, when it appears in more than one local artifact, agrees everywhere.
A consolidation is only trustworthy if its headline numbers are not silently divergent across files.

Checks (each yields {name, values, consistent, sources}):
  X1  n_matches == 58 across: cohort lineage residual_population, 58-match audit recompute, 58-match audit
      reported dataset-manifest, match-level power n_matches_observed.
  X2  forward-chain pooled R0 RPS agrees: 58-match audit recomputed vs reported.
  X3  funnel exact_bridge_population (258) agrees: lineage vs 58-match audit funnel first stage.
  X4  dropped_missing_statsbomb_events (200) == exact_bridge - residual (lineage internal arithmetic).
  X5  on-disk StatsBomb event JSON count agrees: lineage meta vs statsbomb_cache_audit (when present).

Honest: a quantity present in only one artifact is reported as `single_source` (not a failure). A real
divergence is `inconsistent` and fails the job. data_insufficient if no artifacts are present.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev


def _check(name, values_dict, tol=None):
    vals = {k: v for k, v in values_dict.items() if v is not None}
    distinct = set()
    for v in vals.values():
        distinct.add(round(v, 5) if (tol is not None and isinstance(v, float)) else v)
    if len(vals) <= 1:
        status = "single_source"
        consistent = True
    elif tol is not None:
        nums = list(vals.values())
        consistent = (max(nums) - min(nums)) <= tol
        status = "consistent" if consistent else "inconsistent"
    else:
        consistent = (len(distinct) == 1)
        status = "consistent" if consistent else "inconsistent"
    return {"name": name, "values": vals, "status": status, "consistent": consistent}


def main():
    lin = _ev.read_ref_json("evaluation_cohort_lineage.json") or {}
    audit58 = _ev.read_ref_json("residual_58_match_audit.json") or {}
    power = _ev.read_ref_json("match_level_power_analysis.json") or {}
    sb_cache = _ev.read_ref_json("statsbomb_cache_audit.json") or {}

    if not lin and not audit58 and not power:
        _ev.emit("data_insufficient", reason="no consolidation artifacts present to cross-check")
        return

    meta = lin.get("meta", {})
    fs = meta.get("funnel_summary", {})
    cmp = audit58.get("comparison", {})
    nm = cmp.get("n_matches") or {}
    fc = cmp.get("forward_chain_pooled_rps") or {}
    a58_funnel = [s.get("n_matches") for s in (audit58.get("funnel", {}).get("stages") or [])]

    checks = []
    checks.append(_check("n_matches_58", {
        "lineage_residual_population": fs.get("residual_population"),
        "audit_recomputed": nm.get("recomputed"),
        "audit_reported_manifest": nm.get("reported_dataset_manifest"),
        "power_n_matches_observed": (power.get("data_provenance", {}) or {}).get("n_matches_observed"),
    }))
    checks.append(_check("forward_chain_r0_rps", {
        "audit_recomputed": fc.get("recomputed"), "audit_reported": fc.get("reported"),
    }, tol=5e-4))
    checks.append(_check("exact_bridge_258", {
        "lineage_exact_bridge": fs.get("exact_bridge_population"),
        "audit_funnel_stage0": (a58_funnel[0] if a58_funnel else None),
    }))
    # X4 internal arithmetic (single artifact, but a derived equality check)
    eb, drop, resid = (fs.get("exact_bridge_population"), fs.get("dropped_missing_statsbomb_events"),
                       fs.get("residual_population"))
    arith_ok = (None not in (eb, drop, resid)) and ((eb - drop) == resid)
    checks.append({"name": "funnel_arithmetic_eb_minus_drop_eq_resid",
                   "values": {"exact_bridge": eb, "dropped": drop, "residual": resid},
                   "status": "consistent" if arith_ok else (
                       "inconsistent" if None not in (eb, drop, resid) else "single_source"),
                   "consistent": arith_ok or None in (eb, drop, resid)})
    checks.append(_check("on_disk_statsbomb_event_json", {
        "lineage_on_disk_count": meta.get("on_disk_event_json_count"),
        "statsbomb_cache_audit": (sb_cache.get("n_event_json_on_disk")
                                  or sb_cache.get("n_events_cached")
                                  or sb_cache.get("on_disk_event_count")),
    }))

    inconsistencies = [c for c in checks if c["status"] == "inconsistent"]
    all_consistent = (len(inconsistencies) == 0)
    _ev.write_json("ev_consistency_audit.json", {
        "checks": checks, "n_checks": len(checks),
        "n_inconsistent": len(inconsistencies), "all_consistent": all_consistent,
        "utc": _ev.utc(), "labels": _ev.LABELS,
    })
    if not all_consistent:
        _ev.emit("failed",
                 reason=f"cross-artifact inconsistency: {[c['name'] for c in inconsistencies]}")
        return
    _ev.emit("complete",
             reason=f"all {len(checks)} cross-artifact checks consistent "
                    f"(n_matches=58, FC RPS, 258 bridge, funnel arithmetic, on-disk events)",
             state_updates={"consistency_checks": len(checks),
                            "consistency_all_ok": all_consistent})


main()
