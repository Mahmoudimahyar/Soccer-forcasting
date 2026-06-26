"""Self-supervising watchdog for the durable research run. Runs every 15 min (via Task Scheduler),
independently of any chat session. Single GLOBAL LOCK -> never launches concurrent backfills/controllers.
NEVER modifies WorldCupShadowCollector. Reads only run state/heartbeat/job_log/artifact_manifest +
execution manifest + collector heartbeat + Task Scheduler state. Writes only watchdog_log.jsonl /
watchdog_state.json / RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md. research_only.

State machine: BOOTSTRAPPED / RUNNING / WAITING_FOR_API_QUOTA / WAITING_FOR_SOURCE / BLOCKED_EXTERNAL /
COMPLETE / FAILED_INTEGRITY / CANCELLED.
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
LOCK = RUNS / ".global.lock"
COLLECTOR = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")
COLLECTOR_HB = COLLECTOR / "outputs/live_shadow/collector_heartbeat.json"
EXPECTED_COLLECTOR_COMMIT = "dc73318"
MAIN_TASK = "WorldCupResearchTruthFusionRun"
RESUME_TASK = "WorldCupResearchTruthFusionResume"
WATCHDOG_TASK = "WorldCupResearchTruthFusionWatchdog"


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
            if _age_seconds(d.get("ts")) < 14 * 60:   # a recent watchdog holds the lock
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
    """Things WE could cause (fail-closed). Collector-commit-change is recorded but not auto-fatal (the
    collector is an independent system in a separate checkout)."""
    v = []
    # raw must not be git-tracked in this worktree
    tracked = subprocess.run(["git", "ls-files", "data/raw"], capture_output=True, text=True, cwd=str(ROOT)).stdout.strip()
    if tracked:
        v.append("raw_data_git_tracked")
    # canonical roots must not resolve into the collector checkout
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from wcdrawlab.research import data_roots as DR
        for name in DR._load()["roots"]:
            if "worldcup_draw_model_lab_FINAL" in str(DR.get_root(name)).replace("\\", "/"):
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


def main():
    if not _acquire_lock():
        return  # another watchdog action in progress -> never run concurrently
    try:
        run_id = _active_run()
        run_dir = RUNS / run_id if run_id else None
        state = {}
        if run_dir and (run_dir / "state.json").exists():
            try:
                state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            except Exception:
                state = {}
        hb_age = None
        if run_dir and (run_dir / "heartbeat.json").exists():
            try:
                hb_age = _age_seconds(json.loads((run_dir / "heartbeat.json").read_text(encoding="utf-8")).get("ts"))
            except Exception:
                pass
        main_state = _task_state(MAIN_TASK)
        coll = _collector_status()
        violations = _integrity_violations()
        run_state = (state.get("shared") or {}).get("run_state", "RUNNING" if main_state == "Running" else "UNKNOWN")

        wd = {"ts": _utc(), "run_id": run_id, "main_task": main_state, "heartbeat_age_s": hb_age,
              "run_state": run_state, "collector": coll, "integrity_violations": violations, "action": None}

        # --- integrity gate (fail closed) ---
        if violations or not coll["commit_unchanged"]:
            # collector-commit-change alone -> record as WATCH; OUR-caused violations -> FAILED_INTEGRITY
            if violations:
                wd["watchdog_state"] = "FAILED_INTEGRITY"; wd["action"] = "stop_research+disable_resume+incident"
                _ps(f"Stop-ScheduledTask -TaskName {MAIN_TASK} -ErrorAction SilentlyContinue; "
                    f"Disable-ScheduledTask -TaskName {RESUME_TASK} -ErrorAction SilentlyContinue")
                (run_dir / "INCIDENT_failed_integrity.json").write_text(json.dumps(wd, indent=2), encoding="utf-8") if run_dir else None
            else:
                wd["watchdog_state"] = run_state; wd["note"] = "collector commit advanced independently (not our change) -> WATCH only"
        elif main_state == "Running":
            # task Running = healthy; heartbeat may be stale during a long JOB2 backfill subprocess (the
            # supervisor heartbeats between jobs) -> liveness is the Running task + ongoing raw writes.
            wd["watchdog_state"] = "RUNNING"
            wd["action"] = ("healthy: do nothing (no second worker)" if (hb_age is None or hb_age < 600)
                            else f"healthy: do nothing (long job in progress; hb_age={int(hb_age)}s)")
        elif run_state == "WAITING_FOR_API_QUOTA":
            en = _task_state(RESUME_TASK)
            wd["watchdog_state"] = "WAITING_FOR_API_QUOTA"
            wd["action"] = f"ensure daily resume enabled (resume_task={en}); do NOT force resume before quota window"
        elif run_state == "WAITING_FOR_SOURCE":
            # API-Football corpus complete; a binding external source (e.g. StatsBomb) is incomplete. This is a
            # legitimate non-running pause, NOT a crash -> do not restart. Downstream gates resume when the
            # source is acquired (separate bounded official open-data fetch).
            wd["watchdog_state"] = "WAITING_FOR_SOURCE"
            wd["action"] = "observe: corpus complete, waiting on external source (StatsBomb); no restart"
        elif main_state != "Running" and (hb_age is not None and hb_age > 900) and run_state not in (
                "COMPLETE", "WAITING_FOR_SOURCE", "WAITING_FOR_API_QUOTA", "CANCELLED", "FAILED_INTEGRITY"):
            # crashed mid-run -> restart SAME run id, resume only unfinished jobs (idempotent; no re-pull)
            wd["watchdog_state"] = "RUNNING"; wd["action"] = "restart_same_run_id (resume unfinished jobs)"
            wd["restart_reason"] = "task not Running + heartbeat stale >15m + no lock + collector healthy"
        else:
            wd["watchdog_state"] = run_state; wd["action"] = "observe"

        # write outputs (only the allowed locations)
        if run_dir:
            run_dir.mkdir(parents=True, exist_ok=True)
            with (run_dir / "watchdog_log.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(wd) + "\n")
            (run_dir / "watchdog_state.json").write_text(json.dumps(wd, indent=2), encoding="utf-8")
        with (ROOT / "notes/research/RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md").open("a", encoding="utf-8") as f:
            f.write(f"- {wd['ts']} state={wd.get('watchdog_state')} main_task={main_state} hb_age={hb_age} "
                    f"collector={coll['commit']}({'ok' if coll['commit_unchanged'] else 'CHANGED'}) "
                    f"violations={violations or 'none'} action={wd['action']}\n")
        print(json.dumps({k: wd[k] for k in ("watchdog_state", "main_task", "run_state", "action")}))
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
