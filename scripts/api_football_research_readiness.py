"""Phase 5: compute ACTUAL research-readiness counts from the pilot corpus (no model training). Reuses the
quality-audit + reconcile readers. Emits data/processed/api_football_research_readiness.csv + the readiness
JSON. Counts are observed, not endpoint-implied. research_only.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import api_football_data_quality_audit as Q  # noqa: E402
import api_football_reconcile_events as RC  # noqa: E402

# adopted thresholds
T_LINEUP_SUB = 500
T_TIMESTAMPED = 500
T_RED_2Y = 150


def main():
    ev = Q._events_by_fixture()
    ln = Q._lineups_by_fixture()
    fids = sorted(set(ev) | set(ln))
    # per-fixture aggregation (reuse quality logic inline)
    matches = len(fids)
    with_events = with_lineups = with_pids = 0
    subs = yellows = reds = second_y = own_goals = goals = n_events = dups = 0
    for fid in fids:
        events = ev.get(fid, []); lineups = ln.get(fid, [])
        with_events += int(bool(events)); with_lineups += int(len(lineups) >= 2)
        yb = {}
        seen = set()
        for e in events:
            t = (e.get("type") or "").lower(); d = (e.get("detail") or "").lower()
            pid = (e.get("player") or {}).get("id")
            key = (t, d, pid, (e.get("time") or {}).get("elapsed"))
            if key in seen:
                dups += 1
            seen.add(key)
            n_events += 1
            if t == "goal":
                goals += 1
                if "own" in d:
                    own_goals += 1
            elif t == "card":
                if "red" in d:
                    reds += 1
                elif "yellow" in d:
                    yellows += 1
                    yb[pid] = yb.get(pid, 0) + 1
            elif t == "subst":
                subs += 1
        second_y += sum(1 for c in yb.values() if c >= 2)
        t0 = lineups[0] if lineups else {}
        st = t0.get("startXI", []) or []
        if st and st[0].get("player", {}).get("id") is not None:
            with_pids += 1
    red_or_2y = reds + second_y

    # reconcile
    fmap = RC._fixtures_map(); emap = RC._events_map()
    matched = [f for f in emap if f in fmap]
    exact = sum(1 for f in matched if (lambda r: r[0] == fmap[f]["home"] and r[1] == fmap[f]["away"])(RC.reconcile_one(emap[f], fmap[f])))

    # per-model-class readiness (observed vs threshold; pilot is a SAMPLE -> report counts + capacity note)
    readiness = {
        "pilot_matches": matches,
        "A_player_substitution": {
            "matches_with_lineups": with_lineups, "matches_with_player_ids": with_pids,
            "total_substitutions": subs,
            "threshold_lineup_sub": T_LINEUP_SUB,
            "pilot_meets": with_lineups >= T_LINEUP_SUB,
            "capacity_note": "2180 finished matches available in-source -> threshold reachable with more backfill",
        },
        "B_cards_red": {
            "yellows": yellows, "reds": reds, "second_yellows": second_y, "red_or_second_yellow": red_or_2y,
            "threshold_red_2y": T_RED_2Y, "pilot_meets": red_or_2y >= T_RED_2Y,
            "note": "rare events; scale backfill if pilot < 150",
        },
        "C_next_goal": {
            "timestamped_event_matches": with_events, "goals": goals, "own_goals": own_goals,
            "shots": "team-level only (statistics endpoint); per-shot/xG partial; shot-locations unavailable",
            "threshold_timestamped": T_TIMESTAMPED, "pilot_meets": with_events >= T_TIMESTAMPED,
            "capacity_note": "timestamped events verified for all finished matches -> threshold reachable",
        },
        "D_inplay_wdl": {
            "matches_reconciled_exact": exact, "matches_reconcile_attempted": len(matched),
            "score_exact_rate": round(exact / len(matched), 4) if matched else None,
            "matches_with_clean_timeline": with_events,
        },
        "dup_rate": round(dups / n_events, 4) if n_events else 0.0,
    }
    out = ROOT / "data/processed/api_football_research_readiness.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ["model_class", "key_metric", "value", "threshold", "pilot_meets", "capacity"],
        ["A_player_sub", "matches_with_lineups", with_lineups, T_LINEUP_SUB, with_lineups >= T_LINEUP_SUB, "reachable (2180 avail)"],
        ["A_player_sub", "total_substitutions", subs, "-", "-", "-"],
        ["B_cards_red", "red_or_second_yellow", red_or_2y, T_RED_2Y, red_or_2y >= T_RED_2Y, "scale backfill"],
        ["C_next_goal", "timestamped_event_matches", with_events, T_TIMESTAMPED, with_events >= T_TIMESTAMPED, "reachable"],
        ["C_next_goal", "shot_locations", "unavailable", "-", False, "provider gap"],
        ["D_inplay_wdl", "score_exact_rate", readiness["D_inplay_wdl"]["score_exact_rate"], "-", "-", "-"],
    ]
    with open(out, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    (ROOT / "notes/research/_phase5_readiness.json").write_text(json.dumps(readiness, indent=2), encoding="utf-8")
    print(json.dumps(readiness, indent=2))


if __name__ == "__main__":
    main()
