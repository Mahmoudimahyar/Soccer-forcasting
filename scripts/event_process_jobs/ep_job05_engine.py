"""EPJOB5 -- build + AUDIT the event-process engine (possession/territory/transition/attack/set-piece/
chance-quality), on a deterministic synthetic match. No network, no API. Proves the engine is importable
and its leakage gate + extractors behave, before any real snapshots are built (EPJOB6).

research_only / experimental.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ep_lib as L

try:
    from wcdrawlab.research.event_process import snapshot_features as SF
    from wcdrawlab.research.event_process import contracts as C
    from wcdrawlab.research.event_process import registry as REG
except Exception as e:  # pragma: no cover
    L.emit("failed", reason=f"engine import failed: {e!r}")
    raise SystemExit(0)


def _synthetic():
    """Home(1) early goal + box-entry + corner; Away(2) late goal (must be invisible @30); ET shot excluded."""
    return [
        {"index": 1, "period": 1, "minute": 0, "second": 0, "type": {"name": "Starting XI"}, "team": {"id": 1, "name": "Home"}},
        {"index": 2, "period": 1, "minute": 0, "second": 0, "type": {"name": "Starting XI"}, "team": {"id": 2, "name": "Away"}},
        {"index": 5, "period": 1, "minute": 8, "second": 0, "type": {"name": "Pass"}, "team": {"id": 1},
         "location": [100, 40], "pass": {"end_location": [110, 40]}},  # box entry (home)
        {"index": 6, "period": 1, "minute": 9, "second": 0, "type": {"name": "Pass"}, "team": {"id": 1},
         "location": [120, 0.5], "pass": {"type": {"name": "Corner"}, "end_location": [110, 40]}},  # corner
        {"index": 10, "period": 1, "minute": 10, "second": 0, "type": {"name": "Shot"}, "team": {"id": 1},
         "location": [110, 40], "shot": {"statsbomb_xg": 0.3, "outcome": {"name": "Goal"}}},  # home goal @10
        {"index": 12, "period": 1, "minute": 12, "second": 0, "type": {"name": "Ball Recovery"}, "team": {"id": 1},
         "location": [60, 40]},
        {"index": 20, "period": 1, "minute": 30, "second": 0, "type": {"name": "Shot"}, "team": {"id": 2},
         "location": [110, 40], "shot": {"statsbomb_xg": 0.1, "outcome": {"name": "Saved"}}},  # away shot @30
        {"index": 30, "period": 2, "minute": 70, "second": 0, "type": {"name": "Shot"}, "team": {"id": 2},
         "location": [110, 40], "shot": {"statsbomb_xg": 0.4, "outcome": {"name": "Goal"}}},  # away goal @70
        {"index": 40, "period": 3, "minute": 95, "second": 0, "type": {"name": "Shot"}, "team": {"id": 1},
         "location": [110, 40], "shot": {"statsbomb_xg": 0.5, "outcome": {"name": "Goal"}}},  # ET: excluded
    ]


def main():
    ev = _synthetic()
    ctx = SF.prepare_match(ev, "ep_engine_audit")
    checks = {}
    checks["home_away_resolved"] = ctx.home_team_id == 1 and ctx.away_team_id == 2
    checks["registry_canonical"] = (len(REG.ALL_MODELS) == 22 and REG.is_canonical("research.event_process.e7")
                                    and not REG.is_canonical("research.event_process.e99"))

    snap30 = SF.snapshot_features(ev, ctx, 30.0, "clock")
    # leakage: away goal @70 + ET @95 must be invisible at t=30
    checks["score_no_future_leak"] = snap30["goals_home"] == 1 and snap30["goals_away"] == 0
    checks["shots_at_30"] = snap30["shots_home"] == 1 and snap30["shots_away"] == 1
    checks["box_entry_extracted"] = snap30["box_entries_home"] >= 1
    checks["corner_extracted"] = snap30["corners_home"] >= 1
    checks["recovery_extracted"] = snap30["recoveries_home"] >= 1
    checks["possession_present"] = snap30["poss_actions_home"] >= 1
    checks["territory_present"] = snap30["final_third_actions_home"] >= 1

    sliced = SF.events_up_to(ev, 30.0)
    checks["events_up_to_gate"] = all(SF.event_clock(e) <= 30.0 + 1e-9 for e in sliced)
    checks["regulation_only"] = all(e.get("period") in (1, 2) for e in sliced)

    fin = SF.regulation_final(ev, ctx)
    checks["regulation_final_draw"] = fin["target_wdl"] == "D" and fin["reg_home_goals"] == 1 and fin["reg_away_goals"] == 1
    ng = SF.next_goal_after(ev, ctx, 30.0)
    checks["next_goal_away"] = ng["next_goal_side"] == "away"

    rep = SF.source_quality_report(ev, ctx)
    checks["source_quality_flags_valid"] = all(
        info["quality"] in C.QUALITY_FLAGS for info in rep.capabilities.values())

    all_ok = all(checks.values())
    L.write_json("ep_engine_audit.json", {
        "engine_version": SF.ENGINE_VERSION, "schema_version": C.SCHEMA_VERSION,
        "n_canonical_models": len(REG.ALL_MODELS), "checks": checks, "all_ok": all_ok, "utc": L.utc(),
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
    })
    failed = [k for k, v in checks.items() if not v]
    L.emit("complete" if all_ok else "failed",
           reason=f"engine audit checks={len(checks)} all_ok={all_ok} failed={failed} version={SF.ENGINE_VERSION}",
           state_updates={"engine_audit_ok": all_ok, "engine_version": SF.ENGINE_VERSION})


main()
