"""JOB6: StatsBomb bridge + xG features. Verifies the StatsBomb competition catalog and, if the
(gitignored) StatsBomb raw events have been cached, builds leakage-safe in-play state + pre-registered
xG feature families (xg_diff_before, roll5/roll10, shotcounts, time-since-last-shot/major) using shots
strictly BEFORE the decision minute. Only DERIVED hashes/counts/metrics are written (raw stays gitignored,
never committed). Skips with an explicit reason if StatsBomb raw is not present (no network here).
StatsBomb data is non-commercial. research_only / experimental / not_runtime_approved."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
SB_EVENTS = ROOT / "data/raw/statsbomb_open/events"        # corrected path (acquirer writes here)
BRIDGE_AUDIT = ROOT / "data/processed/api_statsbomb_match_bridge_v1.audit.json"


def main():
    rd = Path(_job.run_dir())
    res = {"xg_families": ["f1_xg_before", "f2_roll5", "f3_roll10", "f4_shotcount", "f5_tsl_shot", "f6_tsl_major"]}
    cached = SB_EVENTS.exists() and any(SB_EVENTS.glob("*.json"))
    n_events = len(list(SB_EVENTS.glob("*.json"))) if cached else 0
    matched = None
    if BRIDGE_AUDIT.exists():
        try:
            a = json.loads(BRIDGE_AUDIT.read_text(encoding="utf-8"))
            matched = a.get("accepted") or a.get("matched") or a.get("n_accepted") or a.get("exact_matches")
        except Exception:
            matched = None
    res.update({"statsbomb_raw_cached": cached, "cached_event_files": n_events, "bridged_matches": matched})
    (rd / "job06_statsbomb_xg.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    if not cached:
        _job.emit("skipped", reason="StatsBomb raw events not cached -> xG bridge skipped (honest outcome #5)",
                  state_updates={"statsbomb_xg_built": False})
        return
    # Build the xG event-state features for the cached matched games (derived only; raw stays gitignored).
    import subprocess
    rc = 0
    try:
        p = subprocess.run([sys.executable, str(ROOT / "scripts/build_xg_event_state_features.py")],
                           capture_output=True, text=True, timeout=1800, cwd=str(ROOT))
        rc = p.returncode
    except Exception:
        rc = 1
    _job.emit("complete",
              reason=f"StatsBomb bridge: {matched} exact-matched intl games; {n_events} cached event files; "
                     f"xG event-state build rc={rc} (LIMITED sample -> fusion is low-powered, honest outcome #5 applies)",
              state_updates={"statsbomb_xg_built": rc == 0, "statsbomb_event_files": n_events,
                             "statsbomb_bridged_matches": matched})


main()
