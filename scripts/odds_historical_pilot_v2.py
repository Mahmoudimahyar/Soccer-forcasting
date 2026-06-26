"""Phase 4: bounded Odds API HISTORICAL pilot (diagnostic only). <=30 credits; 2 snapshots (region=eu,
market=h2h) for the 6 PREDECLARED WC2022 fixtures. No-vig per bookmaker, median across bookmakers. Reads
usage headers; stops before exceeding the cap. Does NOT touch the active collector's odds budget ledger and
does NOT run a live loop. Key loaded read-only; URL/key never printed. research_only.
"""
import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import safe_config  # noqa: E402

SPORT = "soccer_fifa_world_cup"
HIST = f"https://api.the-odds-api.com/v4/historical/sports/{SPORT}/odds"
MAX_CREDITS = 30
SNAPSHOTS = ["2022-11-22T08:00:00Z", "2022-11-24T08:00:00Z"]
# predeclared fixtures (home, away, kickoff_utc, expectation, realized)
FIXTURES = [
    ("Argentina", "Saudi Arabia", "2022-11-22T10:00:00Z", "favorite", "away"),
    ("France", "Australia", "2022-11-22T16:00:00Z", "favorite", "home"),
    ("Denmark", "Tunisia", "2022-11-22T13:00:00Z", "balanced", "draw"),
    ("Mexico", "Poland", "2022-11-22T17:00:00Z", "balanced", "draw"),
    ("Brazil", "Serbia", "2022-11-24T19:00:00Z", "favorite", "home"),
    ("Uruguay", "South Korea", "2022-11-24T13:00:00Z", "balanced", "draw"),
]
ALIASES = {"south korea": {"south korea", "korea republic", "korea"}}


def _norm(s):
    return (s or "").strip().lower()


def _match_team(decl, actual):
    a, d = _norm(actual), _norm(decl)
    if a == d:
        return True
    return a in ALIASES.get(d, set())


def _novig(prices):
    """prices = {home,draw,away} decimal -> no-vig probabilities."""
    imp = {k: 1.0 / v for k, v in prices.items() if v and v > 1.0}
    if len(imp) != 3:
        return None
    s = sum(imp.values())
    return {k: imp[k] / s for k in imp}


def main():
    st = safe_config.load_paid_keys()
    print("ODDS_API_KEY:", st["ODDS_API_KEY"])
    if st["ODDS_API_KEY"] != "SET":
        print("key missing -> abort"); return
    import os
    import requests
    key = os.environ["ODDS_API_KEY"]
    credits_used = 0
    snapshots = []
    for ts in SNAPSHOTS:
        if credits_used + 10 > MAX_CREDITS:
            print(f"budget guard: stop before snapshot {ts} (would exceed {MAX_CREDITS})"); break
        params = {"apiKey": key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal", "date": ts}
        try:
            r = requests.get(HIST, params=params, timeout=30)
        except Exception as e:
            print("request error (sanitized):", type(e).__name__); break
        credits_used += 10
        remaining = r.headers.get("x-requests-remaining")
        print(f"snapshot {ts}: http={r.status_code} credits_used~{credits_used} x-requests-remaining={remaining}")
        if r.status_code == 401 or r.status_code == 403:
            print("auth/entitlement error -> stop"); break
        if r.status_code != 200:
            continue
        body = r.json()
        snapshots.append({"ts": ts, "data": body.get("data", []), "snapshot_ts": body.get("timestamp")})

    # extract predeclared fixtures
    rows = []
    for home, away, ko, exp, realized in FIXTURES:
        found = None
        snap_ts = None
        for snap in snapshots:
            for ev in snap["data"]:
                if _match_team(home, ev.get("home_team")) and _match_team(away, ev.get("away_team")):
                    found = ev; snap_ts = snap["snapshot_ts"] or snap["ts"]; break
            if found:
                break
        if not found:
            rows.append({"home": home, "away": away, "status": "not_found_in_snapshot", "n_books": 0}); continue
        # >=60 min before kickoff?
        try:
            ko_dt = datetime.fromisoformat(ko.replace("Z", "+00:00"))
            sn_dt = datetime.fromisoformat((snap_ts or ko).replace("Z", "+00:00"))
            mins_before = (ko_dt - sn_dt).total_seconds() / 60.0
        except Exception:
            mins_before = None
        # per-bookmaker no-vig
        per_book = []
        for bk in found.get("bookmakers", []):
            mk = next((m for m in bk.get("markets", []) if m.get("key") == "h2h"), None)
            if not mk:
                continue
            prices = {}
            for o in mk.get("outcomes", []):
                nm = _norm(o.get("name"))
                if _match_team(home, o.get("name")):
                    prices["home"] = o.get("price")
                elif _match_team(away, o.get("name")):
                    prices["away"] = o.get("price")
                elif nm == "draw":
                    prices["draw"] = o.get("price")
            nv = _novig(prices) if len(prices) == 3 else None
            if nv:
                per_book.append(nv)
        n_books = len(per_book)
        valid = n_books >= 3 and (mins_before is None or mins_before >= 60)
        med = None
        if per_book:
            med = {k: statistics.median([b[k] for b in per_book]) for k in ("home", "draw", "away")}
            s = sum(med.values()); med = {k: round(v / s, 4) for k, v in med.items()}
        rows.append({"home": home, "away": away, "expectation": exp, "realized": realized,
                     "n_books": n_books, "mins_before_ko": round(mins_before, 1) if mins_before else None,
                     "valid": valid, "p_home": med and med["home"], "p_draw": med and med["draw"],
                     "p_away": med and med["away"], "status": "ok" if valid else "insufficient_books_or_timing"})

    valid_rows = [r for r in rows if r.get("valid")]
    verdict = "sufficient" if len(valid_rows) >= 4 else "insufficient"
    out = ROOT / "data/processed/odds_historical_pilot_v2_coverage.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["home", "away", "expectation", "realized", "n_books", "mins_before_ko", "valid",
            "p_home", "p_draw", "p_away", "status"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    summary = {"credits_used_estimate": credits_used, "snapshots": len(snapshots),
               "valid_fixtures": len(valid_rows), "verdict": verdict,
               "retrieved_utc": datetime.now(timezone.utc).isoformat()}
    (ROOT / "notes/research/_phase4_odds.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
