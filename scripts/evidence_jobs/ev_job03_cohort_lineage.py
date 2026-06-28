"""EV_JOB03 -- cohort lineage + exclusion ledger.

Runs the REAL match-level lineage builder (scripts/build_evaluation_cohort_lineage.py): one row per
fixture with explicit stage columns (raw_corpus -> ... -> loco_evaluation_population), every present->absent
transition carrying exactly one allowed drop reason. Records the reconstructed funnel + drop-reason counts
+ integrity flags (allowed_reasons_only / no_silent_disappearance) into the run-dir.

The independent unit is the MATCH. This job is the spine of the WHY-58 question.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev


def main():
    res = _ev.run_builder("scripts/build_evaluation_cohort_lineage.py")
    lin = _ev.read_ref_json("evaluation_cohort_lineage.json")
    if lin is None:
        _ev.emit("data_insufficient",
                 reason=f"lineage not produced (rc={res['returncode']}): {res['stderr_tail']}")
        return
    meta = lin.get("meta", {})
    fs = meta.get("funnel_summary", {})
    funnel = meta.get("funnel_match_level", {})
    integrity_ok = bool(meta.get("allowed_reasons_only") and meta.get("no_silent_disappearance"))
    _ev.write_json("ev_cohort_lineage_summary.json", {
        "builder_returncode": res["returncode"],
        "funnel_match_level": funnel, "funnel_summary": fs,
        "drop_reason_counts": meta.get("drop_reason_counts", {}),
        "allowed_reasons_only": meta.get("allowed_reasons_only"),
        "no_silent_disappearance": meta.get("no_silent_disappearance"),
        "on_disk_event_json_count": meta.get("on_disk_event_json_count"),
        "lineage_csv": "data/reference/evaluation_cohort_lineage.csv",
        "exclusion_ledger_csv": "data/reference/cohort_exclusion_ledger.csv",
        "utc": _ev.utc(), "labels": _ev.LABELS,
    })
    if not integrity_ok:
        _ev.emit("failed",
                 reason=f"lineage integrity breach: allowed_reasons_only="
                        f"{meta.get('allowed_reasons_only')} "
                        f"no_silent_disappearance={meta.get('no_silent_disappearance')} "
                        f"bad_reasons={meta.get('bad_reasons')} unexplained={meta.get('unexplained_drops')}")
        return
    _ev.emit("complete",
             reason=f"lineage built: exact_bridge={fs.get('exact_bridge_population')} -> "
                    f"residual={fs.get('residual_population')} (drop missing_statsbomb_events="
                    f"{fs.get('dropped_missing_statsbomb_events')}); forward_chain="
                    f"{fs.get('primary_evaluation_population')} loco={fs.get('loco_evaluation_population')}; "
                    f"integrity_ok={integrity_ok}",
             state_updates={"funnel_exact_bridge": fs.get("exact_bridge_population"),
                            "funnel_residual": fs.get("residual_population"),
                            "funnel_forward_chain": fs.get("primary_evaluation_population"),
                            "funnel_loco": fs.get("loco_evaluation_population"),
                            "dropped_missing_statsbomb_events": fs.get("dropped_missing_statsbomb_events"),
                            "lineage_integrity_ok": integrity_ok})


main()
