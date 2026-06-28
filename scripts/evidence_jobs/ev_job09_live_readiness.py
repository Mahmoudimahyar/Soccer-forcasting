"""EV_JOB09 -- live-readiness matrix.

Runs the REAL live-readiness builder (scripts/build_live_readiness_matrix.py), which classifies the
in-play feature families by how close each is to LIVE point-in-time use, grounded ONLY in local validated
artifacts. The central fact it encodes: every offline artifact is built from POST-HOC complete-match
event data with only a match-clock coordinate -- there is NO wall-clock event-PUBLICATION timestamp on
any source -- so families separate into point_in_time_replay_possible (almost always true offline) vs
live_eligible (needs measured provider latency + rights + schema parity). Records the readiness-class
distribution. Makes NO purchase recommendation and NO market claim.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev


def main():
    res = _ev.run_builder("scripts/build_live_readiness_matrix.py")
    matrix = _ev.read_ref_json("live_readiness_matrix.json")
    if matrix is None:
        _ev.emit("data_insufficient",
                 reason=f"live-readiness matrix not produced (rc={res['returncode']}): "
                        f"{res['stderr_tail']}")
        return
    fams = matrix.get("families") or matrix.get("rows") or []
    class_counts = dict(Counter((f.get("readiness_class") or f.get("classification")
                                 or "unknown") for f in fams)) if fams else {}
    n_live = sum(1 for f in fams if (f.get("live_eligible") is True))
    _ev.write_json("ev_live_readiness_summary.json", {
        "builder_returncode": res["returncode"],
        "n_families": len(fams), "readiness_class_counts": class_counts,
        "n_live_eligible_today": n_live,
        "central_fact": "no source carries a wall-clock event-publication timestamp; offline "
                        "match-clock replay != live eligibility",
        "utc": _ev.utc(), "labels": _ev.LABELS,
    })
    _ev.emit("complete",
             reason=f"live-readiness matrix: {len(fams)} families, classes={class_counts}, "
                    f"live_eligible_today={n_live}",
             state_updates={"live_readiness_families": len(fams),
                            "live_readiness_classes": class_counts,
                            "live_eligible_today": n_live})


main()
