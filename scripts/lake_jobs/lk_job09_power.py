"""LK_JOB09 -- MATCH-LEVEL statistical power analysis (Phase 5).

Invokes the EXISTING real builder scripts/run_international_event_lake_power_analysis.py. The independent
unit is the MATCH, never the snapshot: every snapshot of a match moves together, a match contributes a
SINGLE per-match mean-RPS value, and all resampling is MATCH-LEVEL clustered. The empirical noise template
is the REAL per-match paired delta (e7 minus e2/R0) from a LOCO run of the locked event-process families on
the lake cohort, centered to zero mean. Products: international_event_lake_power_analysis.json +
international_event_lake_minimum_evidence_requirements.json + report.

Records observed M (eligible matches), the detectable effect at the observed M, and the minimum-evidence
match counts. Match-level (clustered) only -- adding snapshots to the same matches does not buy power.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk

PA_JSON = _lk.REF / "international_event_lake_power_analysis.json"


def main():
    # needs a cohort
    cohort = _lk.read_ref_json("international_event_lake_cohort_manifest.json")
    if not cohort:
        _lk.emit("data_insufficient", reason="cohort manifest absent (JOB08 not complete)")
        return

    res = _lk.run_builder("scripts/run_international_event_lake_power_analysis.py")
    last = res.get("last_json") or {}
    pa = _lk.read_ref_json("international_event_lake_power_analysis.json") or {}
    mer = _lk.read_ref_json("international_event_lake_minimum_evidence_requirements.json") or {}

    observed_M = last.get("observed_M") or pa.get("observed_M_matches")

    out = {
        "builder_ok": res["ok"], "builder_returncode": res["returncode"],
        "observed_M_matches": observed_M,
        "bootstrap_unit": "match_clustered",
        "power_summary": {k: pa.get(k) for k in (
            "observed_M_matches", "detectable_effect_at_observed_M", "power_curve",
            "min_matches_for_target_effect", "reference_model", "candidate_model")},
        "minimum_evidence_requirements": mer,
        "manifest_present": PA_JSON.exists(),
        "builder_stderr_tail": res.get("stderr_tail"),
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    _lk.write_json("lk_power.json", out)

    if PA_JSON.exists() and res["ok"]:
        _lk.emit("complete",
                 reason=f"match-level power: observed_M={observed_M} (match-clustered; snapshots do not "
                        f"buy power)",
                 state_updates={"power_observed_M": observed_M, "power_done": True})
        return
    _lk.emit("data_insufficient",
             reason=f"power analysis not produced (rc={res['returncode']}); "
                    f"stderr={res.get('stderr_tail')}")


main()
