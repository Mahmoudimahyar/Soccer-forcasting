"""EV_JOB02 -- research evidence registry.

Runs the REAL registry builder (scripts/build_research_evidence_registry.py), which writes one row per
major artifact across the prior research programs with a claim_status traced to a present file. This job
does not re-derive counts itself; it invokes the canonical builder (offline, read-only) and records the
registry summary (rows + claim_status distribution) into the run-dir. Honest data_insufficient if the
builder cannot produce a registry.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev


def main():
    res = _ev.run_builder("scripts/build_research_evidence_registry.py")
    reg = _ev.read_ref_json("research_evidence_registry.json")
    if reg is None and not res["ok"]:
        _ev.emit("data_insufficient",
                 reason=f"evidence registry not produced (rc={res['returncode']}): {res['stderr_tail']}")
        return
    # the canonical registry uses `records` (with `n_records` + `status_counts`); tolerate older `rows`.
    rows = ((reg or {}).get("records") or (reg or {}).get("rows")
            or (reg or {}).get("registry") or [])
    status_counts = (reg or {}).get("status_counts")
    if not status_counts:
        status_counts = dict(Counter(
            (r.get("claim_status") or r.get("status") or "unknown") for r in rows)) if rows else {}
    _ev.write_json("ev_evidence_registry_summary.json", {
        "builder_returncode": res["returncode"], "builder_last_json": res["last_json"],
        "n_rows": len(rows), "claim_status_counts": status_counts,
        "registry_file": "data/reference/research_evidence_registry.json",
        "utc": _ev.utc(), "labels": _ev.LABELS,
    })
    if not rows:
        _ev.emit("data_insufficient", reason="registry produced no rows",
                 state_updates={"evidence_registry_rows": 0})
        return
    _ev.emit("complete",
             reason=f"evidence registry built: {len(rows)} rows, claim_status={status_counts}",
             state_updates={"evidence_registry_rows": len(rows),
                            "evidence_claim_status": status_counts})


main()
