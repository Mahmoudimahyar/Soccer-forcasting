"""JOB1: validate the player-impact+xG fusion run. Confirms (a) the config parses, (b) all 13 job
scripts exist, (c) the inherited controller dry-run marks every job complete, and (d) the project's
relevant unit tests pass. research_only / experimental / not_runtime_approved. No network, no API key."""
import sys, json, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]
CONFIG = "configs/player_impact_xg_fusion_run_v1.yaml"
JOB_SLUGS = [(1,"validate"),(2,"manifest"),(3,"backfill"),(4,"reconcile_quality"),(5,"player_linkage"),
             (6,"statsbomb_xg"),(7,"wdl"),(8,"nextgoal"),(9,"discipline"),(10,"xg_fusion"),
             (11,"ablation"),(12,"calibration"),(13,"summary")]


def main():
    _job.run_dir()
    import yaml
    cfg = yaml.safe_load((ROOT / CONFIG).read_text(encoding="utf-8"))
    cfg_jobs = [j["id"] for j in cfg["jobs"]]
    expect_ids = [f"JOB{n}" for n, _ in JOB_SLUGS]
    cfg_ok = cfg_jobs == expect_ids
    scripts = [f"scripts/research_jobs/pi_job{n:02d}_{s}.py" for n, s in JOB_SLUGS]
    missing = [s for s in scripts if not (ROOT / s).exists()]
    # controller dry-run with THIS config (reuse the inherited Supervisor + dry-run path)
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib, tempfile
    from datetime import datetime, timezone
    S = importlib.import_module("deep_research_supervisor")
    dry_ok = False; dry_reason = ""
    try:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            hb = tdp / "hb.json"
            hb.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
            dcfg = dict(cfg); dcfg["run"] = dict(cfg["run"], collector_heartbeat=str(hb), collector_stale_seconds=10**9)
            sup = S.Supervisor(dcfg, tdp / "dryrun", cfg["run"]["max_hours"], cfg["run"]["max_api_requests"], 2, dry_run=True)
            st = sup.run()
            statuses = {jid: v.get("status") for jid, v in st["jobs"].items()}
            dry_ok = all(statuses.get(jid) == "complete" for jid in expect_ids)
            dry_reason = "all jobs complete" if dry_ok else f"statuses={statuses}"
    except Exception as e:
        dry_reason = f"dry-run error: {e}"
    # relevant unit tests (controller + result semantics + datasets)
    test_files = [t for t in ["tests/test_player_impact_controller.py", "tests/test_result_semantics.py",
                              "tests/test_historical_datasets.py"] if (ROOT / t).exists()]
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", *test_files],
                       capture_output=True, text=True, cwd=str(ROOT))
    tests_ok = r.returncode == 0
    ok = cfg_ok and not missing and dry_ok and tests_ok
    reason = ("config parses; 13 job scripts present; controller dry-run all complete; unit tests pass"
              if ok else
              f"cfg_ok={cfg_ok} missing={missing} dry_ok={dry_ok} ({dry_reason}) tests_rc={r.returncode}")
    _job.emit("complete" if ok else "failed", reason=reason,
              state_updates={"validate_cfg_ok": cfg_ok, "validate_dry_ok": dry_ok, "validate_tests_ok": tests_ok})


main()
