"""LK_JOB01 -- preflight + dependency + isolation + test-baseline + dry-run note.

Verifies, with NO writes outside this worktree and NO external network, that:
  (1) ISOLATION -- we are NOT inside the active collector checkout; data_roots' forbidden list contains
      the collector; no data root resolves into the collector; the persistent lake lives OUTSIDE every
      git worktree; the lake objects/ tree is 0 git-tracked in this worktree; raw/ is 0 git-tracked;
      the active collector commit is read read-only (drift is recorded, not failed -- independent system).
  (2) DEPENDENCY -- the inputs the restoration depends on are PRESENT: the exact international bridge CSV,
      the lake roots/contract configs, the lake engine + event_process engine import clean, and the
      prior StatsBomb caches (the ~60 surviving files). Absent inputs are recorded honestly.
  (3) NO-FORBIDDEN-SOURCE STATIC CHECK -- every lk_job*.py is scanned for a forbidden network/provider/
      scrape import token at module scope; any hit is a hard preflight failure. The ONLY permitted
      external retrieval is the official StatsBomb Open Data events endpoint (owned by the engine).
  (4) TEST-BASELINE -- confirms the test dir + conftest + the lake-controller test module are present.
  (5) DRY-RUN NOTE -- records paper-only/research_only/offline-by-default mode + products to be produced.

Honest `failed` ONLY on a real isolation/safety breach (inside collector / root-in-collector / lake under
a worktree / forbidden import / raw or lake git-tracked / configs missing / engine import error).
A missing prior cache downgrades to a recorded gap, not a false complete.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk


def main():
    # (1) isolation ---------------------------------------------------------------------------------
    inside_collector = _lk.COLLECTOR_FORBIDDEN in str(_lk.ROOT).replace("\\", "/")
    root_in_collector = _lk.roots_resolving_into_collector()

    forbidden_ok = False
    dr_err = None
    forbidden_list = []
    try:
        DR = _lk.data_roots()
        forbidden_list = [str(p).replace("\\", "/") for p in DR.forbidden_roots()]
        forbidden_ok = any(_lk.COLLECTOR_FORBIDDEN in f for f in forbidden_list)
    except Exception as e:
        dr_err = repr(e)

    lake_external = None
    lake_root = None
    lake_index_n = None
    lake_err = None
    try:
        L = _lk.lake_engine()
        lake = L.Lake.resolve()  # raises if it would live inside a worktree / collector
        lake_root = str(lake.root)
        norm = lake_root.replace("\\", "/")
        lake_external = ("worldcup-international-event-lake" not in norm
                         and _lk.COLLECTOR_FORBIDDEN not in norm)
        lake_index_n = len(L.read_index(lake))
    except Exception as e:
        lake_err = repr(e)
        lake_external = False

    coll_commit = _lk.collector_commit()
    collector_unchanged = (coll_commit == _lk.EXPECTED_COLLECTOR_COMMIT)
    raw_tracked = _lk.raw_git_tracked()
    lake_tracked = _lk.lake_objects_git_tracked()

    # (2) dependency --------------------------------------------------------------------------------
    bridge_csv = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/"
                      "api_statsbomb_match_bridge_v1.csv")
    prior_cache = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/raw/statsbomb_open")
    prior_event_files = len(list(prior_cache.glob("events/*.json")) + list(prior_cache.glob("*.json"))) \
        if prior_cache.exists() else 0
    ep_import_ok = True
    try:
        from wcdrawlab.research.event_process import snapshot_features as _SF  # noqa: F401
        from wcdrawlab.research.event_process import eval as _EE  # noqa: F401
    except Exception:
        ep_import_ok = False

    bridge_exact_n = None
    try:
        L = _lk.lake_engine()
        bridge_exact_n = len(L.load_exact_bridge())
    except Exception:
        bridge_exact_n = None

    deps = {
        "exact_bridge_csv": bridge_csv.exists(),
        "lake_roots_cfg": (_lk.ROOT / "configs/international_event_lake_roots.yaml").exists(),
        "lake_contract_cfg": (_lk.ROOT / "configs/international_event_lake_contract.yaml").exists(),
        "lake_engine_import": lake_err is None,
        "event_process_engine_import": ep_import_ok,
        "prior_statsbomb_cache": prior_event_files > 0,
        "exact_bridge_loadable": bridge_exact_n is not None,
    }
    deps_all_present = all(deps.values())

    # (3) no-forbidden-source static check ----------------------------------------------------------
    forbidden_imports = _lk.scan_forbidden_imports()

    # (4) test-baseline -----------------------------------------------------------------------------
    tests_dir = _lk.ROOT / "tests"
    test_baseline = {
        "tests_dir_present": tests_dir.exists(),
        "conftest_present": (tests_dir / "conftest.py").exists(),
        "lake_controller_test_present": (tests_dir / "test_lake_jobs_controller.py").exists(),
        "n_test_files": len(list(tests_dir.glob("test_*.py"))) if tests_dir.exists() else 0,
        "note": "the pytest suite is the gate; JOB13 final audit + the verifier run it",
    }

    # (5) dry-run note ------------------------------------------------------------------------------
    note = {
        "mode": "paper_only_research_only_offline_by_default",
        "external_retrieval_policy": "OFFICIAL StatsBomb Open Data events endpoint ONLY (engine-owned)",
        "forbidden_sources": ["api_football", "odds_api", "paid_provider", "scrape", "mirror",
                              "browser", "statsbomb_360", "statsbomb_video", "credentials"],
        "raw_event_json_location": "EXTERNAL content-addressed lake ONLY (never in any git worktree)",
        "never_touch": ["worldcup_draw_model_lab_FINAL (live collector)", "B1", "frozen M1-M5",
                        "candidate.py", "approved_models.yaml", "trading/Kalshi/risk", ".env",
                        "existing raw/manifests"],
        "products_to_produce": [
            "lake objects (init + restore-from-local + acquire-official)",
            "official catalog + selection manifest", "strict exact bridge classification",
            "legacy restoration manifest", "frozen cohort + exclusion + causal datasets",
            "match-level power", "strict forward-chain eval", "LOCO + calibration + bootstrap + ablations",
            "decision ledger + reproducibility + source-quality", "completion report + final integrity audit",
        ],
    }

    # ---- verdict: hard FAIL only on a real isolation/safety breach --------------------------------
    hard_breach = (inside_collector or bool(root_in_collector) or bool(forbidden_imports)
                   or bool(raw_tracked) or bool(lake_tracked) or not forbidden_ok
                   or not lake_external or lake_err is not None
                   or not deps["lake_engine_import"] or not deps["event_process_engine_import"]
                   or not deps["lake_roots_cfg"] or not deps["lake_contract_cfg"])

    _lk.write_json("lk_preflight.json", {
        "isolation": {
            "inside_active_collector": inside_collector,
            "forbidden_write_list_ok": forbidden_ok, "forbidden_roots": forbidden_list,
            "roots_resolving_into_collector": root_in_collector,
            "lake_root": lake_root, "lake_external_to_worktrees": lake_external,
            "lake_resolve_error": lake_err, "lake_index_objects": lake_index_n,
            "raw_data_git_tracked": bool(raw_tracked),
            "lake_objects_git_tracked": bool(lake_tracked),
            "collector_commit_readonly": coll_commit,
            "collector_commit_expected": _lk.EXPECTED_COLLECTOR_COMMIT,
            "collector_commit_unchanged": collector_unchanged,
            "data_roots_import_error": dr_err,
        },
        "dependency_artifacts": deps, "dependency_all_present": deps_all_present,
        "prior_statsbomb_event_files": prior_event_files, "bridge_exact_international": bridge_exact_n,
        "no_forbidden_source_static_check": {"forbidden_imports": forbidden_imports,
                                             "clean": not forbidden_imports,
                                             "official_only": _lk.OFFICIAL_HOST},
        "test_baseline": test_baseline,
        "dry_run_note": note, "utc": _lk.utc(), "labels": _lk.LABELS,
    })

    if hard_breach:
        _lk.emit("failed",
                 reason=f"preflight breach: inside_collector={inside_collector} "
                        f"roots_in_collector={root_in_collector} forbidden_imports={len(forbidden_imports)} "
                        f"raw_git_tracked={bool(raw_tracked)} lake_git_tracked={bool(lake_tracked)} "
                        f"forbidden_list_ok={forbidden_ok} lake_external={lake_external} "
                        f"lake_err={lake_err} ep_import={ep_import_ok}")
        return

    note_commit = ("collector_commit_unchanged" if collector_unchanged
                   else f"collector_commit_advanced_independently({coll_commit})")
    _lk.emit("complete",
             reason=f"isolated(not_in_collector={not inside_collector},forbidden_ok={forbidden_ok},"
                    f"no_root_in_collector={not root_in_collector},lake_external={lake_external}) "
                    f"no_forbidden_imports={not forbidden_imports} raw_untracked={not raw_tracked} "
                    f"lake_untracked={not lake_tracked} deps_present={deps_all_present} {note_commit} "
                    f"official_source_only=True",
             state_updates={"preflight_ok": True, "deps_all_present": deps_all_present,
                            "lake_root": lake_root, "lake_index_objects": lake_index_n,
                            "bridge_exact_international": bridge_exact_n,
                            "prior_statsbomb_event_files": prior_event_files,
                            "collector_commit": coll_commit, "collector_unchanged": collector_unchanged,
                            "missing_deps": [k for k, v in deps.items() if not v]})


main()
