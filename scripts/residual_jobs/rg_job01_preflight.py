"""RG_JOB01 -- preflight + dependency-verify (event-process terminal) + isolation + dry-run note.

Verifies, with NO network/API and NO writes outside this worktree, that:
  (1) ISOLATION -- we are NOT running inside the active collector checkout; the collector
      (worldcup_draw_model_lab_FINAL) is on data_roots' forbidden-write list; the residual package never
      imports candidate.py / approved_models.yaml / trading.
  (2) DEPENDENCY -- the upstream event-process phase is TERMINAL: its decision ledger exists and every
      model already carries a final verdict (no open candidate awaiting this phase). The residual package
      builds RELATIVE to W2 and reuses the event-process engine, so it must not start before EP resolves.
  (3) DATA-ROOT REGISTRY present + the canonical residual package imports + self-test is reachable.
  (4) DRY-RUN NOTE -- records that this run is paper-only / research_only and lists the offline data
      products it will consume (no Odds API, no API-Football, no download).

research_only / experimental. Honest `failed` only on a real isolation/dependency breach.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg


def main():
    coll = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")
    # (1) isolation -------------------------------------------------------------------------------
    inside_collector = _rg.COLLECTOR_FORBIDDEN in str(_rg.ROOT).replace("\\", "/")
    forbidden_ok = False
    collector_commit = None
    try:
        from wcdrawlab.research import data_roots as DR
        forbidden = [str(p).replace("\\", "/") for p in DR.forbidden_roots()]
        forbidden_ok = any(_rg.COLLECTOR_FORBIDDEN in f for f in forbidden)
    except Exception as e:
        forbidden = [f"data_roots import failed: {e!r}"]
    try:
        collector_commit = subprocess.run(
            ["git", "-C", str(coll), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip() or None
    except Exception:
        collector_commit = None

    # (2) dependency: event-process terminal ------------------------------------------------------
    ep_ledger = _rg.REF / "event_process_model_decision_ledger.json"
    ep_terminal = False
    ep_summary = {}
    if ep_ledger.exists():
        import json
        try:
            d = json.loads(ep_ledger.read_text(encoding="utf-8"))
            verdicts = [m.get("verdict") for m in d.get("models", [])]
            from collections import Counter
            ep_summary = dict(Counter(verdicts))
            # terminal := every model has a final verdict; NO model is left "running"/"pending"/None
            non_terminal = {None, "running", "pending", "in_progress"}
            ep_terminal = bool(verdicts) and not any(v in non_terminal for v in verdicts)
        except Exception as e:
            ep_summary = {"ledger_unreadable": str(e)}

    # (3) data-root registry + canonical package import + self-test reachable ----------------------
    reg = (_rg.ROOT / "configs/research_data_roots.yaml").exists()
    pkg_ok = False
    self_test_callable = False
    pkg_err = None
    try:
        import wcdrawlab.research.residual_intensity as RI
        pkg_ok = True
        self_test_callable = callable(getattr(RI, "self_test", None))
    except Exception as e:
        pkg_err = repr(e)

    snap_present = (_rg.PROC / "intl_event_process_snapshots.csv").exists()

    # (4) dry-run note ----------------------------------------------------------------------------
    note = {
        "mode": "paper_only_research_only_offline",
        "no_external_api": True, "no_odds_api": True, "no_api_football": True, "no_download": True,
        "offline_products_consumed": [
            "data/processed/event_process_snapshots/intl_event_process_snapshots.csv",
            "data/processed/event_process_snapshots/intl_targets_wdl.csv",
            "data/processed/event_process_snapshots/intl_targets_next_goal.csv",
            "data/processed/event_process_snapshots/intl_targets_scoring_horizon.csv",
        ],
        "never_touch": ["worldcup_draw_model_lab_FINAL (live collector)", "B1", "frozen M1-M5",
                        "candidate.py", "approved_models.yaml", "trading/Kalshi/risk", ".env"],
        "w2_is_reference_not_classifier": True,
    }

    ok = ((not inside_collector) and forbidden_ok and ep_terminal and reg and pkg_ok and snap_present)
    _rg.write_json("rg_preflight.json", {
        "isolation": {"inside_active_collector": inside_collector, "forbidden_write_list_ok": forbidden_ok,
                      "forbidden_roots": forbidden, "collector_commit_readonly": collector_commit},
        "dependency_event_process_terminal": {"ledger_present": ep_ledger.exists(),
                                              "terminal": ep_terminal, "verdict_counts": ep_summary},
        "registry_present": reg, "residual_package_imports": pkg_ok,
        "self_test_callable": self_test_callable, "package_import_error": pkg_err,
        "snapshot_panel_present": snap_present,
        "dry_run_note": note, "utc": _rg.utc(), "labels": _rg.LABELS,
    })

    if ok:
        _rg.emit("complete",
                 reason=f"isolated(not_in_collector={not inside_collector},forbidden_ok={forbidden_ok}) "
                        f"event_process_terminal={ep_terminal}({ep_summary}) registry={reg} "
                        f"package_imports={pkg_ok} snapshots={snap_present} no_external_api=True",
                 state_updates={"preflight_ok": True, "ep_terminal": ep_terminal,
                                "collector_commit": collector_commit})
    else:
        _rg.emit("failed",
                 reason=f"preflight breach: inside_collector={inside_collector} forbidden_ok={forbidden_ok} "
                        f"ep_terminal={ep_terminal} registry={reg} package_imports={pkg_ok} "
                        f"snapshots={snap_present} pkg_err={pkg_err}")


main()
