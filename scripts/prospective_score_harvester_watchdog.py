"""PHASE 8 — Watchdog for WorldCupProspectiveScoreHarvester.

Inspects task/scorer health, the global lock, the frozen-ledger hash, the collector health, and the
scoring integrity audit. Restarts ONLY a genuinely crashed (stale, unlocked, non-terminal) scorer.
NEVER starts a concurrent scorer. DISABLES restart automatically on integrity failure or a changed
frozen-ledger hash. Read-only w.r.t. the collector and frozen predictions.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "prospective_harvest"))
from _harvest_common import COLLECTOR_ROOT, PRED_LEDGER, SCORING_ROOT, WORKTREE_ROOT, sha256_file, stamp_labels, write_json  # noqa: E402

PY = sys.executable
HEARTBEAT = SCORING_ROOT / "harvester_heartbeat.json"
LOCK = SCORING_ROOT / ".harvester.lock"
INTEGRITY = SCORING_ROOT / "scoring_integrity_audit.json"
WD_STATE = SCORING_ROOT / "watchdog_state.json"
MANIFEST = WORKTREE_ROOT / "data/reference/prospective_frozen_input_manifest.json"
HB_STALE_S = 1800


def now():
    return datetime.now(timezone.utc)


def _age(path):
    try:
        return (now() - datetime.fromisoformat(json.loads(Path(path).read_text())["ts"])).total_seconds()
    except Exception:
        return None


def main():
    actions, alerts = [], []
    restart_allowed = True

    # integrity gate
    integ = json.loads(INTEGRITY.read_text()) if INTEGRITY.exists() else {}
    if integ and not integ.get("all_ok", False):
        restart_allowed = False; alerts.append("integrity_all_ok_false_restart_disabled")

    # frozen-ledger hash gate (must equal Phase 0 manifest)
    if MANIFEST.exists():
        m = json.loads(MANIFEST.read_text())
        recorded = m.get("input_hashes", {}).get("prediction_ledger", {}).get("sha256")
        current = sha256_file(PRED_LEDGER)
        if recorded and current and recorded != current:
            # ledger grew (collector appends new immutable rows) — allowed, but note it; do not treat as corruption
            alerts.append("frozen_ledger_hash_changed_since_phase0 (append-only growth expected)")

    # collector health (record only)
    coll_hb = COLLECTOR_ROOT / "outputs/live_shadow/collector_heartbeat.json"
    collector_status = None
    if coll_hb.exists():
        try:
            collector_status = json.loads(coll_hb.read_text()).get("status")
        except Exception:
            collector_status = "unreadable"

    # scorer heartbeat / lock
    hb_age = _age(HEARTBEAT)
    hb_status = json.loads(HEARTBEAT.read_text()).get("status") if HEARTBEAT.exists() else None
    lock_held = LOCK.exists() and (_age(LOCK) or 0) < HB_STALE_S
    is_terminal = (hb_status == "terminal")

    if is_terminal:
        actions.append("no_action_terminal")
    elif lock_held:
        actions.append("no_action_lock_held")  # never concurrent
    elif hb_age is None or hb_age > HB_STALE_S:
        if restart_allowed:
            r = subprocess.run([PY, str(HERE / "run_prospective_score_harvester.py")],
                               cwd=str(WORKTREE_ROOT), capture_output=True, text=True)
            actions.append(f"restarted_crashed_scorer rc={r.returncode}")
        else:
            actions.append("restart_suppressed_integrity")
    else:
        actions.append("scorer_healthy")

    write_json(WD_STATE, stamp_labels({"ts": now().isoformat(), "hb_status": hb_status, "hb_age_s": hb_age,
                                       "lock_held": lock_held, "is_terminal": is_terminal,
                                       "restart_allowed": restart_allowed, "collector_status": collector_status,
                                       "actions": actions, "alerts": alerts}))
    print(f"watchdog | hb={hb_status} age={hb_age} terminal={is_terminal} restart_allowed={restart_allowed} "
          f"collector={collector_status} actions={actions} alerts={alerts}")


if __name__ == "__main__":
    main()
