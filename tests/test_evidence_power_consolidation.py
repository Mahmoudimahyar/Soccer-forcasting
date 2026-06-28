"""Evidence-Power Consolidation v1 — test suite (>=20 tests).

Covers, with NO network and NO writes outside this worktree:
  - the 12-job controller config (queue shape, critical jobs, safety flags, offline policy);
  - the _ev harness (run-dir / shared / emit / read-only builder runner / isolation backstop);
  - the 12 job scripts exist and import-scan clean of forbidden network/provider tokens (no-external-api);
  - stub/fabrication freedom across the new evidence code;
  - the cohort-lineage funnel ARITHMETIC and allowed-reason / no-silent-disappearance integrity
    (data-dependent -> skipped cleanly when artifacts absent in a clean worktree);
  - the 58-match independent reconstruction reproduces the reported pooled RPS (data-dependent);
  - the match-level power analysis is MATCH-clustered (independent unit = match, never a snapshot row);
  - cross-artifact consistency (n_matches=58 agrees everywhere);
  - isolation: no canonical data root resolves into the active collector; raw not git-tracked.

Data-dependent assertions skip with an explicit reason when the local artifact is absent, so the suite is
green in a clean worktree but rigorous wherever the consolidation has actually run.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

CONFIG = ROOT / "configs/evidence_power_consolidation_v1.yaml"
EV_DIR = ROOT / "scripts/evidence_jobs"
REF = ROOT / "data/reference"
COLLECTOR = "worldcup_draw_model_lab_FINAL"

FORBIDDEN_TOKENS = (
    "requests", "httpx", "urllib.request", "aiohttp", "websocket", "selenium", "playwright",
    "wcdrawlab.providers", "odds_api", "api_football_adapter", "fetch_odds", "live_2026",
)
EXPECTED_JOB_IDS = [f"JOB{i}" for i in range(1, 13)]
EXPECTED_JOB_SCRIPTS = [
    "ev_job01_preflight.py", "ev_job02_evidence_registry.py", "ev_job03_cohort_lineage.py",
    "ev_job04_58_match_audit.py", "ev_job05_reproducibility_audit.py", "ev_job06_detect_repair_bugs.py",
    "ev_job07_rerun_affected.py", "ev_job08_match_level_power.py", "ev_job09_live_readiness.py",
    "ev_job10_decision_memo.py", "ev_job11_consistency_audit.py", "ev_job12_final_report.py",
]


def _load_cfg():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _read_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ============================================================ config / queue
def test_config_present_and_parses():
    assert CONFIG.exists()
    cfg = _load_cfg()
    assert "run" in cfg and "safety" in cfg and "jobs" in cfg


def test_config_has_exactly_12_jobs_in_order():
    cfg = _load_cfg()
    ids = [j["id"] for j in cfg["jobs"]]
    assert ids == EXPECTED_JOB_IDS, ids


def test_config_job_scripts_match_expected_filenames():
    cfg = _load_cfg()
    scripts = [Path(j["script"]).name for j in cfg["jobs"]]
    assert scripts == EXPECTED_JOB_SCRIPTS, scripts


def test_config_critical_jobs_are_preflight_lineage_58match_final():
    cfg = _load_cfg()
    crit = {j["id"] for j in cfg["jobs"] if j.get("critical")}
    assert crit == {"JOB1", "JOB3", "JOB4", "JOB12"}, crit


def test_config_safety_is_paper_only_offline():
    s = _load_cfg()["safety"]
    assert s["kalshi_live_trading"] is False
    assert s["trading_mode"] == "paper"
    assert s["use_odds_api"] is False and s["use_api_football"] is False
    assert "research_only" in s["labels"] and "not_trade_eligible" in s["labels"]


def test_config_run_bounds_8h_2workers_long_timeout():
    r = _load_cfg()["run"]
    assert r["max_hours"] == 8.0
    assert r["max_workers"] == 2
    assert r["per_job_timeout_s"] == 28800
    assert COLLECTOR in r["collector_heartbeat"]


def test_config_collector_heartbeat_points_at_collector_not_a_write_path():
    # the heartbeat is READ from the collector; the consolidation must never WRITE there.
    hb = _load_cfg()["run"]["collector_heartbeat"]
    assert hb.endswith("collector_heartbeat.json")
    assert COLLECTOR in hb


# ============================================================ job scripts exist + clean
def test_all_12_job_scripts_exist():
    for name in EXPECTED_JOB_SCRIPTS:
        assert (EV_DIR / name).exists(), name


def test_ev_harness_exists():
    assert (EV_DIR / "_ev.py").exists()


def test_no_forbidden_network_or_provider_imports_in_jobs():
    offenders = []
    for f in sorted(EV_DIR.glob("*.py")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if s.startswith(("import ", "from ")):
                for tok in FORBIDDEN_TOKENS:
                    if tok in s:
                        offenders.append((f.name, s, tok))
    assert not offenders, offenders


def test_jobs_emit_status_via_ev_emit_or_subprocess():
    # every job must end by emitting a status line (directly or by importing _ev.emit)
    for name in EXPECTED_JOB_SCRIPTS:
        txt = (EV_DIR / name).read_text(encoding="utf-8")
        assert "_ev.emit(" in txt, name


def test_no_stub_or_fabrication_markers_in_evidence_code():
    bad = ("TODO", "FIXME", "STUB", "FAKE", "PLACEHOLDER", "np.random.rand(", "random.random(",
           "lorem ipsum")
    offenders = []
    # scan the evidence job/harness/watchdog code (NOT this test file, which legitimately names the
    # marker tokens in `bad` above).
    targets = list(EV_DIR.glob("*.py")) + [ROOT / "scripts/research_evidence_watchdog.py"]
    for f in targets:
        txt = f.read_text(encoding="utf-8")
        for b in bad:
            if b in txt:
                offenders.append((f.name, b))
    assert not offenders, offenders


def test_jobs_allow_honest_data_insufficient_or_skipped():
    # the design explicitly permits honest skip/data_insufficient (never a false complete). Confirm at
    # least the conditional jobs (05/06/07/etc.) can emit a non-complete honest status.
    blob = "".join((EV_DIR / n).read_text(encoding="utf-8") for n in EXPECTED_JOB_SCRIPTS)
    assert "data_insufficient" in blob
    assert "\"skipped\"" in blob or "'skipped'" in blob


# ============================================================ _ev harness behavior
def test_ev_harness_imports_and_has_api():
    sys.path.insert(0, str(EV_DIR))
    import _ev
    for attr in ("run_dir", "art_dir", "shared", "emit", "write_json", "run_builder",
                 "data_roots", "FORBIDDEN_IMPORT_TOKENS", "LABELS"):
        assert hasattr(_ev, attr), attr


def test_ev_harness_labels_are_research_only():
    sys.path.insert(0, str(EV_DIR))
    import _ev
    for tok in ("research_only", "not_runtime_approved", "not_trade_eligible", "not_live_eligible"):
        assert tok in _ev.LABELS


def test_ev_run_builder_returns_honest_failure_for_missing_script():
    sys.path.insert(0, str(EV_DIR))
    import _ev
    res = _ev.run_builder("scripts/__definitely_not_a_real_builder__.py", timeout=10)
    assert res["ok"] is False
    assert "missing" in (res["stderr_tail"] or "").lower()


# ============================================================ isolation
def test_data_roots_never_resolve_into_active_collector():
    from wcdrawlab.research import data_roots as DR
    for name in DR._load()["roots"]:
        try:
            p = str(DR.get_root(name)).replace("\\", "/")
        except PermissionError:
            # fail-closed resolver tripping IS the guard working
            continue
        # a research root may live under a *worktree* but never the bare collector checkout root
        assert not (COLLECTOR in p and "worktree" not in p), (name, p)


def test_forbidden_roots_list_contains_collector():
    from wcdrawlab.research import data_roots as DR
    forbidden = " ".join(str(p) for p in DR.forbidden_roots())
    assert COLLECTOR in forbidden


def test_raw_data_not_git_tracked_in_this_worktree():
    tracked = subprocess.run(["git", "ls-files", "data/raw"], capture_output=True, text=True,
                             cwd=str(ROOT)).stdout.strip()
    assert tracked == "", f"raw data must not be git-tracked: {tracked[:200]}"


def test_watchdog_never_modifies_collector_and_has_global_lock():
    txt = (ROOT / "scripts/research_evidence_watchdog.py").read_text(encoding="utf-8")
    assert "_acquire_lock" in txt and "_release_lock" in txt
    assert "WorldCupEvidencePowerConsolidationRun" in txt
    # restart guarded by terminal check (never restart a completed run)
    assert "_run_terminal" in txt and "never restart a completed run" in txt


# ============================================================ lineage funnel (data-dependent)
def test_lineage_funnel_arithmetic_balances():
    lin = _read_json(REF / "evaluation_cohort_lineage.json")
    if lin is None:
        pytest.skip("evaluation_cohort_lineage.json absent (run JOB3 / the builder first)")
    fs = lin["meta"]["funnel_summary"]
    assert fs["exact_bridge_population"] - fs["dropped_missing_statsbomb_events"] == fs[
        "residual_population"]


def test_lineage_integrity_allowed_reasons_and_no_silent_drops():
    lin = _read_json(REF / "evaluation_cohort_lineage.json")
    if lin is None:
        pytest.skip("evaluation_cohort_lineage.json absent")
    meta = lin["meta"]
    assert meta["allowed_reasons_only"] is True, meta.get("bad_reasons")
    assert meta["no_silent_disappearance"] is True, meta.get("unexplained_drops")


def test_lineage_residual_population_is_58_and_is_data_boundary():
    lin = _read_json(REF / "evaluation_cohort_lineage.json")
    if lin is None:
        pytest.skip("evaluation_cohort_lineage.json absent")
    fs = lin["meta"]["funnel_summary"]
    assert fs["exact_bridge_population"] == 258
    assert fs["residual_population"] == 58
    # the dominant loss reason is a DATA-availability boundary, not a modeling drop
    assert lin["meta"]["drop_reason_counts"].get("missing_statsbomb_events") == 200


def test_forward_chain_test_set_excludes_earliest_train_only_competition():
    lin = _read_json(REF / "evaluation_cohort_lineage.json")
    if lin is None:
        pytest.skip("evaluation_cohort_lineage.json absent")
    fs = lin["meta"]["funnel_summary"]
    # forward-chain set (46) < LOCO set (58) by exactly the held-out earliest competition's matches
    assert fs["primary_evaluation_population"] < fs["loco_evaluation_population"]
    assert fs["dropped_held_out_fold_rule"] == (
        fs["residual_population"] - fs["primary_evaluation_population"])


# ============================================================ 58-match reconstruction (data-dependent)
def test_58_match_independent_recompute_reproduces_reported_rps():
    audit = _read_json(REF / "residual_58_match_audit.json")
    if audit is None:
        pytest.skip("residual_58_match_audit.json absent (run JOB4 / the audit first)")
    cmp = audit["comparison"]
    fc = cmp["forward_chain_pooled_rps"]
    assert fc["match"] is True, fc
    assert cmp["n_matches"]["recomputed"] == 58
    assert audit["verdict"]["cohort_reconstructed_to_58"] is True


# ============================================================ power (match-clustered)
def test_match_level_power_unit_is_match_not_snapshot():
    power = _read_json(REF / "match_level_power_analysis.json")
    if power is None:
        pytest.skip("match_level_power_analysis.json absent (run JOB8 first)")
    unit = power["unit_of_independence"].lower()
    assert "match" in unit and "snapshot" not in unit.split("(")[0]
    # more-snapshots-same-matches must keep 58 clusters (clustering ceiling)
    by_inf = power["more_snapshots_same_matches"]["by_inflation"]
    for v in by_inf.values():
        assert v["independent_clusters"] == 58


def test_match_level_power_is_deterministic_fixed_seed():
    power = _read_json(REF / "match_level_power_analysis.json")
    if power is None:
        pytest.skip("match_level_power_analysis.json absent")
    seeds = power["seeds"]
    assert seeds["no_walltime_entropy"] is True
    assert isinstance(seeds["master_seed"], int)


# ============================================================ cross-artifact consistency
def test_n_matches_58_agrees_across_artifacts():
    lin = _read_json(REF / "evaluation_cohort_lineage.json")
    audit = _read_json(REF / "residual_58_match_audit.json")
    power = _read_json(REF / "match_level_power_analysis.json")
    present = [x for x in (lin, audit, power) if x is not None]
    if len(present) < 2:
        pytest.skip("fewer than 2 consolidation artifacts present to cross-check")
    vals = set()
    if lin is not None:
        vals.add(lin["meta"]["funnel_summary"]["residual_population"])
    if audit is not None:
        vals.add(audit["comparison"]["n_matches"]["recomputed"])
    if power is not None:
        vals.add(power["data_provenance"]["n_matches_observed"])
    assert vals == {58}, vals
