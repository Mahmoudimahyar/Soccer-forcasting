"""Phase 1: API-Football empirical capability audit (<=30 read-only requests, hard-capped).
Uses the existing ApiFootballReadOnly adapter + KNOWN league IDs (avoids the non-allowlisted /leagues).
Raw responses persisted append-only + gitignored. Key loaded read-only; never printed. research_only.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import safe_config  # noqa: E402
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly, QuotaExceeded  # noqa: E402

RAW = ROOT / "data/raw/api_football_audit"
# (label, league_id, season) — standard API-Sports v3 IDs
COMPS = [
    ("FIFA_WC_2022", 1, 2022), ("UEFA_Euro_2024", 4, 2024), ("Copa_America_2024", 9, 2024),
    ("AFCON_2023", 6, 2023), ("AFC_Asian_Cup_2023", 7, 2023),
    ("UCL_2023", 2, 2023), ("EPL_2023", 39, 2023), ("LaLiga_2023", 140, 2023),
    ("Bundesliga_2023", 78, 2023), ("SerieA_2023", 135, 2023), ("Ligue1_2023", 61, 2023),
]
INTL = {"FIFA_WC_2022", "UEFA_Euro_2024", "Copa_America_2024", "AFCON_2023", "AFC_Asian_Cup_2023"}


def main():
    st = safe_config.load_paid_keys()
    print("API_FOOTBALL_KEY:", st["API_FOOTBALL_KEY"])
    if st["API_FOOTBALL_KEY"] != "SET":
        print("key missing -> abort (no calls made)"); return
    af = ApiFootballReadOnly(daily_budget=30, reserve=0, min_interval_s=2.0, raw_dir=RAW)

    rows = []
    plan = {}
    try:
        sres = af.get("/status")
        if sres["ok"] and sres["response"]:
            acc = sres["response"]
            plan = {"plan": acc.get("subscription", {}).get("plan"),
                    "requests_current": acc.get("requests", {}).get("current"),
                    "requests_limit_day": acc.get("requests", {}).get("limit_day")}
        print("plan:", json.dumps(plan))
    except QuotaExceeded:
        pass

    for label, lid, season in COMPS:
        if af.remaining_budget() <= 0:
            break
        try:
            f = af.get("/fixtures", {"league": lid, "season": season})
        except QuotaExceeded:
            break
        fixtures = f.get("response", []) if f["ok"] else []
        finished = [x for x in fixtures if (x.get("fixture", {}).get("status", {}).get("short") == "FT")]
        row = {"label": label, "league": lid, "season": season, "ok": f["ok"],
               "n_fixtures": len(fixtures), "n_finished": len(finished),
               "has_timestamp": bool(fixtures and fixtures[0].get("fixture", {}).get("timestamp")),
               "has_score": bool(finished and finished[0].get("goals", {}).get("home") is not None),
               "errors": f.get("errors")}
        # deep sample for international tournaments (+ UCL as a club control), budget permitting
        deep = (label in INTL) or (label == "UCL_2023")
        sample_fid = finished[0]["fixture"]["id"] if finished else None
        ev = ln = stx = pl = None
        if deep and sample_fid and af.remaining_budget() > 0:
            try:
                ev = af.get("/fixtures/events", {"fixture": sample_fid})
                if af.remaining_budget() > 0:
                    ln = af.get("/fixtures/lineups", {"fixture": sample_fid})
                if label in ("FIFA_WC_2022", "UEFA_Euro_2024") and af.remaining_budget() > 0:
                    stx = af.get("/fixtures/statistics", {"fixture": sample_fid})
                if label == "FIFA_WC_2022" and af.remaining_budget() > 0:
                    pl = af.get("/fixtures/players", {"fixture": sample_fid})
            except QuotaExceeded:
                pass
        row.update(_analyze_events(ev))
        row.update(_analyze_lineups(ln))
        row.update(_analyze_stats(stx))
        row.update(_analyze_players(pl))
        rows.append(row)
        print(f"  {label}: fixtures={row['n_fixtures']} finished={row['n_finished']} "
              f"events={row.get('event_types')} lineups={row.get('lineup_ok')} reqs={af.stats.requests_made}")

    summary = {"plan": plan, "requests_made": af.stats.requests_made, "competitions": rows}
    (ROOT / "data/reference").mkdir(parents=True, exist_ok=True)
    (ROOT / "data/reference/api_football_empirical_coverage.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    cols = ["label", "league", "season", "ok", "n_fixtures", "n_finished", "has_timestamp", "has_score",
            "event_types", "n_events", "has_goal", "has_owngoal", "has_card", "has_red", "has_subst", "has_var",
            "lineup_ok", "has_formation", "has_bench", "has_player_id", "has_position", "stats_ok", "has_shots",
            "has_xg", "players_ok", "player_positions"]
    with open(ROOT / "data/reference/api_football_empirical_coverage.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"TOTAL requests made: {af.stats.requests_made} (cap 30)")


def _analyze_events(ev):
    if not ev or not ev.get("ok"):
        return {"event_types": None, "n_events": 0}
    resp = ev.get("response", [])
    types = {}
    has = {"goal": False, "owngoal": False, "card": False, "red": False, "subst": False, "var": False}
    for e in resp:
        t = (e.get("type") or "").lower(); d = (e.get("detail") or "").lower()
        types[t] = types.get(t, 0) + 1
        if t == "goal":
            has["goal"] = True
            if "own" in d:
                has["owngoal"] = True
        if t == "card":
            has["card"] = True
            if "red" in d:
                has["red"] = True
        if t == "subst":
            has["subst"] = True
        if t == "var":
            has["var"] = True
    return {"event_types": ",".join(sorted(types)), "n_events": len(resp), "has_goal": has["goal"],
            "has_owngoal": has["owngoal"], "has_card": has["card"], "has_red": has["red"],
            "has_subst": has["subst"], "has_var": has["var"]}


def _analyze_lineups(ln):
    if not ln or not ln.get("ok") or not ln.get("response"):
        return {"lineup_ok": False}
    t0 = ln["response"][0]
    start = t0.get("startXI", []) or []
    pid = bool(start) and (start[0].get("player", {}).get("id") is not None)
    pos = bool(start) and (start[0].get("player", {}).get("pos") is not None)
    return {"lineup_ok": True, "has_formation": bool(t0.get("formation")),
            "has_bench": bool(t0.get("substitutes")), "has_player_id": pid, "has_position": pos}


def _analyze_stats(stx):
    if not stx or not stx.get("ok") or not stx.get("response"):
        return {"stats_ok": False}
    stats = stx["response"][0].get("statistics", []) or []
    names = {(s.get("type") or "").lower() for s in stats}
    return {"stats_ok": True, "has_shots": any("shot" in n for n in names),
            "has_xg": any("expected" in n or n == "expected_goals" for n in names)}


def _analyze_players(pl):
    if not pl or not pl.get("ok") or not pl.get("response"):
        return {"players_ok": False}
    teams = pl["response"]
    players = teams[0].get("players", []) if teams else []
    pos = bool(players) and (players[0].get("statistics", [{}])[0].get("games", {}).get("position") is not None)
    return {"players_ok": True, "player_positions": pos}


if __name__ == "__main__":
    main()
