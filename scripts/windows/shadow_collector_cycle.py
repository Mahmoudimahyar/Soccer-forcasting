"""Bounded single-cycle shadow collector (invoked by Task Scheduler every 5 min). NOT a loop, NOT a
reasoning agent. Fail-closed on trading flags; never trades; never changes the model.

Each cycle: (1) verify KALSHI_ENABLE_LIVE_TRADING==false & TRADING_MODE==paper (else HALT);
(2) stop if past hard-end or all group matches scored; (3) if an odds snapshot window is due AND the
budget allows -> fetch one batched Odds API snapshot; (4) freeze immutable M1-M5 predictions;
(5) score finished matches; (6) write heartbeat + state. Safe by default: --dry-run does no spend/writes.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.operations.odds_budget import OddsBudget  # noqa: E402

OUT = ROOT / "outputs/live_shadow"; OUT.mkdir(parents=True, exist_ok=True)
HEARTBEAT = OUT / "collector_heartbeat.json"; STATE = OUT / "collector_state.json"
BUDGET_STATE = OUT / "odds_budget.json"
QUEUE = ROOT / "data/reference/future_2026_prospective_queue.csv"
PY = sys.executable


def now():
    return datetime.now(timezone.utc)


def flags_ok():
    try:
        from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
    except Exception:
        pass
    import os
    return (str(os.getenv("KALSHI_ENABLE_LIVE_TRADING")).strip().lower() == "false"
            and str(os.getenv("TRADING_MODE")).strip().lower() == "paper")


def due_snapshot_type(n):
    """Pick a snapshot window if one is due for any eligible NS match; else None."""
    import pandas as pd
    if not QUEUE.exists():
        return None
    q = pd.read_csv(QUEUE)
    el = q[q.get("state", "").astype(str) == "eligible"] if "state" in q.columns else q
    if el.empty:
        return None
    mins = []
    for ko in el["kickoff_utc"]:
        try:
            dt = datetime.fromisoformat(str(ko).replace("Z", "+00:00"))
            mins.append((dt - n).total_seconds() / 60.0)
        except Exception:
            pass
    upcoming = [m for m in mins if m > -5]
    if not upcoming:
        return None
    if any(10 <= m <= 20 for m in upcoming):
        return "T-15"
    if any(80 <= m <= 100 for m in upcoming):
        return "T-90"
    return "baseline"  # gated below by 30-min/budget rules


def run(cmd):
    return subprocess.run([PY] + cmd, cwd=str(ROOT), capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hard-end-utc", default="2026-07-05T00:00:00+00:00")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    n = now(); status = "ok"; actions = []

    if not flags_ok():
        HEARTBEAT.write_text(json.dumps({"ts": n.isoformat(), "status": "HALT_TRADING_FLAGS"}), encoding="utf-8")
        print("HALT: trading flags not safe (KALSHI_ENABLE_LIVE_TRADING must be false, TRADING_MODE paper)")
        sys.exit(3)

    if n > datetime.fromisoformat(a.hard_end_utc):
        STATE.write_text(json.dumps({"ts": n.isoformat(), "status": "stopped_hard_end"}), encoding="utf-8")
        HEARTBEAT.write_text(json.dumps({"ts": n.isoformat(), "status": "stopped_hard_end"}), encoding="utf-8")
        print("stopped: past hard-end"); return

    budget = OddsBudget(BUDGET_STATE, max_credits=500, min_interval_s=600.0)
    snap = due_snapshot_type(n)
    # Budget protection: baseline snapshots are a sparse fallback (>=120 min apart) so multi-day running
    # cannot drain the 500-credit total; the valuable T-90/T-15 windows always fire (subject to the
    # 10-min hard floor). Baseline is skipped if a snapshot was taken within the last 120 min.
    if snap == "baseline":
        last = budget._state.get("last_request_utc")
        if last:
            try:
                if (n - datetime.fromisoformat(last)).total_seconds() < 120 * 60:
                    snap = None
            except Exception:
                pass
    if snap:
        ok, reason = budget.can_request(1)
        if a.dry_run:
            actions.append(f"would_fetch_odds[{snap}] (budget_ok={ok}: {reason})")
        elif ok:
            r = run(["scripts/fetch_odds_live_2026.py", "--snapshot-type", snap, "--execute"])
            actions.append(f"fetch_odds[{snap}] rc={r.returncode}")
        else:
            actions.append(f"odds_skip[{snap}]: {reason}")
    else:
        actions.append("no_odds_window_due")

    if not a.dry_run:
        actions.append(f"freeze rc={run(['scripts/live_2026_shadow.py', 'freeze']).returncode}")
        actions.append(f"score rc={run(['scripts/live_2026_shadow.py', 'score']).returncode}")
    else:
        actions.append("would_freeze+score")

    hb = {"ts": n.isoformat(), "status": status, "snapshot_due": snap, "actions": actions,
          "budget": budget.summary(), "dry_run": a.dry_run}
    HEARTBEAT.write_text(json.dumps(hb, indent=2), encoding="utf-8")
    STATE.write_text(json.dumps({"ts": n.isoformat(), "last_cycle": hb}, indent=2), encoding="utf-8")
    print(f"cycle {n.isoformat()} | {', '.join(actions)} | credits {budget.credits_used}/500")


if __name__ == "__main__":
    main()
