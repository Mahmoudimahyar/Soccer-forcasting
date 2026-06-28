"""LK_JOB10 -- strict forward-chain evaluation of the preregistered model families.

Invokes the EXISTING real builder scripts/rerun_international_event_lake_models.py, which reuses ONLY the
preregistered model families (remaining-time Poisson REFERENCE e2/R0, time+score e1, xG-state e3, full
event-process intensity e4..e7, calibrated hybrid e8/e9, residual/selective-correction -- NO new features /
search / neural / market) and the LOCKED harness verbatim:
  * forward-chaining by tournament (kickoff order)   event_process.eval.forward_chain_wdl
  * leave-one-competition-out (LOCO)                  event_process.eval.loco_wdl
  * match-level PAIRED bootstrap (unit = MATCH)       event_process.eval.paired_bootstrap_delta
  * three-way calibration / reliability
The builder writes the decision ledger + evaluation_metrics + calibration + bootstrap + reproducibility
audit in ONE pass. This job runs that pass and reports the FORWARD-CHAIN result + the candidate verdict.

The builder is idempotent (it recomputes from the lake-hash-backed cohort). JOB11 reads the SAME products
without recomputing (shared state). The candidate gate is the LOCKED rule: a candidate is accepted only if
strictly better than R0 on the composite, no calibration degradation, favorable in >=75% of folds,
bootstrap-favored, LOCO-consistent, and adequately covered; otherwise reference_only / rejected.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk

METRICS_JSON = _lk.REF / "international_event_lake_evaluation_metrics.json"
LEDGER_JSON = _lk.REF / "international_event_lake_model_decision_ledger.json"


def main():
    cohort = _lk.read_ref_json("international_event_lake_cohort_manifest.json")
    if not cohort:
        _lk.emit("data_insufficient", reason="cohort manifest absent (JOB08 not complete)")
        return
    n_wdl = (cohort.get("subcohort_counts") or {}).get("wdl")
    if not n_wdl:
        _lk.emit("data_insufficient",
                 reason=f"no WDL-eligible matches in cohort (wdl={n_wdl}) -- cannot evaluate")
        return

    res = _lk.run_builder("scripts/rerun_international_event_lake_models.py")
    last = res.get("last_json") or {}
    metrics = _lk.read_ref_json("international_event_lake_evaluation_metrics.json") or {}
    ledger = _lk.read_ref_json("international_event_lake_model_decision_ledger.json") or {}

    fwd = metrics.get("forward_chain") or last.get("forward_chain") or {}
    verdict = (ledger.get("verdict") or last.get("verdict")
               or (ledger.get("decision") if isinstance(ledger, dict) else None))

    out = {
        "builder_ok": res["ok"], "builder_returncode": res["returncode"],
        "n_wdl_eligible": n_wdl,
        "reference_model": metrics.get("reference_model") or last.get("reference_model"),
        "forward_chain": fwd,
        "candidate_verdict": verdict,
        "metrics_present": METRICS_JSON.exists(), "ledger_present": LEDGER_JSON.exists(),
        "protocols": ["forward_chain_wdl", "loco_wdl", "paired_bootstrap_delta", "calibration"],
        "preregistered_families_only": True, "no_new_features": True,
        "builder_stderr_tail": res.get("stderr_tail"),
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    _lk.write_json("lk_forward_chain_eval.json", out)

    if METRICS_JSON.exists() and res["ok"]:
        _lk.emit("complete",
                 reason=f"forward-chain eval done on {n_wdl} WDL matches; reference={out['reference_model']}; "
                        f"candidate_verdict={verdict} (locked rule; preregistered families only)",
                 state_updates={"model_rerun_done": True, "candidate_verdict": verdict,
                                "n_wdl_eligible": n_wdl})
        return
    _lk.emit("data_insufficient",
             reason=f"model rerun did not produce metrics (rc={res['returncode']}); "
                    f"stderr={res.get('stderr_tail')}")


main()
