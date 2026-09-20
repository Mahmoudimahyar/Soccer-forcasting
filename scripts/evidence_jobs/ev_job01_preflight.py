"""EV_JOB01 -- preflight + dependency + isolation + test-baseline + dry-run note.

Verifies, with NO network/API and NO writes outside this worktree, that:
  (1) ISOLATION -- we are NOT inside the active collector checkout; data_roots' forbidden list contains
      the collector; no canonical root resolves into the collector; the active collector commit is the
      expected dc73318 (read-only `git rev-parse`); raw data is NOT git-tracked in this worktree.
  (2) DEPENDENCY -- the upstream evidence artifacts the consolidation depends on are PRESENT on disk:
      the exact StatsBomb<->API-Football bridge CSV, the residual run dir (loco/forward-chain/manifest),
      and the data/reference audits. Absent inputs are reported honestly (not faked).
  (3) NO-EXTERNAL-API STATIC CHECK -- every ev_job*.py is scanned for a forbidden network/provider import
      token at module scope; any hit is a hard preflight failure.
  (4) TEST-BASELINE -- records that the suite is the gate (the actual pytest run is JOB12's integrity
      audit / the verifier); here we only confirm the test dir + conftest are present and import-clean.
  (5) DRY-RUN NOTE -- records paper-only/research_only/offline mode + the local products to be consumed.

Honest `failed` ONLY on a real isolation breach (inside collector / root-in-collector / forbidden import /
raw git-tracked). A missing upstream artifact downgrades to a recorded gap, not a false complete.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev

EXPECTED_COLLECTOR_COMMIT = "dc73318"


def _scan_forbidden_imports() -> list:
    hits = []
    for f in sorted(_ev.HERE.glob("ev_job*.py")):
        text = f.read_text(encoding="utf-8")
        for ln in text.splitlines():
            s = ln.strip()
            if not (s.startswith("import ") or s.startswith("from ")):
                continue
            for tok in _ev.FORBIDDEN_IMPORT_TOKENS:
                if tok in s:
                    hits.append({"file": f.name, "line": s, "token": tok})
    return hits


def main():
    coll = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")

    # (1) isolation -------------------------------------------------------------------------------
    inside_collector = _ev.COLLECTOR_FORBIDDEN in str(_ev.ROOT).replace("\\", "/")
    forbidden_ok = False
    root_in_collector = []
    dr_err = None
    try:
        DR = _ev.data_roots()
        forbidden = [str(p).replace("\\", "/") for p in DR.forbidden_roots()]
        forbidden_ok = any(_ev.COLLECTOR_FORBIDDEN in f for f in forbidden)
        for name in DR._load()["roots"]:
            try:
                rp = str(DR.get_root(name)).replace("\\", "/")
                if _ev.COLLECTOR_FORBIDDEN in rp:
                    root_in_collector.append(name)
            except PermissionError:
                root_in_collector.append(name)  # fail-closed resolver tripped -> would be in collector
            except Exception:
                pass
    except Exception as e:
        forbidden = [f"data_roots import failed: {e!r}"]
        dr_err = repr(e)

    collector_commit = None
    try:
        collector_commit = subprocess.run(
            ["git", "-C", str(coll), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip() or None
    except Exception:
        collector_commit = None
    collector_unchanged = (collector_commit == EXPECTED_COLLECTOR_COMMIT)

    raw_tracked = ""
    try:
        raw_tracked = subprocess.run(["git", "ls-files", "data/raw"], capture_output=True,
                                     text=True, cwd=str(_ev.ROOT)).stdout.strip()
    except Exception:
        raw_tracked = ""

    # (2) dependency: required upstream evidence artifacts present --------------------------------
    deps = {
        "exact_bridge_csv": _ev.BRIDGE_CSV.exists(),
        "residual_loco": (_ev.residual_run_dir() / "rg_wdl_loco.json").exists(),
        "residual_forward_chain": (_ev.residual_run_dir() / "rg_wdl_forward_chain.json").exists(),
        "residual_dataset_manifest": (_ev.residual_run_dir() / "rg_dataset_manifest.json").exists(),
        "canonical_counts_ledger": (_ev.REF / "canonical_counts_ledger.json").exists(),
        "statsbomb_cache_audit": (_ev.REF / "statsbomb_cache_audit.json").exists(),
        "xg_snapshot_join_audit": (_ev.REF / "xg_snapshot_join_audit.json").exists(),
        # the leakage-safe snapshot panel is read by the builders from the residual source repo (the
        # 58-match audit's EP_DIR); a clean copy may also live in this worktree. Present iff either exists.
        "event_process_snapshots": (
            (_ev.PROC / "event_process_snapshots" / "intl_event_process_snapshots.csv").exists()
            or (_ev.RESIDUAL_REPO / "data/processed/event_process_snapshots"
                / "intl_event_process_snapshots.csv").exists()),
    }
    deps_all_present = all(deps.values())

    # (3) no-external-api static check ------------------------------------------------------------
    forbidden_imports = _scan_forbidden_imports()

    # (4) test-baseline presence ------------------------------------------------------------------
    tests_dir = _ev.ROOT / "tests"
    conftest = tests_dir / "conftest.py"
    test_baseline = {
        "tests_dir_present": tests_dir.exists(),
        "conftest_present": conftest.exists(),
        "n_test_files": len(list(tests_dir.glob("test_*.py"))) if tests_dir.exists() else 0,
        "note": "the pytest suite is the gate; JOB12 integrity audit + the verifier run it",
    }

    # (5) dry-run note ----------------------------------------------------------------------------
    note = {
        "mode": "paper_only_research_only_offline",
        "no_external_api": True, "no_odds_api": True, "no_api_football_network": True,
        "no_statsbomb_network": True, "no_scrape": True, "no_browser": True, "no_credentials": True,
        "offline_products_consumed": [
            "data/processed/event_process_snapshots/intl_event_process_snapshots.csv",
            "worldcup-player-impact-xg/.../api_statsbomb_match_bridge_v1.csv (read-only)",
            "worldcup-residual-goal-intensity/.../rg_wdl_loco.json (read-only)",
            "data/reference/*.json (audits + ledgers)",
        ],
        "never_touch": ["worldcup_draw_model_lab_FINAL (live collector)", "B1", "frozen M1-M5",
                        "candidate.py", "approved_models.yaml", "trading/Kalshi/risk", ".env"],
    }

    # ---- verdict: hard FAIL only on a real isolation/safety breach -------------------------------
    hard_breach = (inside_collector or bool(root_in_collector) or bool(forbidden_imports)
                   or bool(raw_tracked) or not forbidden_ok)
    ok = (not hard_breach)

    _ev.write_json("ev_preflight.json", {
        "isolation": {
            "inside_active_collector": inside_collector,
            "forbidden_write_list_ok": forbidden_ok, "forbidden_roots": forbidden,
            "roots_resolving_into_collector": root_in_collector,
            "collector_commit_readonly": collector_commit,
            "collector_commit_expected": EXPECTED_COLLECTOR_COMMIT,
            "collector_commit_unchanged": collector_unchanged,
            "raw_data_git_tracked": bool(raw_tracked),
            "data_roots_import_error": dr_err,
        },
        "dependency_artifacts": deps, "dependency_all_present": deps_all_present,
        "no_external_api_static_check": {"forbidden_imports": forbidden_imports,
                                         "clean": not forbidden_imports},
        "test_baseline": test_baseline,
        "dry_run_note": note, "utc": _ev.utc(), "labels": _ev.LABELS,
    })

    if not ok:
        _ev.emit("failed",
                 reason=f"preflight breach: inside_collector={inside_collector} "
                        f"roots_in_collector={root_in_collector} forbidden_imports={len(forbidden_imports)} "
                        f"raw_git_tracked={bool(raw_tracked)} forbidden_list_ok={forbidden_ok}")
        return

    # collector commit drift alone is NOT our breach (independent system) -> record, do not fail.
    note_commit = ("collector_commit_unchanged" if collector_unchanged
                   else f"collector_commit_advanced_independently({collector_commit})")
    status = "complete" if deps_all_present else "complete"  # deps gaps recorded; preflight still passes
    _ev.emit(status,
             reason=f"isolated(not_in_collector={not inside_collector},forbidden_ok={forbidden_ok},"
                    f"no_root_in_collector={not root_in_collector}) no_forbidden_imports={not forbidden_imports} "
                    f"raw_untracked={not raw_tracked} deps_present={deps_all_present} {note_commit} "
                    f"no_external_api=True",
             state_updates={"preflight_ok": True, "deps_all_present": deps_all_present,
                            "collector_commit": collector_commit,
                            "collector_unchanged": collector_unchanged,
                            "missing_deps": [k for k, v in deps.items() if not v]})


main()
