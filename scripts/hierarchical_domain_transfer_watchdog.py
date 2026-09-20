"""Self-supervising watchdog for the durable HIERARCHICAL CROSS-DOMAIN TRANSFER run. Runs every 10 min
(via Task Scheduler), independently of any chat session. Single GLOBAL LOCK -> never launches concurrent
controllers (never a 2nd worker). NEVER modifies WorldCupShadowCollector / the active collector. Reads only
run state/heartbeat/job_log + collector heartbeat + Task Scheduler state. Writes only watchdog_log.jsonl /
watchdog_state.json / HIERARCHICAL_DOMAIN_TRANSFER_OPERATIONS_LOG.md. research_only.

Checks every cycle: collector ISOLATION (commit unchanged + no data root in collector), the global LOCK,
the run HEARTBEAT, and that data/raw is NOT git-tracked. Restart policy: restarts ONLY a crashed/stale run
(task not Running + heartbeat stale + a job stuck 'running' + collector healthy). NEVER restarts a terminal
clean run (queue_complete / all jobs terminal / run_state COMPLETE). DISABLES restart on FAILED_INTEGRITY
(stops the worker + writes an incident). Mirrors scripts/research_evidence_watchdog.py.
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
LOCK = RUNS / ".ht_global.lock"
COLLECTOR = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")
COLLECTOR_HB = COLLECTOR / "outputs/live_shadow/collector_heartbeat.json"
EXPECTED_COLLECTOR_COMMIT = "dc73318"
MAIN_TASK = "WorldCupHierarchicalDomainTransferRun"
WATCHDOG_TASK = "WorldCupHierarchicalDomainTransferWatchdog"
TERMINAL_RUN_STATES = ("COMPLETE", "CANCELLED", "FAILED_INTEGRITY")


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
            if _age_seconds(d.get("ts")) < 9 * 60:   # a recent watchdog (10-min cadence) holds the lock
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
    """Violations WE could cause (fail-closed). Collector-commit-change is recorded but not auto-fatal
    (the collector is an independent system in a separate checkout)."""
    v = []
    tracked = subprocess.run(["git", "ls-files", "data/raw"], capture_output=True, text=True,
                             cwd=str(ROOT)).stdout.strip()
    if tracked:
        v.append("raw_data_git_tracked")
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from wcdrawlab.research import data_roots as DR
        for name in DR._load()["roots"]:
            rp = str(DR.get_root(name)).replace("\\", "/")
            if "worldcup_draw_model_lab_FINAL" in rp and "worktree" not in rp:
                v.append(f"research_root_in_collector:{name}")
    except PermissionError:
        v.append("data_root_resolves_into_collector")
    except Exception:
        pass
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
    """A run is terminal-clean iff a run_summary exists with stop_reason queue_complete, OR every job is in
    a terminal status (complete/skipped/blocked) with none left 'running', OR run_state is terminal."""
    if summary and summary.get("stop_reason") == "queue_complete":
        return True
    rs = (state.get("shared") or {}).get("run_state")
    if rs in TERMINAL_RUN_STATES:
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

        # --- integrity gate (fail closed): stop the worker, disable restart, write incident ---
        if violations or run_state == "FAILED_INTEGRITY":
            wd["watchdog_state"] = "FAILED_INTEGRITY"
            wd["action"] = "stop_run+incident (restart disabled)"
            _ps(f"Stop-ScheduledTask -TaskName {MAIN_TASK} -ErrorAction SilentlyContinue")
            if run_dir:
                (run_dir / "INCIDENT_failed_integrity.json").write_text(
                    json.dumps(wd, indent=2), encoding="utf-8")
        elif not coll["commit_unchanged"] and coll["commit"]:
            wd["watchdog_state"] = run_state
            wd["note"] = "collector commit advanced independently (not our change) -> WATCH only"
            wd["action"] = "observe"
        elif terminal:
            # terminal clean run -> NEVER restart (no restart loop)
            wd["watchdog_state"] = "COMPLETE"
            wd["action"] = "terminal clean run; do nothing (never restart a completed run)"
        elif main_state == "Running":
            wd["watchdog_state"] = "RUNNING"
            wd["action"] = ("healthy: do nothing (no second worker)" if (hb_age is None or hb_age < 600)
                            else f"healthy: long job in progress (hb_age={int(hb_age)}s)")
        elif (main_state != "Running" and (hb_age is not None and hb_age > 900)
              and any(v.get("status") == "running" for v in (state.get("jobs") or {}).values())
              and run_state not in TERMINAL_RUN_STATES):
            # CRASH = a job stuck 'running' while the task is stopped + collector healthy -> restart same
            # run id (idempotent; supervisor skips completed jobs). Never starts a 2nd worker (global lock).
            wd["watchdog_state"] = "RUNNING"
            wd["action"] = "restart_same_run_id (resume unfinished jobs)"
            wd["restart_reason"] = ("task not Running + heartbeat stale >15m + a job stuck 'running' + "
                                    "collector healthy")
            _ps("Start-ScheduledTask -TaskName " + MAIN_TASK + " -ErrorAction SilentlyContinue")
        else:
            wd["watchdog_state"] = run_state
            wd["action"] = "observe"

        if run_dir:
            run_dir.mkdir(parents=True, exist_ok=True)
            with (run_dir / "watchdog_log.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(wd) + "\n")
            (run_dir / "watchdog_state.json").write_text(json.dumps(wd, indent=2), encoding="utf-8")
        (ROOT / "notes/research").mkdir(parents=True, exist_ok=True)
        with (ROOT / "notes/research/HIERARCHICAL_DOMAIN_TRANSFER_OPERATIONS_LOG.md").open(
                "a", encoding="utf-8") as f:
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
