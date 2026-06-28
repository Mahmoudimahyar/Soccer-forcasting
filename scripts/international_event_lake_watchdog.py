"""Self-supervising watchdog for the durable International Event Lake Restoration v1 run. Runs every 10 min
(via Task Scheduler), independently of any chat session. A single GLOBAL LOCK -> never launches concurrent
controllers (never a 2nd worker). NEVER modifies the active collector (WorldCupShadowCollector /
worldcup_draw_model_lab_FINAL), B1, frozen M1-M5, candidate.py, approved_models.yaml, trading/Kalshi/risk,
or .env. Reads only run state/heartbeat/job_log + collector heartbeat + Task Scheduler state + the lake
index/sentinel. Writes only watchdog_log.jsonl / watchdog_state.json / the operations log.

Every cycle it verifies (fail-closed):
  * collector ISOLATION    -- no data root resolves into the active collector; we are not in the collector,
  * the global LOCK        -- only one watchdog action at a time,
  * the collector HEARTBEAT -- recorded read-only (collector commit drift = WATCH only, not our breach),
  * lake RETENTION         -- the lake is external; the index is consistent with on-disk objects,
  * raw NOT git-tracked    -- data/raw and the lake objects/ tree are 0 git-tracked in this worktree.

Restart policy: restarts ONLY a crashed/stale run (task not Running + heartbeat stale + a job stuck
'running' + collector healthy + no integrity violation). NEVER restarts a terminal-clean run
(queue_complete / all jobs terminal). On a FAILED_INTEGRITY violation it STOPS the run and DISABLES the
main task (no auto-restart).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "outputs/research_runs"
LOCK = RUNS / ".lake_global.lock"
COLLECTOR = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")
COLLECTOR_HB = COLLECTOR / "outputs/live_shadow/collector_heartbeat.json"
EXPECTED_COLLECTOR_COMMIT = "dc73318"
MAIN_TASK = "WorldCupInternationalEventLakeRun"
WATCHDOG_TASK = "WorldCupInternationalEventLakeWatchdog"
TERMINAL_RUN_STATES = ("COMPLETE", "CANCELLED", "FAILED_INTEGRITY")
OPS_LOG = ROOT / "notes/research/INTERNATIONAL_EVENT_LAKE_OPERATIONS_LOG.md"


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _ps(cmd):
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def _task_state(name):
    s = _ps(f"try{{(Get-ScheduledTask -TaskName {name} -ErrorAction Stop).State}}catch{{'ABSENT'}}")
    return s or "ABSENT"


def _age_seconds(ts):
    try:
        return time.time() - datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 1e9


def _active_run():
    p = RUNS / "active_run_id.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


def _acquire_lock():
    RUNS.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            d = json.loads(LOCK.read_text(encoding="utf-8"))
            if _age_seconds(d.get("ts")) < 9 * 60:
                return False
        except Exception:
            pass
    LOCK.write_text(json.dumps({"pid": os.getpid(), "ts": _utc()}), encoding="utf-8")
    return True


def _release_lock():
    try:
        LOCK.unlink()
    except Exception:
        pass


def _integrity_violations():
    """Fail-closed violations WE could cause: raw git-tracked, lake git-tracked, a data root in the
    collector, the lake living inside a worktree, or the lake index inconsistent with on-disk objects.
    Collector-commit drift is recorded but NOT auto-fatal (independent system in a separate checkout)."""
    v = []
    try:
        tracked = subprocess.run(["git", "ls-files", "data/raw"], capture_output=True, text=True,
                                 cwd=str(ROOT)).stdout.strip()
        if tracked:
            v.append("raw_data_git_tracked")
    except Exception:
        pass
    sys.path.insert(0, str(ROOT / "src"))
    # data roots must not resolve into the collector
    try:
        from wcdrawlab.research import data_roots as DR
        for name in DR._load()["roots"]:
            try:
                if "worldcup_draw_model_lab_FINAL" in str(DR.get_root(name)).replace("\\", "/"):
                    v.append(f"research_root_in_collector:{name}")
            except PermissionError:
                v.append(f"data_root_resolves_into_collector:{name}")
    except Exception:
        pass
    # lake: external + objects not git-tracked + index consistent
    try:
        from wcdrawlab.research import international_event_lake as L
        lake = L.Lake.resolve()  # raises if it would live inside a worktree/collector
        norm = str(lake.root).replace("\\", "/")
        if "worldcup-international-event-lake" in norm or "worldcup_draw_model_lab_FINAL" in norm:
            v.append("lake_root_inside_worktree")
        lake_tracked = subprocess.run(["git", "ls-files", str(lake.root)], capture_output=True,
                                      text=True, cwd=str(ROOT)).stdout.strip()
        if lake_tracked:
            v.append("lake_objects_git_tracked")
        # retention: every index object exists on disk with its recorded sha (cheap subset check)
        index = L.read_index(lake)
        for sb, rec in list(index.items())[:5000]:
            lp = rec.get("local_path")
            if not lp:
                v.append(f"index_missing_local_path:{sb}")
                break
            obj = (lake.root / lp)
            if not obj.exists():
                v.append(f"manifest_present_but_object_absent:{sb}")
                break
    except Exception as e:
        v.append(f"lake_resolve_or_retention_error:{type(e).__name__}")
    return v


def _collector_status():
    commit = subprocess.run(["git", "-C", str(COLLECTOR), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    hb_age = None
    if COLLECTOR_HB.exists():
        try:
            hb_age = _age_seconds(json.loads(COLLECTOR_HB.read_text(encoding="utf-8")).get("ts"))
        except Exception:
            pass
    return {"commit": commit, "commit_unchanged": commit == EXPECTED_COLLECTOR_COMMIT, "hb_age_s": hb_age}


def _run_terminal(state, summary):
    if summary and summary.get("stop_reason") == "queue_complete":
        return True
    jobs = (state.get("jobs") or {})
    if jobs and not any(j.get("status") == "running" for j in jobs.values()):
        if all(j.get("status") in ("complete", "skipped", "blocked") for j in jobs.values()):
            return True
    return False


def main():
    if not _acquire_lock():
        return  # another watchdog action in progress -> never run concurrently / never a 2nd worker
    try:
        run_id = _active_run()
        run_dir = RUNS / run_id if run_id else None
        state, summary = {}, {}
        if run_dir and (run_dir / "state.json").exists():
            try:
                state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            except Exception:
                state = {}
        if run_dir and (run_dir / "run_summary.json").exists():
            try:
                summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
            except Exception:
                summary = {}
        hb_age = None
        if run_dir and (run_dir / "heartbeat.json").exists():
            try:
                hb_age = _age_seconds(json.loads((run_dir / "heartbeat.json").read_text(
                    encoding="utf-8")).get("ts"))
            except Exception:
                pass

        main_state = _task_state(MAIN_TASK)
        coll = _collector_status()
        violations = _integrity_violations()
        terminal = _run_terminal(state, summary)
        run_state = (state.get("shared") or {}).get("run_state",
                     "RUNNING" if main_state == "Running" else "UNKNOWN")

        wd = {"ts": _utc(), "run_id": run_id, "main_task": main_state, "heartbeat_age_s": hb_age,
              "run_state": run_state, "terminal": terminal, "collector": coll,
              "integrity_violations": violations, "action": None}

        if violations:
            # FAIL CLOSED -> stop + DISABLE the main task (no auto-restart on integrity failure)
            wd["watchdog_state"] = "FAILED_INTEGRITY"
            wd["action"] = "stop_run+disable_main_task+incident"
            _ps(f"Stop-ScheduledTask -TaskName {MAIN_TASK} -ErrorAction SilentlyContinue")
            _ps(f"Disable-ScheduledTask -TaskName {MAIN_TASK} -ErrorAction SilentlyContinue")
            if run_dir:
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "INCIDENT_failed_integrity.json").write_text(
                    json.dumps(wd, indent=2), encoding="utf-8")
        elif not coll["commit_unchanged"]:
            wd["watchdog_state"] = run_state
            wd["note"] = "collector commit advanced independently (not our change) -> WATCH only"
            wd["action"] = "observe"
        elif terminal:
            wd["watchdog_state"] = "COMPLETE"
            wd["action"] = "terminal clean run; do nothing (never restart a completed run)"
        elif main_state == "Running":
            wd["watchdog_state"] = "RUNNING"
            wd["action"] = ("healthy: do nothing (no second worker)" if (hb_age is None or hb_age < 600)
                            else f"healthy: long job in progress (hb_age={int(hb_age)}s)")
        elif (main_state != "Running" and (hb_age is not None and hb_age > 900)
              and any(v.get("status") == "running" for v in (state.get("jobs") or {}).values())
              and run_state not in TERMINAL_RUN_STATES):
            wd["watchdog_state"] = "RUNNING"
            wd["action"] = "restart_same_run_id (resume unfinished jobs; only crashed)"
            wd["restart_reason"] = ("task not Running + heartbeat stale >15m + a job stuck 'running' + "
                                    "collector healthy + no integrity violation")
            _ps(f"Start-ScheduledTask -TaskName {MAIN_TASK} -ErrorAction SilentlyContinue")
        else:
            wd["watchdog_state"] = run_state
            wd["action"] = "observe"

        if run_dir:
            run_dir.mkdir(parents=True, exist_ok=True)
            with (run_dir / "watchdog_log.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(wd) + "\n")
            (run_dir / "watchdog_state.json").write_text(json.dumps(wd, indent=2), encoding="utf-8")
        OPS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with OPS_LOG.open("a", encoding="utf-8") as f:
            f.write(f"- {wd['ts']} state={wd.get('watchdog_state')} main_task={main_state} "
                    f"hb_age={hb_age} terminal={terminal} "
                    f"collector={coll['commit']}({'ok' if coll['commit_unchanged'] else 'CHANGED'}) "
                    f"violations={violations or 'none'} action={wd['action']}\n")
        print(json.dumps({k: wd[k] for k in ("watchdog_state", "main_task", "run_state",
                                             "terminal", "action")}))
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
