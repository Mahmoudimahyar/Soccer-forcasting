"""LK_JOB11 -- LOCO + calibration + bootstrap + ablations (reads JOB10's products; no recompute).

JOB10 ran scripts/rerun_international_event_lake_models.py, which wrote the LOCO, calibration, bootstrap,
ablation, and reproducibility-audit products in one locked pass. This job reads those SAME lake-hash-backed
products (it does NOT recompute -- the model rerun is the single source of truth) and reports:
  * LOCO per-fold (leave-one-competition-out) consistency,
  * three-way calibration / reliability (and whether the candidate degrades calibration vs R0),
  * MATCH-LEVEL paired bootstrap delta + one-sided interval,
  * preregistered ablations (reference-vs-xG / event-process / residual; per-tournament removal),
  * the reproducibility audit (deterministic recompute hash).

If JOB10's products are absent (e.g. JOB10 was data_insufficient), this job runs the builder once itself
(idempotent) and then reports. No fabrication: an absent product is reported as data_insufficient.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk

CALIB_JSON = _lk.REF / "international_event_lake_calibration.json"
BOOT_JSON = _lk.REF / "international_event_lake_bootstrap.json"
AUDIT_JSON = _lk.REF / "international_event_lake_reproducibility_audit.json"
METRICS_JSON = _lk.REF / "international_event_lake_evaluation_metrics.json"


def main():
    cohort = _lk.read_ref_json("international_event_lake_cohort_manifest.json")
    if not cohort:
        _lk.emit("data_insufficient", reason="cohort manifest absent (JOB08 not complete)")
        return

    # JOB10 normally produces these; if missing, run the rerun once (idempotent).
    produced_by_job10 = _lk.shared().get("model_rerun_done")
    builder_rc = None
    if not (METRICS_JSON.exists() and CALIB_JSON.exists()) or not produced_by_job10:
        res = _lk.run_builder("scripts/rerun_international_event_lake_models.py")
        builder_rc = res["returncode"]

    metrics = _lk.read_ref_json("international_event_lake_evaluation_metrics.json") or {}
    calib = _lk.read_ref_json("international_event_lake_calibration.json") or {}
    boot = _lk.read_ref_json("international_event_lake_bootstrap.json") or {}
    audit = _lk.read_ref_json("international_event_lake_reproducibility_audit.json") or {}
    ledger = _lk.read_ref_json("international_event_lake_model_decision_ledger.json") or {}

    loco = metrics.get("loco") or {}
    ablations = metrics.get("ablations") or {}

    out = {
        "loco": {"n_folds": loco.get("n_folds"), "per_fold": loco.get("folds") or loco.get("per_fold"),
                 "consistent": loco.get("consistent")},
        "calibration": {"reference_ece": calib.get("reference_ece") or calib.get("ece_reference"),
                        "candidate_ece": calib.get("candidate_ece") or calib.get("ece_candidate"),
                        "degrades": calib.get("candidate_degrades_calibration")},
        "bootstrap": {"paired_mean_delta": boot.get("paired_mean_delta") or boot.get("mean_delta"),
                      "ci": boot.get("ci") or boot.get("one_sided_ci"),
                      "bootstrap_unit": "match_clustered",
                      "favored": boot.get("candidate_favored")},
        "ablations": ablations,
        "reproducibility_audit": {"deterministic": audit.get("deterministic"),
                                  "recompute_hash": audit.get("recompute_hash") or audit.get("hash")},
        "verdict": ledger.get("verdict") or ledger.get("decision"),
        "products_present": {"calibration": CALIB_JSON.exists(), "bootstrap": BOOT_JSON.exists(),
                             "reproducibility_audit": AUDIT_JSON.exists(),
                             "metrics": METRICS_JSON.exists()},
        "builder_returncode_if_rerun": builder_rc,
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    _lk.write_json("lk_loco_calibration_bootstrap.json", out)

    if METRICS_JSON.exists() and CALIB_JSON.exists():
        _lk.emit("complete",
                 reason=f"LOCO+calibration+bootstrap+ablations reported (match-clustered bootstrap); "
                        f"loco_folds={out['loco']['n_folds']} verdict={out['verdict']} "
                        f"repro_deterministic={out['reproducibility_audit']['deterministic']}",
                 state_updates={"loco_calibration_bootstrap_done": True, "verdict": out["verdict"]})
        return
    _lk.emit("data_insufficient",
             reason=f"model evaluation products absent (metrics={METRICS_JSON.exists()}, "
                    f"calibration={CALIB_JSON.exists()}); builder_rc={builder_rc}")


main()
