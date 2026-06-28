"""LK_JOB07 -- event-lake quality + retention audit. FAIL CLOSED.

Runs, in-process via the canonical engine and the existing audit/retention scripts:
  (A) the fail-closed INTEGRITY SENTINEL over EVERY indexed object (object present, bytes hash to recorded
      sha256, filename == sha256, non-empty, valid JSON, non-empty event list, not HTML/error, id resolves
      to exactly one EXACT international bridge row, object under the registered objects/ root, no orphan).
  (B) the RETENTION verifier (scripts/verify_international_event_lake_retention.py): every manifest line
      still references an existing object with the recorded sha256; the index is a subset of manifest
      history; the lake is external to every git worktree; no indexed object missing on disk.
  (C) ISOLATION re-assertion: this worktree is not the collector; no data root resolves into the collector;
      the lake objects/ tree is 0 git-tracked in this worktree; raw/ is 0 git-tracked.

ANY failure in (A)/(B)/(C) is a HARD `failed` (fail closed). On failure the watchdog must NOT auto-restart
(FAILED_INTEGRITY); the durable run stops here so a corrupt lake never feeds evaluation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk


def main():
    L = _lk.lake_engine()
    try:
        lake = L.Lake.resolve()
    except Exception as e:
        _lk.emit("failed", reason=f"FAILED_INTEGRITY: lake_resolve_failed: {e!r}")
        return

    # (A) sentinel ----------------------------------------------------------------------------------
    try:
        rep = L.run_sentinel(lake, write_report=True)
        sentinel = rep.to_dict()
    except Exception as e:
        sentinel = {"all_ok": False, "checked": 0, "failure_count": -1, "error": repr(e)}
    sentinel_ok = bool(sentinel.get("all_ok"))

    # (B) retention verifier ------------------------------------------------------------------------
    ret = _lk.run_builder("scripts/verify_international_event_lake_retention.py")
    ret_last = ret.get("last_json") or {}
    retention_ok = bool(ret["ok"]) and (ret_last.get("all_ok", True) is not False)

    # (C) isolation re-assertion --------------------------------------------------------------------
    inside_collector = _lk.COLLECTOR_FORBIDDEN in str(_lk.ROOT).replace("\\", "/")
    root_in_collector = _lk.roots_resolving_into_collector()
    raw_tracked = bool(_lk.raw_git_tracked())
    lake_tracked = bool(_lk.lake_objects_git_tracked())
    norm = str(lake.root).replace("\\", "/")
    lake_external = ("worldcup-international-event-lake" not in norm
                     and _lk.COLLECTOR_FORBIDDEN not in norm)
    isolation_ok = (not inside_collector and not root_in_collector and not raw_tracked
                    and not lake_tracked and lake_external)

    # quality stats (raw-backed; counts come from the engine index, never an id list)
    index = L.read_index(lake)
    n_obj = len(index)
    n_xg = sum(1 for r in index.values() if r.get("xg_available"))
    n_poss = sum(1 for r in index.values() if r.get("possession_available"))
    n_loc = sum(1 for r in index.values() if r.get("location_available"))
    total_events = sum(int(r.get("event_count") or 0) for r in index.values())

    out = {
        "sentinel": sentinel, "sentinel_ok": sentinel_ok,
        "retention": {"ok": retention_ok, "returncode": ret["returncode"], "last_json": ret_last,
                      "stderr_tail": ret.get("stderr_tail")},
        "isolation": {"ok": isolation_ok, "inside_collector": inside_collector,
                      "roots_in_collector": root_in_collector, "raw_git_tracked": raw_tracked,
                      "lake_git_tracked": lake_tracked, "lake_external": lake_external},
        "quality": {"lake_objects": n_obj, "objects_with_xg": n_xg,
                    "objects_with_possession": n_poss, "objects_with_location": n_loc,
                    "total_events": total_events,
                    "xg_fraction": round(n_xg / n_obj, 4) if n_obj else None},
        "fail_closed": True, "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    _lk.write_json("lk_quality_retention_audit.json", out)
    L.log_run(lake, "lk_job07_quality_retention_audit", out)

    all_ok = sentinel_ok and retention_ok and isolation_ok
    if not all_ok:
        _lk.emit("failed",
                 reason=f"FAILED_INTEGRITY: sentinel_ok={sentinel_ok} "
                        f"(failures={sentinel.get('failure_count')}) retention_ok={retention_ok} "
                        f"isolation_ok={isolation_ok} (inside_collector={inside_collector}, "
                        f"roots_in_collector={root_in_collector}, raw_tracked={raw_tracked}, "
                        f"lake_tracked={lake_tracked}, lake_external={lake_external}) -- fail closed",
                 state_updates={"lake_integrity_ok": False})
        return

    _lk.emit("complete",
             reason=f"lake integrity CLEAN: sentinel_ok=True (checked={sentinel.get('checked')}) "
                    f"retention_ok=True isolation_ok=True objects={n_obj} xg={n_xg} events={total_events}",
             state_updates={"lake_integrity_ok": True, "lake_objects_audited": n_obj,
                            "objects_with_xg": n_xg})


main()
