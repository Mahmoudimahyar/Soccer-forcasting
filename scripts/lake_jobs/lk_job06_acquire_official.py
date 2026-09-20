"""LK_JOB06 -- acquire + validate MISSING official events INTO THE LAKE (the durable acquisition job).

This is the ONE job permitted to touch an external network, and ONLY the official StatsBomb Open Data
events endpoint (raw.githubusercontent.com/statsbomb/open-data), owned by the engine acquisition script
scripts/acquire_official_international_events.py:
  * Pass 1 -- copy a VALID + hash-verified local file into the lake (never re-download a locally valid one).
  * Pass 2 -- retrieve events/<sb_match_id>.json from the OFFICIAL source ONLY, <=4 concurrent,
    exponential backoff, <=2 retries, atomic tmp->rename, sha256, immutable manifest append. Invalid
    bodies are quarantined (fail-closed) and never indexed.

Every write goes through the engine (validate -> sha256 -> atomic -> manifest). After the run we read the
lake index back and list the EXACT sb_match_ids still missing. If matches remain genuinely missing after
the official source could not serve them, this job ends WAITING_FOR_OFFICIAL_SOURCE (honest -- no
fabrication, exact missing ids listed) so the durable run resumes them later. If everything is already in
the lake (idempotent restart), it completes immediately with no network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk


def _missing_ids(L, lake):
    index = L.read_index(lake)
    try:
        bridge = L.load_exact_bridge()
    except Exception:
        return None, None
    missing = sorted(sb for sb in bridge if str(sb) not in index)
    return missing, len(bridge)


def main():
    L = _lk.lake_engine()
    try:
        lake = L.Lake.resolve()
    except Exception as e:
        _lk.emit("failed", reason=f"lake_resolve_failed: {e!r}")
        return

    before = len(L.read_index(lake))
    missing_before, n_bridge = _missing_ids(L, lake)
    if missing_before is None:
        _lk.emit("data_insufficient", reason="exact bridge unavailable -- cannot determine missing ids")
        return

    # If nothing is missing, no network is needed (idempotent restart).
    if not missing_before:
        _lk.write_json("lk_acquire_official.json", {
            "lake_objects_before": before, "lake_objects_after": before,
            "missing_before": 0, "missing_after": 0, "network_used": False,
            "bridge_exact_international": n_bridge, "utc": _lk.utc(), "labels": _lk.LABELS})
        _lk.emit("complete",
                 reason=f"all {n_bridge} exact-bridge matches already in lake (no acquisition needed)",
                 state_updates={"lake_object_count": before, "missing_after": 0,
                                "acquire_network_used": False})
        return

    # Matches are missing -> attempt official acquisition (official-source-only, engine-owned).
    res = _lk.run_builder("scripts/acquire_official_international_events.py", args=["--allow-network"])
    last = res.get("last_json") or {}

    after = len(L.read_index(lake))
    missing_after, _ = _missing_ids(L, lake)
    actions = last.get("actions") or {}

    # sentinel over the acquired lake (fail-closed)
    try:
        rep = L.run_sentinel(lake, write_report=True)
        sentinel = rep.to_dict()
    except Exception as e:
        sentinel = {"all_ok": False, "error": repr(e)}

    out = {
        "builder_ok": res["ok"], "builder_returncode": res["returncode"],
        "bridge_exact_international": n_bridge,
        "lake_objects_before": before, "lake_objects_after": after,
        "missing_before": len(missing_before),
        "missing_after": len(missing_after) if missing_after is not None else None,
        "missing_after_ids": (missing_after or [])[:500],
        "actions": actions,
        "network_used": bool(last.get("network_enabled")),
        "official_source_only": _lk.OFFICIAL_HOST,
        "fetch_errors": actions.get("fetch_error"),
        "sentinel": {"all_ok": sentinel.get("all_ok"), "checked": sentinel.get("checked"),
                     "failure_count": sentinel.get("failure_count")},
        "builder_stderr_tail": res.get("stderr_tail"),
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    _lk.write_json("lk_acquire_official.json", out)

    if sentinel.get("all_ok") is False:
        _lk.emit("failed",
                 reason=f"sentinel FAILED after acquisition (failures={sentinel.get('failure_count')}) "
                        f"-- fail closed")
        return

    if missing_after:
        # genuinely unavailable from the official source after retries -> WAITING (list exact ids)
        _lk.emit("waiting_for_official_source",
                 reason=f"{len(missing_after)} exact-bridge matches still missing after official "
                        f"acquisition (rc={res['returncode']}, fetch_errors={actions.get('fetch_error')}); "
                        f"lake {before}->{after}; will resume. example_missing="
                        f"{(missing_after or [])[:15]}",
                 state_updates={"lake_object_count": after, "missing_after": len(missing_after),
                                "acquire_network_used": True,
                                "missing_after_ids_head": (missing_after or [])[:50]})
        return

    _lk.emit("complete",
             reason=f"acquisition complete: lake {before}->{after}, all {n_bridge} exact-bridge matches "
                    f"present (copied_local={actions.get('copied_local')} "
                    f"retrieved_official={actions.get('retrieved_official')} "
                    f"quarantined={actions.get('quarantined')}) sentinel_all_ok={sentinel.get('all_ok')}",
             state_updates={"lake_object_count": after, "missing_after": 0,
                            "acquire_network_used": True})


main()
