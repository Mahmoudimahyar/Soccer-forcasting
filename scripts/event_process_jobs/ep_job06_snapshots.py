"""EPJOB6 -- build the causal event-process SNAPSHOTS (intl exact-bridge + club auxiliary) by invoking
the deterministic builder scripts/build_event_process_snapshots.py. The builder is leakage-safe
(snapshot_features.events_up_to gate), regulation-only, club/intl-separated, and writes a build_manifest
with a leakage self-test. This job runs it, then re-asserts the manifest's self-test and the row counts.
If the StatsBomb event cache / bridge is absent (clean worktree), the builder returns data_insufficient
and this job emits an honest skip -- never a fake completion.

research_only / experimental. No network, no API.
"""
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ep_lib as L

ROOT = L.ROOT


def main():
    rd = L.run_dir()
    run_id = rd.name
    cmd = [sys.executable, str(ROOT / "scripts/build_event_process_snapshots.py"), "--run-id", run_id]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=28800)
    out = (p.stdout or "").strip()
    last = out.splitlines()[-1] if out else ""
    try:
        res = json.loads(last)
    except Exception:
        res = {}

    man_path = L.PROC / "build_manifest.json"
    if not man_path.exists():
        L.emit("data_insufficient",
               reason=f"snapshot build produced no manifest (StatsBomb cache/bridge likely absent); "
                      f"builder_status={res.get('status')} stderr={(p.stderr or '')[:200]}")
        return
    man = json.loads(man_path.read_text(encoding="utf-8"))
    intl = man.get("international", {})
    club = man.get("club", {})
    lk = man.get("leakage_self_test", {})

    n_snap = intl.get("n_snapshots", 0)
    n_wdl = intl.get("n_wdl_targets", 0)
    leak_ok = lk.get("all_ok")

    L.write_json("ep_snapshot_build.json", {
        "international": intl, "club": club, "leakage_self_test": lk,
        "engine_version": man.get("engine_version"), "utc": L.utc(),
    })

    if n_snap <= 0 or n_wdl <= 0:
        L.emit("data_insufficient",
               reason=f"no international snapshots/targets present (n_snap={n_snap} n_wdl={n_wdl}); "
                      f"event cache/bridge likely absent -- honest skip, not a false completion")
        return
    if leak_ok is False:
        L.emit("failed", reason=f"snapshot leakage self-test FAILED: {lk.get('violations')}")
        return
    L.emit("complete",
           reason=f"intl snapshots={n_snap} wdl_targets={n_wdl} club_snapshots={club.get('n_snapshots')} "
                  f"leakage_self_test_all_ok={leak_ok}",
           state_updates={"n_intl_snapshots": n_snap, "n_intl_wdl_targets": n_wdl,
                          "snapshot_leakage_ok": bool(leak_ok)})


main()
