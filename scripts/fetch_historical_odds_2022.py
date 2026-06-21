"""Pull 2022 World Cup group-stage PRE-KICKOFF odds from The Odds API historical endpoint
and normalize to no-vig consensus market features (a backtestable baseline B6 for the 2022 fold).

Strategy (credit-efficient): 1 discovery snapshot lists all 48 group matches + kickoff times;
then for each distinct kickoff time, one snapshot ~90 min before kickoff gives the latest
pre-kickoff line. Each historical call costs 10 credits per region per market.

Output: data/processed/market_features_2022.csv
  match_date, team_a, team_b, p_a_market, p_draw_market, p_b_market, market_total_goals,
  n_books, snapshot_time, commence_time
"""
from __future__ import annotations

import json
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
SPORT = "soccer_fifa_world_cup"
BASE = "https://api.the-odds-api.com/v4/historical/sports/{}/odds".format(SPORT)
RAWDIR = ROOT / "data" / "raw" / "odds" / "historical_2022"
OUT = ROOT / "data" / "processed" / "market_features_2022.csv"

EXTRA = {"USA": "United States", "South Korea": "Korea Republic", "Czech Republic": "Czechia",
         "Bosnia & Herzegovina": "Bosnia", "Curaçao": "Curacao", "DR Congo": "Congo DR"}


def canon(n):
    return EXTRA.get(str(n).strip(), canonical_team_name(n))


def snapshot(date_iso: str, markets: str = "h2h"):
    r = requests.get(BASE, params={"apiKey": KEY, "regions": "us,uk,eu", "markets": markets,
                                   "oddsFormat": "decimal", "date": date_iso}, timeout=45)
    r.raise_for_status()
    return r.json(), int(r.headers.get("x-requests-last", 0)), r.headers.get("x-requests-remaining")


def consensus(event):
    pv, totals = [], []
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
            elif mk.get("key") == "totals":
                pts = [o.get("point") for o in mk.get("outcomes", []) if o.get("point") is not None]
                if pts:
                    totals.append(float(np.median(pts)))
        if h and d and a and h > 1 and d > 1 and a > 1:
            pv.append(no_vig_from_decimal_odds(np.array([h]), np.array([d]), np.array([a]))[0])
    if not pv:
        return None
    c = np.median(np.vstack(pv), axis=0); c = c / c.sum()
    return c, (float(np.median(totals)) if totals else np.nan), len(pv)


def main():
    RAWDIR.mkdir(parents=True, exist_ok=True)
    # 1) discovery: all 48 group matches + commence times
    disc, cost, rem = snapshot("2022-11-20T06:00:00Z", "h2h")
    print(f"[discovery] events={len(disc['data'])} cost={cost} remaining={rem}")
    by_ct = {}
    for e in disc["data"]:
        by_ct.setdefault(e["commence_time"], []).append((canon(e["home_team"]), canon(e["away_team"])))
    commence_times = sorted(by_ct)
    print(f"[discovery] {len(commence_times)} distinct kickoff slots, {sum(len(v) for v in by_ct.values())} matches")

    # 2) one pre-kickoff snapshot (~90 min before) per slot, markets h2h+totals
    rows = []
    total_cost = cost
    for ct in commence_times:
        ct_dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        snap_at = (ct_dt - timedelta(minutes=90)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            snap, c2, rem = snapshot(snap_at, "h2h,totals")
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] slot {ct} failed: {repr(e)[:80]}"); continue
        total_cost += c2
        (RAWDIR / f"{ct.replace(':','').replace('-','')}.json").write_text(
            json.dumps({"snapshot_time": snap.get("timestamp"), "data": snap["data"]}))
        for e in snap["data"]:
            if e["commence_time"] != ct:
                continue
            res = consensus(e)
            if not res:
                continue
            c, tot, nb = res
            rows.append({
                "match_date": ct[:10], "commence_time": ct, "snapshot_time": snap.get("timestamp"),
                "team_a": canon(e["home_team"]), "team_b": canon(e["away_team"]),
                "p_a_market": c[0], "p_draw_market": c[1], "p_b_market": c[2],
                "market_total_goals": tot, "n_books": nb,
            })
    df = pd.DataFrame(rows).drop_duplicates(subset=["team_a", "team_b", "match_date"])
    df.to_csv(OUT, index=False)
    print(f"[done] matches with market: {len(df)} | total credits spent this run: {total_cost} | remaining: {rem}")
    print(df[["match_date", "team_a", "team_b", "p_a_market", "p_draw_market", "p_b_market", "n_books"]]
          .head(10).to_string(index=False))


if __name__ == "__main__":
    main()
