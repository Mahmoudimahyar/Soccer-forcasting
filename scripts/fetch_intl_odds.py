"""Build a large international-match PRE-KICKOFF odds dataset from The Odds API historical
endpoint, across many senior men's international competitions (2020-2025). This is the data
unlock that makes "can we beat the market" answerable on hundreds of matches, not 48.

Per competition window: 1+ discovery snapshots list all matches + kickoff times; then one
targeted snapshot ~90 min before each distinct kickoff slot gives a near-closing no-vig
consensus. Appends to data/processed/intl_odds_raw.csv (resumable: skips slots already saved).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from _live_env import load_keys  # noqa: E402
load_keys(verbose=False)
import os  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from wcdrawlab.market import no_vig_from_decimal_odds  # noqa: E402

KEY = os.environ["ODDS_API_KEY"]
OUT = ROOT / "data" / "processed" / "intl_odds_raw.csv"
REGIONS = "eu"               # eu has deep coverage for international matches (1 region = 10 credits)
MARKETS = "h2h"              # 1X2 only -> 10 credits per snapshot
CREDIT_FLOOR = 6000          # stop if remaining drops below this

# (sport_key, [discovery_dates]) — discovery lists all then-upcoming matches in that window.
WINDOWS = [
    ("soccer_uefa_european_championship", ["2021-06-11T06:00:00Z"]),   # Euro 2020
    ("soccer_uefa_european_championship", ["2024-06-14T06:00:00Z"]),   # Euro 2024
    ("soccer_conmebol_copa_america",      ["2024-06-20T06:00:00Z"]),   # Copa America 2024
    ("soccer_africa_cup_of_nations",      ["2022-01-09T06:00:00Z"]),   # AFCON 2021 (played 2022)
    ("soccer_africa_cup_of_nations",      ["2024-01-13T06:00:00Z"]),   # AFCON 2023 (played 2024)
    ("soccer_concacaf_gold_cup",          ["2025-06-14T06:00:00Z"]),   # Gold Cup 2025
    ("soccer_fifa_world_cup",             ["2022-11-20T06:00:00Z"]),   # WC 2022 (group + KO)
    ("soccer_uefa_nations_league", ["2022-06-01T06:00:00Z", "2022-09-20T06:00:00Z",
                                    "2023-06-13T06:00:00Z", "2024-09-04T06:00:00Z",
                                    "2024-10-09T06:00:00Z", "2024-11-13T06:00:00Z"]),
    ("soccer_uefa_euro_qualification", ["2023-03-20T06:00:00Z", "2023-09-05T06:00:00Z",
                                        "2023-10-09T06:00:00Z", "2023-11-13T06:00:00Z"]),
    ("soccer_fifa_world_cup_qualifiers_south_america", ["2024-09-03T06:00:00Z", "2024-10-08T06:00:00Z",
                                                        "2025-03-18T06:00:00Z", "2025-06-03T06:00:00Z"]),
]


def canon(n):
    return canonical_team_name(n)


def get(date_iso, sport):
    r = requests.get(f"https://api.the-odds-api.com/v4/historical/sports/{sport}/odds",
                     params={"apiKey": KEY, "regions": REGIONS, "markets": MARKETS,
                             "oddsFormat": "decimal", "date": date_iso}, timeout=45)
    if r.status_code >= 400:
        return None, 0, r.headers.get("x-requests-remaining")
    return r.json(), int(r.headers.get("x-requests-last", 0)), r.headers.get("x-requests-remaining")


def consensus(event):
    pv = []
    for bk in event.get("bookmakers", []):
        h = d = a = None
        for mk in bk.get("markets", []):
            if mk.get("key") == "h2h":
                for o in mk.get("outcomes", []):
                    if o["name"] == event["home_team"]:
                        h = o["price"]
                    elif o["name"] == event["away_team"]:
                        a = o["price"]
                    elif o["name"] == "Draw":
                        d = o["price"]
        if h and d and a and h > 1 and d > 1 and a > 1:
            pv.append(no_vig_from_decimal_odds(np.array([h]), np.array([d]), np.array([a]))[0])
    if not pv:
        return None
    c = np.median(np.vstack(pv), axis=0); c = c / c.sum()
    return c, len(pv)


def main():
    existing = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame()
    seen = set(zip(existing.get("sport", []), existing.get("commence_time", []),
                   existing.get("home", []), existing.get("away", []))) if len(existing) else set()
    rows = existing.to_dict("records") if len(existing) else []
    rem = None
    for sport, disc_dates in WINDOWS:
        slots = {}  # commence_time -> set of (home,away)
        for dd in disc_dates:
            j, cost, rem = get(dd, sport)
            if not j:
                continue
            for e in j.get("data", []):
                slots.setdefault(e["commence_time"], set()).add((e["home_team"], e["away_team"]))
        ncount = 0
        for ct in sorted(slots):
            if rem is not None and int(rem) < CREDIT_FLOOR:
                print(f"[stop] credit floor reached ({rem})"); break
            ct_dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
            snap_at = (ct_dt - timedelta(minutes=90)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            j, cost, rem = get(snap_at, sport)
            if not j:
                continue
            for e in j.get("data", []):
                if e["commence_time"] != ct:
                    continue
                ka = (sport, ct, e["home_team"], e["away_team"])
                if ka in seen:
                    continue
                res = consensus(e)
                if not res:
                    continue
                c, nb = res
                rows.append({"sport": sport, "commence_time": ct, "snapshot_time": j.get("timestamp"),
                             "home": canon(e["home_team"]), "away": canon(e["away_team"]),
                             "p_a_market": c[0], "p_draw_market": c[1], "p_b_market": c[2], "n_books": nb})
                seen.add(ka); ncount += 1
        pd.DataFrame(rows).to_csv(OUT, index=False)  # checkpoint after each competition
        print(f"[{sport}] +{ncount} matches | total {len(rows)} | credits remaining {rem}")
    print(f"[done] total matches: {len(rows)} | wrote {OUT}")


if __name__ == "__main__":
    main()
