"""Phase 3: data-quality audit over the pulled API-Football historical pilot (gitignored raw). Computes real
counts (matches, events, subs, cards, yellows, reds, second-yellows, own goals, lineups, player IDs,
positions), duplicate rate, and completeness. Writes data/processed/api_football_historical_coverage_summary.csv.
research_only. No raw text/keys in tracked outputs.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/api_football_historical"
OUT = ROOT / "data/processed/api_football_historical_coverage_summary.csv"


def _events_by_fixture():
    out = {}
    for fp in RAW.glob("fixtures_events_*.json"):
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        fid = (p.get("parameters") or {}).get("fixture")
        if fid is not None:
            out[str(fid)] = p.get("response", []) or []
    return out


def _lineups_by_fixture():
    out = {}
    for fp in RAW.glob("fixtures_lineups_*.json"):
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        fid = (p.get("parameters") or {}).get("fixture")
        if fid is not None:
            out[str(fid)] = p.get("response", []) or []
    return out


def main():
    ev = _events_by_fixture()
    ln = _lineups_by_fixture()
    fids = sorted(set(ev) | set(ln))
    agg = defaultdict(int)
    rows = []
    for fid in fids:
        events = ev.get(fid, [])
        lineups = ln.get(fid, [])
        yellows_by_player = defaultdict(int)
        n_sub = n_goal = n_owngoal = n_yellow = n_red = n_var = 0
        seen = set(); dups = 0
        for e in events:
            t = (e.get("type") or "").lower(); d = (e.get("detail") or "").lower()
            pid = (e.get("player") or {}).get("id")
            key = (t, d, pid, (e.get("time") or {}).get("elapsed"))
            if key in seen:
                dups += 1
            seen.add(key)
            if t == "goal":
                n_goal += 1
                if "own" in d:
                    n_owngoal += 1
            elif t == "card":
                if "red" in d:
                    n_red += 1
                elif "yellow" in d:
                    n_yellow += 1
                    if pid is not None:
                        yellows_by_player[pid] += 1
            elif t == "subst":
                n_sub += 1
            elif t == "var":
                n_var += 1
        second_yellows = sum(1 for c in yellows_by_player.values() if c >= 2)
        team0 = lineups[0] if lineups else {}
        starters = team0.get("startXI", []) or []
        has_pid = bool(starters) and (starters[0].get("player", {}).get("id") is not None)
        has_pos = bool(starters) and (starters[0].get("player", {}).get("pos") is not None)
        has_bench = bool(team0.get("substitutes"))
        has_form = bool(team0.get("formation"))
        rows.append({"fixture": fid, "n_events": len(events), "goals": n_goal, "own_goals": n_owngoal,
                     "yellows": n_yellow, "reds": n_red, "second_yellows": second_yellows, "subs": n_sub,
                     "var": n_var, "dups": dups, "lineups_teams": len(lineups), "player_ids": int(has_pid),
                     "positions": int(has_pos), "bench": int(has_bench), "formation": int(has_form)})
        agg["matches"] += 1
        agg["matches_with_events"] += int(bool(events))
        agg["matches_with_lineups"] += int(len(lineups) >= 2)
        agg["matches_with_player_ids"] += int(has_pid)
        for k in ("goals", "own_goals", "yellows", "reds", "subs", "var"):
            agg[k] += rows[-1][k.replace("goals", "goals")] if k in rows[-1] else 0
        agg["goals"] = agg["goals"]  # noqa (kept explicit below)
        agg["second_yellows"] += second_yellows
        agg["dups"] += dups
    # recompute clean aggregates
    tot = {k: sum(r[k] for r in rows) for k in ("goals", "own_goals", "yellows", "reds", "second_yellows",
                                                "subs", "var", "dups", "n_events")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["fixture"]); w.writeheader(); w.writerows(rows)
    summary = {"matches": agg["matches"], "matches_with_events": agg["matches_with_events"],
               "matches_with_lineups": agg["matches_with_lineups"],
               "matches_with_player_ids": agg["matches_with_player_ids"],
               "total_subs": tot["subs"], "total_yellows": tot["yellows"], "total_reds": tot["reds"],
               "total_second_yellows": tot["second_yellows"],
               "red_or_second_yellow": tot["reds"] + tot["second_yellows"],
               "total_own_goals": tot["own_goals"], "total_goals": tot["goals"],
               "total_events": tot["n_events"], "dup_events": tot["dups"],
               "dup_rate": round(tot["dups"] / tot["n_events"], 4) if tot["n_events"] else 0.0}
    (ROOT / "notes/research/_phase3_quality.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
