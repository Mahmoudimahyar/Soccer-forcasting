"""EV_JOB05 -- reproducibility audit.

Consolidates the cross-evaluation reproducibility classification (data/reference/
evaluation_reproducibility_audit.json -- 7 major out-of-sample evaluations classified across six
traceability dimensions) and CONFIRMS the one headline metric that was independently recomputed cold
in JOB04 (residual forward-chain / LOCO R0 RPS). Records the reproducibility distribution + the
independently-verified headline. No fitting, no network. If the reproducibility artifact is absent the
job emits data_insufficient (it never fabricates a classification).
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev


def main():
    repro = _ev.read_ref_json("evaluation_reproducibility_audit.json")
    audit58 = _ev.read_ref_json("residual_58_match_audit.json")
    if repro is None:
        _ev.emit("data_insufficient",
                 reason="evaluation_reproducibility_audit.json absent (no local reproducibility "
                        "classification on disk); cannot synthesize without fabricating")
        return

    evals = repro.get("evaluations") or repro.get("rows") or []
    class_counts = dict(Counter((e.get("classification") or e.get("reproducibility")
                                 or "unknown") for e in evals)) if evals else {}

    # the one cold-recomputed headline (from JOB04's independent reconstruction)
    v = (audit58 or {}).get("verdict", {})
    cmp = (audit58 or {}).get("comparison", {})
    headline = {
        "evaluation": "residual_goal_intensity_wdl",
        "forward_chain_rps_reproduced": bool(v.get("forward_chain_rps_reproduced")),
        "loco_rps_reproduced": bool(v.get("loco_rps_reproduced")),
        "fc_rps_recomputed": ((cmp.get("forward_chain_pooled_rps") or {}).get("recomputed")),
        "fc_rps_reported": ((cmp.get("forward_chain_pooled_rps") or {}).get("reported")),
        "method": "cold reimplementation of W2 R0 from raw CSV columns (no package import)",
    } if audit58 else {"note": "58-match audit artifact absent; headline recompute unconfirmed here"}

    _ev.write_json("ev_reproducibility_summary.json", {
        "n_evaluations": len(evals), "classification_counts": class_counts,
        "independently_recomputed_headline": headline,
        "source": "data/reference/evaluation_reproducibility_audit.json",
        "utc": _ev.utc(), "labels": _ev.LABELS,
    })
    _ev.emit("complete",
             reason=f"reproducibility: {len(evals)} evaluations classified {class_counts}; "
                    f"headline residual FC RPS reproduced="
                    f"{headline.get('forward_chain_rps_reproduced')}",
             state_updates={"reproducibility_n_evaluations": len(evals),
                            "reproducibility_classes": class_counts,
                            "headline_fc_rps_reproduced": headline.get("forward_chain_rps_reproduced")})


main()
