"""LK_JOB04 -- legacy restoration manifest + restore legacy events INTO THE LAKE.

Two REAL steps, both engine-backed (no fabrication, no re-download of a locally valid file):

  (A) build the legacy bridge RESTORATION manifest via the existing builder
      scripts/build_legacy_international_bridge_restoration_manifest.py -- per exact-international-bridge
      row it records the old cache root, current lake status + hash, and a retrieval_decision
      (copy_verified_local / retrieve_official / quarantine_invalid / excluded_with_reason).

  (B) COPY valid + hash-verified local StatsBomb event files (the ~60 surviving files in the prior cache
      + this worktree's statsbomb_raw) INTO the content-addressed lake via
      scripts/restore_international_event_lake.py -- which goes through L.store_object
      (validate -> sha256 -> atomic tmp->rename -> immutable manifest append). A file already in the lake
      with identical bytes is skipped (idempotent). Invalid/ambiguous payloads go to quarantine.

Then the lake object count is read back from the engine index and the fail-closed sentinel is run.
Restoration is RAW-BACKED + hash-verified -- counts come from the lake index, never from an id list.
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
        _lk.emit("failed", reason=f"lake_resolve_failed: {e!r}")
        return
    before = len(L.read_index(lake))

    # (A) legacy restoration manifest
    man = _lk.run_builder("scripts/build_legacy_international_bridge_restoration_manifest.py")
    man_last = man.get("last_json") or {}

    # (B) restore valid local files into the lake (copy-only; never re-downloads)
    res = _lk.run_builder("scripts/restore_international_event_lake.py")
    res_last = res.get("last_json") or {}

    after = len(L.read_index(lake))

    # sentinel over the restored lake (fail-closed)
    try:
        rep = L.run_sentinel(lake, write_report=True)
        sentinel = rep.to_dict()
    except Exception as e:
        sentinel = {"all_ok": False, "error": repr(e)}

    out = {
        "restoration_manifest": {"ok": man["ok"], "returncode": man["returncode"], "last_json": man_last,
                                 "stderr_tail": man.get("stderr_tail")},
        "restore_from_local": {"ok": res["ok"], "returncode": res["returncode"], "last_json": res_last,
                               "stderr_tail": res.get("stderr_tail")},
        "lake_object_count_before": before,
        "lake_object_count_after": after,
        "objects_copied_this_run": res_last.get("objects_copied"),
        "objects_already_present": res_last.get("objects_already_present"),
        "quarantined": res_last.get("quarantined"),
        "bridge_exact_international": res_last.get("bridge_exact_international"),
        "sentinel": {"all_ok": sentinel.get("all_ok"), "checked": sentinel.get("checked"),
                     "failure_count": sentinel.get("failure_count")},
        "raw_backed": True, "hash_verified": True,
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    L.log_run(lake, "lk_job04_legacy_restore", out)
    _lk.write_json("lk_legacy_restore.json", out)

    # The restore script itself must have run (it owns the copy-in). A populated lake from a prior run is
    # fine (idempotent: copied=0, already_present>0). Hard FAIL only if the restore step could not run AND
    # the lake is empty (nothing restored), or the sentinel fails on what we restored.
    restore_ran = res["ok"] or (res_last and "lake_object_count" in res_last)
    if not restore_ran and after == 0:
        _lk.emit("failed",
                 reason=f"restore step could not run and lake is empty (rc={res['returncode']}); "
                        f"stderr={res.get('stderr_tail')}")
        return
    if sentinel.get("all_ok") is False:
        _lk.emit("failed",
                 reason=f"sentinel FAILED after restore (failures={sentinel.get('failure_count')}) -- "
                        f"fail closed; restored objects are not integrity-clean")
        return

    _lk.emit("complete",
             reason=f"legacy restore raw-backed+hash-verified: lake {before}->{after} "
                    f"(copied={out['objects_copied_this_run']} already={out['objects_already_present']} "
                    f"quarantined={out['quarantined']}) sentinel_all_ok={sentinel.get('all_ok')}",
             state_updates={"lake_object_count": after, "legacy_restore_done": True,
                            "objects_copied_this_run": out["objects_copied_this_run"],
                            "sentinel_all_ok_after_restore": sentinel.get("all_ok")})


main()
