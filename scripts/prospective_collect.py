"""Durable prospective collector (V1.5) — SAFE BY DEFAULT (dry-run unless --execute).

Captures frozen-M2 research predictions for queued future 2026 matches:
  - pre-match windows (T-90, T-15) are DETERMINISTIC (state = 0-0, minute 0, Elo anchor from queue) and
    need no API call;
  - in-play windows require a live read via the read-only API-Football adapter (only with --execute).
First-write-wins immutable ledger; bounded single pass (no infinite loop); no-op when nothing is due;
never trades; never changes the model.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.final_holdout import load_frozen  # noqa: E402
from wcdrawlab.operations.ledger import ImmutableLedger  # noqa: E402
from wcdrawlab.operations.session import SessionManifest, now_iso  # noqa: E402
from wcdrawlab.operations.windows import capture_plan  # noqa: E402
from wcdrawlab.operations import prospective as PRO  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(ROOT / "data/reference/future_2026_prospective_queue.csv"))
    ap.add_argument("--ledger", default=str(ROOT / "data/processed/prospective/ledger.jsonl"))
    ap.add_argument("--session-dir", default=str(ROOT / "data/processed/prospective/sessions"))
    ap.add_argument("--config", default=str(ROOT / "configs/final_holdout_model_m2.yaml"))
    ap.add_argument("--now", default=now_iso(), help="ISO decision-time anchor (default: real UTC now)")
    ap.add_argument("--session-id", default="dryrun")
    ap.add_argument("--execute", action="store_true", help="actually write/fetch (default: dry-run plan only)")
    a = ap.parse_args()

    model = load_frozen(a.config)
    sess = SessionManifest(a.session_dir, a.session_id)
    sess.heartbeat("starting", now=a.now, execute=a.execute)
    if not Path(a.queue).exists():
        print(f"no queue at {a.queue} -> no-op"); sess.shutdown_summary(); return
    q = pd.read_csv(a.queue)
    elig = q[q.get("state", "eligible").astype(str) == "eligible"] if "state" in q.columns else q
    ledger = ImmutableLedger(a.ledger) if a.execute else None
    existing = ledger.keys() if ledger else set()

    planned = captured = skipped = missed = 0
    for r in elig.itertuples():
        plan = capture_plan(r.kickoff_utc, a.now)
        for w in plan:
            key = f"{r.match_id}:{w['window']}"
            if w["status"] == "missed" and key not in existing:
                sess.mark_missed(r.match_id, w["window"]); missed += 1
                continue
            if w["status"] != "due":
                continue
            if key in existing:
                sess.log("duplicate", f"dup:{key}", match_id=r.match_id, window=w["window"]); skipped += 1
                continue
            if w["phase"] == "pre_match":
                state = {"elo_delta_home": float(getattr(r, "elo_delta_home", 0.0)),
                         "decision_minute": 0, "score_home": 0, "score_away": 0, "red_home": 0, "red_away": 0}
                rec = PRO.build_prediction_record(
                    match_id=r.match_id, kickoff_utc=r.kickoff_utc, phase="pre_match",
                    capture_window=w["window"], decision_minute=0, decision_timestamp=a.now,
                    retrieval_timestamp=a.now, event_source_timestamp=a.now, state=state,
                    frozen_model=model,
                    anchor_probs=(getattr(r, "anchor_p_home", 0.34), getattr(r, "anchor_p_draw", 0.33),
                                  getattr(r, "anchor_p_away", 0.33)),
                    source_hashes={"queue": str(getattr(r, "match_id"))})
                if a.execute:
                    res = ledger.record(key, rec)
                    sess.log("captured", f"cap:{key}", match_id=r.match_id, window=w["window"], wrote=res["wrote"])
                    captured += int(res["wrote"])
                else:
                    sess.log("planned", f"plan:{key}", match_id=r.match_id, window=w["window"], phase="pre_match")
                    planned += 1
            else:  # in_play -> needs a live read (execute only)
                if not a.execute:
                    sess.log("planned", f"plan:{key}", match_id=r.match_id, window=w["window"], phase="in_play")
                    planned += 1
                    continue
                sess.log("inplay_requires_live_source", f"live:{key}", match_id=r.match_id, window=w["window"],
                         note="adapter fetch path; enable when source verified")
                skipped += 1
    summary = sess.shutdown_summary()
    print(f"{'EXECUTE' if a.execute else 'DRY-RUN'} now={a.now} | planned={planned} captured={captured} "
          f"skipped={skipped} missed={missed} | eligible_matches={len(elig)}")
    print(f"manifest: {sess.manifest}")


if __name__ == "__main__":
    main()
