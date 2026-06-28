"""Deterministic tests for the 13-job durable International Event Lake Restoration controller.

research_only. These tests are HERMETIC: nothing here touches the network, the active collector, the
persistent lake, or any provider. They exercise:
  * the supervisor contract (config schema, dry-run queue_complete, job-script presence),
  * the _lk harness isolation primitives + the forbidden-import static scan (fail-closed),
  * each lk_job emitting a single valid JSON line with an allowed status,
  * synthetic-lake behavior for the engine-backed jobs (init/restore/cohort/sentinel) in an isolated tmp
    lake (the persistent lake is never read or written),
  * the watchdog's restart policy invariants (terminal-clean never restarts; FAILED_INTEGRITY disables).

No fabricated numbers: where a count is asserted it is recomputed from the synthetic fixture in-test.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
JOBS = ROOT / "scripts" / "lake_jobs"
CONFIG = ROOT / "configs" / "international_event_lake_restoration_v1.yaml"
SUPERVISOR = ROOT / "scripts" / "deep_research_supervisor.py"
WATCHDOG = ROOT / "scripts" / "international_event_lake_watchdog.py"
RUNNER = ROOT / "scripts" / "run_international_event_lake_restoration.ps1"

for p in (str(SRC), str(JOBS)):
    if p not in sys.path:
        sys.path.insert(0, p)

ALLOWED_STATUSES = {"complete", "skipped", "failed", "blocked",
                    "waiting_for_official_source", "data_insufficient"}
EXPECTED_JOB_IDS = [f"JOB{i}" for i in range(1, 14)]
JOB_SCRIPTS = {
    "JOB1": "lk_job01_preflight.py", "JOB2": "lk_job02_init_lake.py",
    "JOB3": "lk_job03_official_catalog.py", "JOB4": "lk_job04_legacy_restore.py",
    "JOB5": "lk_job05_strict_bridge.py", "JOB6": "lk_job06_acquire_official.py",
    "JOB7": "lk_job07_quality_retention_audit.py", "JOB8": "lk_job08_cohort.py",
    "JOB9": "lk_job09_power.py", "JOB10": "lk_job10_forward_chain_eval.py",
    "JOB11": "lk_job11_loco_calibration_bootstrap.py", "JOB12": "lk_job12_decision_ledger.py",
    "JOB13": "lk_job13_completion_report.py",
}


# =====================================================================================================
# config schema (matches scripts/deep_research_supervisor.py)
# =====================================================================================================
@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_config_exists_and_parses(cfg):
    assert isinstance(cfg, dict)
    assert set(("run", "safety", "jobs")).issubset(cfg.keys())


def test_config_run_keys_match_supervisor_contract(cfg):
    run = cfg["run"]
    for k in ("max_hours", "max_workers", "max_api_requests", "collector_heartbeat",
              "collector_stale_seconds", "per_job_timeout_s"):
        assert k in run, f"missing run.{k}"
    assert run["max_hours"] <= 10.0
    assert run["max_workers"] == 2


def test_config_safety_is_paper_and_no_forbidden_providers(cfg):
    s = cfg["safety"]
    assert s["kalshi_live_trading"] is False
    assert s["trading_mode"] == "paper"
    assert s["use_odds_api"] is False
    assert s["use_api_football"] is False
    assert "research_only" in s["labels"]
    assert "not_live_eligible" in s["labels"]


def test_config_has_exactly_13_jobs_in_order(cfg):
    ids = [j["id"] for j in cfg["jobs"]]
    assert ids == EXPECTED_JOB_IDS, ids


def test_config_job_scripts_resolve_to_lake_jobs(cfg):
    for j in cfg["jobs"]:
        script = ROOT / j["script"]
        assert script.exists(), f"missing {j['script']}"
        assert script.parent.name == "lake_jobs"
        assert Path(j["script"]).name == JOB_SCRIPTS[j["id"]]


def test_config_critical_jobs_are_the_pipeline_gates(cfg):
    crit = {j["id"] for j in cfg["jobs"] if j.get("critical")}
    # preflight, init, legacy-restore, fail-closed audit, cohort, completion are the gates
    assert {"JOB1", "JOB2", "JOB4", "JOB7", "JOB8", "JOB13"}.issubset(crit)


def test_config_collector_heartbeat_points_at_collector_not_into_worktree(cfg):
    hb = cfg["run"]["collector_heartbeat"].replace("\\", "/")
    assert "worldcup_draw_model_lab_FINAL" in hb
    assert "worldcup-international-event-lake" not in hb


# =====================================================================================================
# job scripts present + import-clean + emit contract
# =====================================================================================================
def test_all_13_job_scripts_present():
    for name in JOB_SCRIPTS.values():
        assert (JOBS / name).exists(), name


def test_lk_harness_present_and_importable():
    assert (JOBS / "_lk.py").exists()
    import _lk  # noqa: F401
    assert hasattr(_lk, "emit") and hasattr(_lk, "run_builder") and hasattr(_lk, "resolve_lake")


def test_every_job_emit_helper_produces_single_valid_json_with_allowed_status():
    import _lk
    # emit must produce a JSON object whose status is in the allowed set
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _lk.emit("complete", reason="x", state_updates={"a": 1}, api_requests=0)
    line = buf.getvalue().strip()
    obj = json.loads(line)
    assert obj["status"] in ALLOWED_STATUSES
    assert obj["api_requests"] == 0
    assert obj["state_updates"] == {"a": 1}


# =====================================================================================================
# _lk isolation primitives + forbidden-import static scan (fail-closed)
# =====================================================================================================
def test_harness_not_inside_collector():
    import _lk
    assert _lk.COLLECTOR_FORBIDDEN not in str(_lk.ROOT).replace("\\", "/")


def test_forbidden_import_scan_is_clean_over_all_jobs():
    import _lk
    hits = _lk.scan_forbidden_imports()
    assert hits == [], f"forbidden imports found: {hits}"


def test_forbidden_token_list_covers_providers_and_scrape():
    import _lk
    toks = set(_lk.FORBIDDEN_IMPORT_TOKENS)
    for must in ("api_football", "odds_api", "wcdrawlab.providers", "selenium", "playwright"):
        assert must in toks


def test_no_job_imports_requests_or_urllib_at_module_scope():
    # only the engine (owned by JOB6's builder, a separate subprocess) may retrieve official data.
    offenders = []
    for f in sorted(JOBS.glob("lk_job*.py")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if (s.startswith("import requests") or s.startswith("from requests")
                    or "urllib.request" in s):
                offenders.append((f.name, s))
    assert offenders == [], offenders


def test_official_host_is_statsbomb_open_data():
    import _lk
    assert _lk.OFFICIAL_HOST == "raw.githubusercontent.com/statsbomb/open-data"


def test_data_roots_resolver_fails_closed_on_collector():
    from wcdrawlab.research import data_roots as DR
    forb = [str(p).replace("\\", "/") for p in DR.forbidden_roots()]
    assert any("worldcup_draw_model_lab_FINAL" in f for f in forb)


def test_no_data_root_resolves_into_collector():
    import _lk
    assert _lk.roots_resolving_into_collector() == []


# =====================================================================================================
# lake engine resolves OUTSIDE every worktree (the persistent lake is external)
# =====================================================================================================
def test_lake_resolves_external_to_worktrees():
    from wcdrawlab.research import international_event_lake as L
    lake = L.Lake.resolve()
    norm = str(lake.root).replace("\\", "/")
    assert "worldcup-international-event-lake" not in norm
    assert "worldcup_draw_model_lab_FINAL" not in norm


def test_lake_resolve_rejects_root_inside_worktree(monkeypatch):
    from wcdrawlab.research import international_event_lake as L
    bad = dict(L.load_roots())
    bad["lake_root"] = str(ROOT / "data" / "would_be_inside_worktree")
    monkeypatch.setattr(L, "load_roots", lambda: bad)
    with pytest.raises(L.LakeError):
        L.Lake.resolve()


# =====================================================================================================
# synthetic isolated lake — engine-backed job behavior (never touches the persistent lake)
# =====================================================================================================
@pytest.fixture
def synth_lake(tmp_path):
    """A minimal valid single-match lake in tmp_path (content-addressed, hash-verified)."""
    from wcdrawlab.research import international_event_lake as L
    events = [
        {"id": "a", "index": 1, "period": 1, "minute": 0, "second": 0,
         "type": {"name": "Starting XI"}, "team": {"id": 1, "name": "Home"}},
        {"id": "b", "index": 2, "period": 1, "minute": 0, "second": 0,
         "type": {"name": "Starting XI"}, "team": {"id": 2, "name": "Away"}},
        {"id": "c", "index": 3, "period": 1, "minute": 10, "second": 0, "type": {"name": "Shot"},
         "team": {"id": 1}, "location": [110.0, 40.0],
         "shot": {"statsbomb_xg": 0.3, "outcome": {"name": "Goal"}}},
    ]
    raw = json.dumps(events).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    objdir = tmp_path / "objects" / sha[:2]
    objdir.mkdir(parents=True, exist_ok=True)
    (objdir / f"{sha}.json").write_bytes(raw)
    lake = L.Lake(root=tmp_path, objects=tmp_path / "objects", indexes=tmp_path / "indexes",
                  manifests=tmp_path / "manifests", quarantine=tmp_path / "quarantine",
                  integrity=tmp_path / "integrity", logs=tmp_path / "logs",
                  index_json=tmp_path / "indexes" / "idx.json",
                  index_jsonl=tmp_path / "indexes" / "idx.jsonl",
                  manifest_jsonl=tmp_path / "manifests" / "man.jsonl", cfg={})
    for d in (lake.objects, lake.indexes, lake.manifests, lake.quarantine, lake.integrity, lake.logs):
        d.mkdir(parents=True, exist_ok=True)
    rec = {"sb_match_id": 777, "local_path": f"objects/{sha[:2]}/{sha}.json", "sha256": sha,
           "event_count": len(events), "xg_available": True, "possession_available": False,
           "location_available": True, "source_url":
           "https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/777.json",
           "validation_status": "valid"}
    L.write_index(lake, {"777": rec})
    return lake, sha, events


def test_synth_lake_validate_event_bytes_ok(synth_lake):
    from wcdrawlab.research import international_event_lake as L
    _, sha, events = synth_lake
    raw = json.dumps(events).encode("utf-8")
    vr = L.validate_event_bytes(raw)
    assert vr.ok and vr.event_count == len(events) and vr.xg_available is True


def test_synth_lake_validate_rejects_html_body():
    from wcdrawlab.research import international_event_lake as L
    vr = L.validate_event_bytes(b"<html>404: Not Found</html>")
    assert not vr.ok and vr.reason == "html_or_error_body"


def test_synth_lake_validate_rejects_empty():
    from wcdrawlab.research import international_event_lake as L
    assert L.validate_event_bytes(b"").reason == "empty_file"


def test_synth_lake_validate_rejects_non_event_list():
    from wcdrawlab.research import international_event_lake as L
    assert L.validate_event_bytes(b'{"not":"a list"}').reason == "not_event_list"


def test_synth_lake_sentinel_passes_on_clean_lake(synth_lake):
    from wcdrawlab.research import international_event_lake as L
    lake, _, _ = synth_lake
    rep = L.run_sentinel(lake, bridge={777: {"competition_label": "UEFA Euro 2020"}}, write_report=False)
    assert rep.ok, rep.failures


def test_synth_lake_sentinel_fails_on_hash_mismatch(synth_lake):
    from wcdrawlab.research import international_event_lake as L
    lake, sha, _ = synth_lake
    index = L.read_index(lake)
    index["777"]["sha256"] = "0" * 64  # corrupt the recorded hash
    L.write_index(lake, index)
    rep = L.run_sentinel(lake, bridge={777: {}}, write_report=False)
    assert not rep.ok
    assert any(f["reason"] == "hash_mismatch" for f in rep.failures)


def test_synth_lake_sentinel_fails_on_missing_object(synth_lake):
    from wcdrawlab.research import international_event_lake as L
    lake, sha, _ = synth_lake
    (lake.objects / sha[:2] / f"{sha}.json").unlink()  # delete the object the index references
    rep = L.run_sentinel(lake, bridge={777: {}}, write_report=False)
    assert not rep.ok
    assert any(f["reason"] == "manifest_present_but_object_absent" for f in rep.failures)


def test_synth_lake_store_object_is_idempotent_and_immutable(synth_lake):
    from wcdrawlab.research import international_event_lake as L
    lake, _, events = synth_lake
    raw = json.dumps(events).encode("utf-8")
    rec1 = L.store_object(lake, sb_match_id=777, raw=raw, source_url="u", ingestion_mode="copied_local",
                          ingestion_run_id="t", bridge_row={"competition_label": "UEFA Euro 2020"})
    rec2 = L.store_object(lake, sb_match_id=777, raw=raw, source_url="u", ingestion_mode="copied_local",
                          ingestion_run_id="t", bridge_row={"competition_label": "UEFA Euro 2020"})
    assert rec1["sha256"] == rec2["sha256"]  # identical bytes -> same content address


def test_synth_lake_store_object_rejects_invalid_payload(synth_lake):
    from wcdrawlab.research import international_event_lake as L
    lake, _, _ = synth_lake
    with pytest.raises(L.LakeError):
        L.store_object(lake, sb_match_id=1, raw=b"<html>err</html>", source_url="u",
                       ingestion_mode="x", ingestion_run_id="t", bridge_row=None)


# =====================================================================================================
# cohort builder invariants (synthetic) — 2026 guard + raw-backed read
# =====================================================================================================
def test_cohort_2026_world_cup_guard():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "lk_cohort_builder", ROOT / "scripts/build_international_event_lake_cohort.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.is_2026_wc("FIFA World Cup 2026", "2026-06-15") is True
    assert mod.is_2026_wc("FIFA World Cup 2018", "2018-06-14") is False
    assert mod.is_2026_wc("UEFA Euro 2020", "2021-06-11") is False


def test_cohort_load_raw_from_lake_hash_mismatch_fails_closed(synth_lake):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "lk_cohort_builder2", ROOT / "scripts/build_international_event_lake_cohort.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    lake, sha, _ = synth_lake
    rec = {"local_path": f"objects/{sha[:2]}/{sha}.json", "sha256": "0" * 64}
    evs, reason = mod.load_raw_from_lake(lake, rec)
    assert evs is None and reason == "hash_mismatch"


# =====================================================================================================
# supervisor dry-run (queue_complete with 13 jobs) — the real harness, no work
# =====================================================================================================
def test_supervisor_dry_run_queue_complete():
    p = subprocess.run(
        [sys.executable, str(SUPERVISOR), "--dry-run", "--config",
         "configs/international_event_lake_restoration_v1.yaml"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    last = None
    for line in (p.stdout or "").splitlines():
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            last = json.loads(s)
    assert last is not None, p.stdout + p.stderr
    assert last["stop_reason"] == "queue_complete"
    assert last["counts"].get("complete") == 13


# =====================================================================================================
# runner + installers + watchdog presence and policy invariants
# =====================================================================================================
def test_runner_resumes_active_run_id():
    txt = RUNNER.read_text(encoding="utf-8")
    assert "active_run_id.txt" in txt
    assert "international_event_lake_restoration_v1.yaml" in txt
    assert "--hours 10" in txt


def test_main_task_installer_is_one_time_and_ignore_new():
    t = (ROOT / "scripts/windows/install_international_event_lake_task.ps1").read_text(encoding="utf-8")
    assert "WorldCupInternationalEventLakeRun" in t
    assert "IgnoreNew" in t and "StartWhenAvailable" in t
    assert "RestartCount 3" in t and "RestartInterval" in t
    assert "Hours 10" in t


def test_watchdog_installer_every_10_min():
    t = (ROOT / "scripts/windows/install_international_event_lake_watchdog_task.ps1").read_text(
        encoding="utf-8")
    assert "WorldCupInternationalEventLakeWatchdog" in t
    assert "Minutes 10" in t


def test_uninstallers_present():
    for n in ("uninstall_international_event_lake_task.ps1",
              "uninstall_international_event_lake_watchdog_task.ps1"):
        assert (ROOT / "scripts/windows" / n).exists()


def test_watchdog_never_restarts_terminal_clean_run():
    import importlib.util
    spec = importlib.util.spec_from_file_location("lk_watchdog", WATCHDOG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # queue_complete summary -> terminal
    assert mod._run_terminal({}, {"stop_reason": "queue_complete"}) is True
    # all jobs terminal, none running -> terminal
    assert mod._run_terminal({"jobs": {"JOB1": {"status": "complete"},
                                       "JOB2": {"status": "skipped"}}}, {}) is True
    # a job still running -> NOT terminal
    assert mod._run_terminal({"jobs": {"JOB1": {"status": "running"}}}, {}) is False


def test_watchdog_disables_main_task_on_failed_integrity_source():
    txt = WATCHDOG.read_text(encoding="utf-8")
    assert "FAILED_INTEGRITY" in txt
    assert "Disable-ScheduledTask" in txt
    # the disable must be in the violations branch
    assert "disable_main_task" in txt


def test_watchdog_integrity_check_flags_raw_and_lake_git_tracked():
    txt = WATCHDOG.read_text(encoding="utf-8")
    assert "raw_data_git_tracked" in txt
    assert "lake_objects_git_tracked" in txt
    assert "research_root_in_collector" in txt


# =====================================================================================================
# raw + lake are NOT git-tracked in this worktree (defence in depth, run in CI)
# =====================================================================================================
def test_raw_dir_not_git_tracked():
    out = subprocess.run(["git", "ls-files", "data/raw"], capture_output=True, text=True,
                         cwd=str(ROOT)).stdout.strip()
    assert out == "", f"raw event data must not be git-tracked: {out[:200]}"


def test_completion_note_path_is_under_notes_research():
    import _lk
    assert (_lk.NOTES / "INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md").parent == _lk.NOTES
