"""Player-Impact + xG fusion controller tests — SYNTHETIC; no network, no real data, no API key, no
Odds API. Verifies the run config parses, all 13 job scripts exist, and the inherited Supervisor dry-run
path marks every job complete. Reuses the existing deep_research_supervisor.Supervisor class.
research_only / experimental."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import deep_research_supervisor as S  # noqa: E402

CONFIG = ROOT / "configs/player_impact_xg_fusion_run_v1.yaml"
EXPECT_IDS = [f"JOB{i}" for i in range(1, 14)]
EXPECT_SCRIPTS = [
    "scripts/research_jobs/pi_job01_validate.py", "scripts/research_jobs/pi_job02_manifest.py",
    "scripts/research_jobs/pi_job03_backfill.py", "scripts/research_jobs/pi_job04_reconcile_quality.py",
    "scripts/research_jobs/pi_job05_player_linkage.py", "scripts/research_jobs/pi_job06_statsbomb_xg.py",
    "scripts/research_jobs/pi_job07_wdl.py", "scripts/research_jobs/pi_job08_nextgoal.py",
    "scripts/research_jobs/pi_job09_discipline.py", "scripts/research_jobs/pi_job10_xg_fusion.py",
    "scripts/research_jobs/pi_job11_ablation.py", "scripts/research_jobs/pi_job12_calibration.py",
    "scripts/research_jobs/pi_job13_summary.py",
]


def _load_cfg():
    import yaml
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_config_parses_and_has_13_jobs():
    cfg = _load_cfg()
    assert cfg is not None
    jobs = cfg["jobs"]
    assert len(jobs) == 13
    assert [j["id"] for j in jobs] == EXPECT_IDS
    # bounded + fail-closed knobs present and within spec
    assert cfg["run"]["max_hours"] == 6.0
    assert cfg["run"]["max_api_requests"] == 3500
    assert cfg["run"]["per_job_timeout_s"] == 7200
    assert cfg["run"]["collector_stale_seconds"] == 5400
    assert cfg["run"]["collector_heartbeat"].endswith("outputs/live_shadow/collector_heartbeat.json")
    # safety: paper-only, no odds api
    assert cfg["safety"]["use_odds_api"] is False
    assert cfg["safety"]["kalshi_live_trading"] is False


def test_all_13_job_scripts_exist():
    cfg = _load_cfg()
    cfg_scripts = [j["script"] for j in cfg["jobs"]]
    assert cfg_scripts == EXPECT_SCRIPTS
    missing = [s for s in EXPECT_SCRIPTS if not (ROOT / s).exists()]
    assert missing == [], f"missing job scripts: {missing}"


def test_critical_jobs_flagged():
    cfg = _load_cfg()
    crit = {j["id"]: bool(j.get("critical")) for j in cfg["jobs"]}
    # JOB1 validate, JOB2 manifest, JOB4 reconcile, JOB5 linkage, JOB13 summary are critical
    for jid in ("JOB1", "JOB2", "JOB4", "JOB5", "JOB13"):
        assert crit[jid] is True


def _fresh_hb(tmp_path):
    hb = tmp_path / "hb.json"
    hb.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    return hb


def test_dry_run_marks_all_jobs_complete(tmp_path):
    cfg = _load_cfg()
    hb = _fresh_hb(tmp_path)
    # point the collector heartbeat at a fresh local file so health preflight passes in CI
    cfg["run"] = dict(cfg["run"], collector_heartbeat=str(hb), collector_stale_seconds=10 ** 9)
    sup = S.Supervisor(cfg, tmp_path / "run1", cfg["run"]["max_hours"],
                       cfg["run"]["max_api_requests"], 2, dry_run=True)
    state = sup.run()
    for jid in EXPECT_IDS:
        assert state["jobs"][jid]["status"] == "complete", f"{jid} not complete: {state['jobs'].get(jid)}"
    summ = json.loads((tmp_path / "run1" / "run_summary.json").read_text(encoding="utf-8"))
    assert summ["job_status_counts"].get("complete") == 13
    assert summ["stop_reason"] == "queue_complete"
    assert (tmp_path / "run1" / "heartbeat.json").exists()


def test_dry_run_is_idempotent_on_restart(tmp_path):
    cfg = _load_cfg()
    hb = _fresh_hb(tmp_path)
    cfg["run"] = dict(cfg["run"], collector_heartbeat=str(hb), collector_stale_seconds=10 ** 9)
    rd = tmp_path / "r"
    S.Supervisor(cfg, rd, cfg["run"]["max_hours"], cfg["run"]["max_api_requests"], 2, dry_run=True).run()
    state2 = S.Supervisor(cfg, rd, cfg["run"]["max_hours"], cfg["run"]["max_api_requests"], 2, dry_run=True).run()
    assert all(state2["jobs"][jid]["status"] == "complete" for jid in EXPECT_IDS)
