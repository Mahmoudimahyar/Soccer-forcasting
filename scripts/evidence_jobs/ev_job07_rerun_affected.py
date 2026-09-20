"""EV_JOB07 -- rerun affected evaluations ONLY if a VERIFIED repair was applied in JOB06.

Conditional by design. Reads repair_log.json from JOB06:
  - if no_repair_required (the honest-negative case) -> emit `skipped` with the explicit reason that
    there is nothing to rerun (a rerun without a repair would only burn cycles and risk perturbing a
    reproduced result). This is the expected path.
  - if a verified repair WAS applied -> rerun ONLY the evaluations whose inputs the repair touched
    (the affected set), via the existing offline builders, and record the before/after headline metric.

Never reruns the 2026 WC holdout. Never fits to any locked set. Offline only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev


def main():
    repair = _ev.read_run_json("repair_log.json")
    if repair is None:
        _ev.emit("skipped",
                 reason="repair_log.json absent (JOB06 did not run / produced no log) -> nothing to rerun")
        return

    if repair.get("no_repair_required", False) or not repair.get("verified_defects"):
        _ev.write_json("ev_rerun_affected.json", {
            "reran": [], "reason": "no_repair_required -> no affected evaluation to rerun",
            "no_repair_required": True, "utc": _ev.utc(), "labels": _ev.LABELS,
        })
        _ev.emit("skipped",
                 reason="no verified repair in JOB06 (no_repair_required=true) -> "
                        "no evaluation affected; rerun correctly skipped",
                 state_updates={"reran_evaluations": 0, "rerun_skipped_reason": "no_repair_required"})
        return

    # A verified repair exists -> rerun only the affected offline evaluations (recompute funnel + 58-match
    # audit, which are the consolidation's recomputable headline). 2026 WC is never touched.
    affected = []
    res_lin = _ev.run_builder("scripts/build_evaluation_cohort_lineage.py")
    res_58 = _ev.run_builder("scripts/audit_residual_58_match_cohort.py")
    affected.append({"evaluation": "cohort_lineage", "rc": res_lin["returncode"]})
    affected.append({"evaluation": "residual_58_match_audit", "rc": res_58["returncode"]})
    audit58 = _ev.read_ref_json("residual_58_match_audit.json") or {}
    fc = ((audit58.get("comparison", {}).get("forward_chain_pooled_rps")) or {})
    _ev.write_json("ev_rerun_affected.json", {
        "reran": affected, "no_repair_required": False,
        "post_repair_forward_chain_rps": fc.get("recomputed"),
        "post_repair_match": fc.get("match"),
        "defect_checks": repair.get("verified_defects"),
        "utc": _ev.utc(), "labels": _ev.LABELS,
    })
    ok = all(a["rc"] == 0 for a in affected)
    _ev.emit("complete" if ok else "failed",
             reason=f"reran affected evaluations after verified repair: {affected}; "
                    f"post-repair FC RPS={fc.get('recomputed')} match={fc.get('match')}",
             state_updates={"reran_evaluations": len(affected),
                            "post_repair_fc_rps": fc.get("recomputed")})


main()
