"""PHASE 8 — Durable, bounded single-cycle prospective score harvester runner.

Invoked by Task Scheduler (WorldCupProspectiveScoreHarvester). NOT a loop, NOT a reasoning agent.
One cycle: acquire global lock -> heartbeat -> refresh ONLY final results if any universe fixture is
non-final (else offline) -> run the idempotent harvester (append-only) -> compute terminal condition ->
write state + JSONL log -> release lock. Never calls The Odds API. Never touches frozen predictions or
the collector. Disables itself logically (writes terminal state) when the locked universe is fully resolved.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "prospective_harvest"))
from _harvest_common import PRED_LEDGER, SCORING_ROOT, stamp_labels, write_json  # noqa: E402
from refresh_prospective_final_results import RESULTS_CSV  # noqa: E402
from prospective_score_harvester_v1 import EXCLUSIONS, SCORED_CSV  # noqa: E402

PY = sys.executable
LOCK = SCORING_ROOT / ".harvester.lock"
HEARTBEAT = SCORING_ROOT / "harvester_heartbeat.json"
STATE = SCORING_ROOT / "harvester_state.json"
LOG = SCORING_ROOT / "harvester_log.jsonl"
LOCK_STALE_S = 1800


def now():
    return datetime.now(timezone.utc)


def _log(event: dict):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(stamp_labels({"ts": now().isoformat(), **event}), default=str) + "\n")


def _heartbeat(status, extra=None):
    write_json(HEARTBEAT, stamp_labels({"ts": now().isoformat(), "status": status, **(extra or {})}))


def acquire_lock() -> bool:
    if LOCK.exists():
        try:
            age = (now() - datetime.fromisoformat(json.loads(LOCK.read_text())["ts"])).total_seconds()
            if age < LOCK_STALE_S:
                return False
        except Exception:
            pass
    write_json(LOCK, {"ts": now().isoformat(), "pid": "scheduled"})
    return True


def release_lock():
    try:
        LOCK.unlink()
    except Exception:
        pass


def run(cmd):
    return subprocess.run([PY] + cmd, cwd=str(HERE.parent), capture_output=True, text=True)


def universe_fixages():
    preds = pd.read_csv(PRED_LEDGER)
    return set(preds["match_id"].unique())


def refresh_needed(universe) -> bool:
    if not RESULTS_CSV.exists():
        return True
    res = pd.read_csv(RESULTS_CSV)
    vf = set(res[res.reconciliation_status == "verified_final"]["canonical_fixture_id"])
    return not universe.issubset(vf)


def terminal_status(universe):
    scored = set(pd.read_csv(SCORED_CSV)["canonical_fixture_id"]) if SCORED_CSV.exists() else set()
    excl = set(pd.read_csv(EXCLUSIONS)["canonical_fixture_id"]) if EXCLUSIONS.exists() and pd.read_csv(EXCLUSIONS).shape[0] else set()
    cancelled = postponed = set()
    if RESULTS_CSV.exists():
        res = pd.read_csv(RESULTS_CSV)
        cancelled = set(res[res.reconciliation_status == "fixture_cancelled"]["canonical_fixture_id"])
        postponed = set(res[res.reconciliation_status == "fixture_postponed"]["canonical_fixture_id"])
    resolved = scored | excl | cancelled | postponed
    unresolved = universe - resolved
    return {"universe": len(universe), "scored": len(scored & universe), "excluded": len(excl & universe),
            "cancelled": len(cancelled & universe), "postponed": len(postponed & universe),
            "unresolved": sorted(unresolved), "is_terminal": len(unresolved) == 0}


def main():
    SCORING_ROOT.mkdir(parents=True, exist_ok=True)
    if not acquire_lock():
        _heartbeat("skipped_locked"); _log({"event": "skip", "reason": "locked"})
        print("skip: another cycle holds the lock"); return
    try:
        _heartbeat("working")
        universe = universe_fixages()
        need = refresh_needed(universe)
        rr = run(["scripts/refresh_prospective_final_results.py"] + ([] if need else ["--offline"]))
        hr = run(["scripts/prospective_score_harvester_v1.py"])
        term = terminal_status(universe)
        integ = json.loads((SCORING_ROOT / "scoring_integrity_audit.json").read_text()) if (SCORING_ROOT / "scoring_integrity_audit.json").exists() else {}
        state = stamp_labels({"ts": now().isoformat(),
                              "refresh_rc": rr.returncode, "refresh_mode": "network" if need else "offline",
                              "harvest_rc": hr.returncode, "integrity_all_ok": integ.get("all_ok"),
                              "terminal": term, "odds_api_called": False})
        write_json(STATE, state)
        _heartbeat("terminal" if term["is_terminal"] else "ok", {"terminal": term["is_terminal"]})
        _log({"event": "cycle", "refresh_rc": rr.returncode, "harvest_rc": hr.returncode,
              "is_terminal": term["is_terminal"], "scored": term["scored"], "excluded": term["excluded"]})
        print(f"cycle ok | refresh_rc={rr.returncode}({'net' if need else 'offline'}) harvest_rc={hr.returncode} "
              f"terminal={term['is_terminal']} scored={term['scored']}/{term['universe']} "
              f"excluded={term['excluded']} integrity_ok={integ.get('all_ok')}")
    finally:
        release_lock()


if __name__ == "__main__":
    main()
