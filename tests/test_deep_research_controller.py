"""Deep-research controller tests — SYNTHETIC jobs only; no network, no real data. Must pass in clean worktree."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import deep_research_supervisor as S  # noqa: E402


def _cfg(tmp, jobs, stale=999999, collector_hb=None):
    return {"run": {"max_hours": 4.0, "max_workers": 2, "max_api_requests": 100,
                    "heartbeat_interval_s": 30, "collector_heartbeat": str(collector_hb or (tmp / "hb.json")),
                    "collector_stale_seconds": stale, "per_job_timeout_s": 60},
            "safety": {"labels": "research_only", "kalshi_live_trading": False, "trading_mode": "paper"},
            "jobs": jobs}


def _fresh_collector_hb(tmp):
    from datetime import datetime, timezone
    hb = tmp / "hb.json"
    hb.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    return hb


def test_dry_run_all_present(tmp_path):
    hb = _fresh_collector_hb(tmp_path)
    jobs = [{"id": "J1", "title": "t1", "script": "scripts/deep_research_supervisor.py", "critical": True}]
    cfg = _cfg(tmp_path, jobs, collector_hb=hb)
    sup = S.Supervisor(cfg, tmp_path / "run1", 4.0, 100, 2, dry_run=True)
    state = sup.run()
    assert state["jobs"]["J1"]["status"] == "complete"
    assert (tmp_path / "run1" / "run_summary.json").exists()
    assert (tmp_path / "run1" / "heartbeat.json").exists()


def test_missing_script_dry_run_fails_that_job(tmp_path):
    hb = _fresh_collector_hb(tmp_path)
    jobs = [{"id": "J1", "title": "t", "script": "scripts/does_not_exist.py", "critical": False}]
    sup = S.Supervisor(_cfg(tmp_path, jobs, collector_hb=hb), tmp_path / "r", 4.0, 100, 2, dry_run=True)
    state = sup.run()
    assert state["jobs"]["J1"]["status"] == "failed"


def test_collector_stale_blocks(tmp_path):
    # heartbeat far in the past -> stale -> jobs blocked, summary still written
    from datetime import datetime, timezone, timedelta
    hb = tmp_path / "hb.json"
    old = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    hb.write_text(json.dumps({"ts": old}), encoding="utf-8")
    jobs = [{"id": "J1", "title": "t", "script": "scripts/deep_research_supervisor.py", "critical": False}]
    sup = S.Supervisor(_cfg(tmp_path, jobs, stale=60, collector_hb=hb), tmp_path / "r", 4.0, 100, 2, dry_run=True)
    state = sup.run()
    assert state["jobs"]["J1"]["status"] == "blocked"
    summ = json.loads((tmp_path / "r" / "run_summary.json").read_text(encoding="utf-8"))
    assert "collector_health" in summ["stop_reason"]


def test_idempotent_restart(tmp_path):
    hb = _fresh_collector_hb(tmp_path)
    jobs = [{"id": "J1", "title": "t", "script": "scripts/deep_research_supervisor.py", "critical": True}]
    cfg = _cfg(tmp_path, jobs, collector_hb=hb)
    S.Supervisor(cfg, tmp_path / "r", 4.0, 100, 2, dry_run=True).run()
    # second run: J1 already complete -> stays complete (no re-run error)
    state2 = S.Supervisor(cfg, tmp_path / "r", 4.0, 100, 2, dry_run=True).run()
    assert state2["jobs"]["J1"]["status"] == "complete"


def test_atomic_checkpoint_is_valid_json(tmp_path):
    hb = _fresh_collector_hb(tmp_path)
    jobs = [{"id": "J1", "title": "t", "script": "scripts/deep_research_supervisor.py", "critical": True}]
    sup = S.Supervisor(_cfg(tmp_path, jobs, collector_hb=hb), tmp_path / "r", 4.0, 100, 2, dry_run=True)
    sup.run()
    json.loads((tmp_path / "r" / "state.json").read_text(encoding="utf-8"))  # parses -> atomic write ok


def test_budget_exhaustion_blocks(tmp_path):
    hb = _fresh_collector_hb(tmp_path)
    jobs = [{"id": "J1", "title": "t", "script": "scripts/deep_research_supervisor.py", "critical": False}]
    sup = S.Supervisor(_cfg(tmp_path, jobs, collector_hb=hb), tmp_path / "r", 4.0, 0, 2, dry_run=True)
    sup.run()
    summ = json.loads((tmp_path / "r" / "run_summary.json").read_text(encoding="utf-8"))
    assert summ["stop_reason"] == "api_budget_exhausted"
