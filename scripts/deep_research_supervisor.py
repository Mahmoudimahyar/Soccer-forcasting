"""Deep Research Controller (supervisor). Restart-safe, bounded (<=4h), finite ordered job queue, fail-closed.
research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Each job is a python script invoked as: python <script> --run-dir <dir>. It must print, as its LAST stdout
line, a JSON object: {"status": "...", "reason": "...", "api_requests": int, "state_updates": {...}}.
Status in {complete, skipped, failed, blocked}. The supervisor enforces deadline + API budget + collector
health BEFORE each job (fail-closed), checkpoints state.json atomically after each job, writes a heartbeat,
and ALWAYS writes a final run_summary.json. No infinite loop (finite queue + hard deadline).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _load_yaml(p):
    import yaml
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


def _collector_stale(cfg, mono_start_wall):
    hb = Path(cfg["run"]["collector_heartbeat"])
    if not hb.exists():
        return True, "collector heartbeat missing"
    try:
        ts = json.loads(hb.read_text(encoding="utf-8")).get("ts")
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        return True, "collector heartbeat unreadable"
    age = time.time() - t
    if age > cfg["run"]["collector_stale_seconds"]:
        return True, f"collector heartbeat stale ({int(age)}s)"
    return False, None


class Supervisor:
    def __init__(self, cfg, run_dir: Path, max_hours, max_api, max_workers, dry_run):
        self.cfg = cfg
        self.run_dir = run_dir
        self.max_seconds = max_hours * 3600.0
        self.max_api = max_api
        self.max_workers = max_workers
        self.dry_run = dry_run
        self.state_path = run_dir / "state.json"
        self.hb_path = run_dir / "heartbeat.json"
        self.log_path = run_dir / "job_log.jsonl"
        self.summary_path = run_dir / "run_summary.json"

    def _load_state(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"run_id": self.run_dir.name, "started_utc": _utc(), "jobs": {}, "api_requests_used": 0,
                "shared": {}, "dry_run": self.dry_run}

    def _heartbeat(self, state, phase):
        _atomic_write(self.hb_path, {"ts": _utc(), "phase": phase, "api_requests_used": state["api_requests_used"],
                                     "elapsed_s": round(time.time() - self.t0, 1)})

    def _log(self, rec):
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def run(self):
        self.t0 = time.time()
        state = self._load_state()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        jobs = self.cfg["jobs"]
        deadline = self.t0 + self.max_seconds
        stop_reason = None
        for job in jobs:
            jid = job["id"]
            prev = state["jobs"].get(jid, {})
            if prev.get("status") == "complete":
                continue  # idempotent restart: skip done jobs
            # fail-closed preflight
            if time.time() >= deadline:
                stop_reason = "deadline_reached"; self._block_remaining(state, jobs, jid, stop_reason); break
            stale, why = _collector_stale(self.cfg, self.t0)
            if stale:
                stop_reason = f"collector_health:{why}"; self._block_remaining(state, jobs, jid, stop_reason); break
            if state["api_requests_used"] >= self.max_api:
                stop_reason = "api_budget_exhausted"; self._block_remaining(state, jobs, jid, stop_reason); break

            state["jobs"][jid] = {"status": "running", "started_utc": _utc(), "title": job["title"]}
            self._checkpoint(state); self._heartbeat(state, f"running:{jid}")
            result = self._run_job(job, state, deadline)
            state["jobs"][jid].update({"status": result["status"], "reason": result.get("reason"),
                                       "ended_utc": _utc(), "api_requests": result.get("api_requests", 0)})
            state["api_requests_used"] += int(result.get("api_requests", 0) or 0)
            for k, v in (result.get("state_updates") or {}).items():
                state["shared"][k] = v
            self._log({"ts": _utc(), "job": jid, **result})
            self._checkpoint(state); self._heartbeat(state, f"done:{jid}")
            if result["status"] == "failed" and job.get("critical"):
                stop_reason = f"critical_job_failed:{jid}"; self._block_remaining(state, jobs, jid, stop_reason, after=True); break
        self._write_summary(state, stop_reason)
        return state

    def _run_job(self, job, state, deadline):
        script = ROOT / job["script"]
        if self.dry_run:
            ok = script.exists()
            return {"status": "complete" if ok else "failed",
                    "reason": "dry-run: script present" if ok else "dry-run: script MISSING", "api_requests": 0}
        if not script.exists():
            return {"status": "failed", "reason": f"script missing: {job['script']}", "api_requests": 0}
        timeout = min(self.cfg["run"]["per_job_timeout_s"], max(1, int(deadline - time.time())))
        env = dict(os.environ, DEEP_RESEARCH_RUN_DIR=str(self.run_dir),
                   DEEP_RESEARCH_API_BUDGET=str(max(0, self.max_api - state["api_requests_used"])),
                   DEEP_RESEARCH_SHARED=json.dumps(state["shared"]))
        try:
            p = subprocess.run([sys.executable, str(script), "--run-dir", str(self.run_dir)],
                               capture_output=True, text=True, timeout=timeout, env=env, cwd=str(ROOT))
        except subprocess.TimeoutExpired:
            return {"status": "failed", "reason": "job timeout", "api_requests": 0}
        last = None
        for line in (p.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    last = json.loads(line)
                except Exception:
                    pass
        if last is None:
            return {"status": "failed" if p.returncode else "complete",
                    "reason": (p.stderr or "no JSON result")[-300:], "api_requests": 0}
        last.setdefault("status", "complete" if p.returncode == 0 else "failed")
        return last

    def _block_remaining(self, state, jobs, from_jid, reason, after=False):
        hit = False
        for job in jobs:
            jid = job["id"]
            if jid == from_jid:
                hit = True
                if after:
                    continue
            if hit and state["jobs"].get(jid, {}).get("status") not in ("complete", "skipped"):
                state["jobs"][jid] = {"status": "blocked", "reason": reason}
        self._checkpoint(state)

    def _checkpoint(self, state):
        state["updated_utc"] = _utc()
        _atomic_write(self.state_path, state)

    def _write_summary(self, state, stop_reason):
        counts = {}
        for j in state["jobs"].values():
            counts[j["status"]] = counts.get(j["status"], 0) + 1
        summary = {"run_id": state["run_id"], "started_utc": state.get("started_utc"), "ended_utc": _utc(),
                   "elapsed_s": round(time.time() - self.t0, 1), "stop_reason": stop_reason or "queue_complete",
                   "api_requests_used": state["api_requests_used"], "job_status_counts": counts,
                   "jobs": {k: {"status": v["status"], "reason": v.get("reason")} for k, v in state["jobs"].items()},
                   "shared": state["shared"], "dry_run": self.dry_run,
                   "labels": self.cfg["safety"]["labels"]}
        _atomic_write(self.summary_path, summary)
        print(json.dumps({"supervisor": "done", "stop_reason": summary["stop_reason"],
                          "counts": counts, "api_used": state["api_requests_used"]}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/deep_research_run_v1.yaml")
    ap.add_argument("--hours", type=float, default=4.0)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--resume-run-id", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-api-requests", type=int, default=None)
    ap.add_argument("--max-workers", type=int, default=2)
    a = ap.parse_args()
    cfg = _load_yaml(ROOT / a.config)
    max_api = a.max_api_requests if a.max_api_requests is not None else cfg["run"]["max_api_requests"]
    rid = a.resume_run_id or a.run_id or ("dryrun" if a.dry_run else "run_" + str(int(os.environ.get("DR_STAMP", "1"))))
    run_dir = ROOT / "outputs/research_runs" / rid
    sup = Supervisor(cfg, run_dir, min(a.hours, cfg["run"]["max_hours"]), max_api, a.max_workers, a.dry_run)
    sup.run()


if __name__ == "__main__":
    main()
