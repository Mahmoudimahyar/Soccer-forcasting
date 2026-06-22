"""Fetch a competition's group-stage events from API-Football (free tier, 2022-2024) and build its
in-play state table (research-only). Bounded, throttled (<=10/min), cached/idempotent, append-only.
Pre-match Elo from elo_history.csv. Does NOT touch protected code.

Usage: python scripts/build_multicomp_inplay.py --league 4 --season 2024 --competition-id EURO2024
"""
import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except Exception:
    pass
import os
import requests
from wcdrawlab.research.inplay_dataset import build_state_for_competition  # noqa: E402

BASE = "https://v3.football.api-sports.io"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--league", type=int, required=True)
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--competition-id", required=True)
    p.add_argument("--max-events", type=int, default=45)
    p.add_argument("--interval", type=float, default=7.0)
    p.add_argument("--key-env", default="API_FOOTBALL_KEY", help="env var holding the API-Football key")
    a = p.parse_args()
    assert a.season in (2022, 2023, 2024), "free tier seasons 2022-2024 only"
    H = {"x-apisports-key": os.getenv(a.key_env) or ""}
    assert H["x-apisports-key"], f"{a.key_env} not set"
    cache = ROOT / f"data/raw/api_football_{a.competition_id.lower()}"; cache.mkdir(parents=True, exist_ok=True)

    fxp = cache / "fixtures.json"
    if not fxp.exists():
        r = requests.get(BASE + "/fixtures", headers=H, params={"league": a.league, "season": a.season}, timeout=25)
        fxp.write_text(json.dumps(r.json()), encoding="utf-8"); time.sleep(a.interval)
    fixtures = json.loads(fxp.read_text(encoding="utf-8"))["response"]
    grp = [f for f in fixtures if "group" in str(f.get("league", {}).get("round", "")).lower()]
    print(f"{a.competition_id}: {len(fixtures)} fixtures, {len(grp)} group-stage")

    fetched = 0
    for f in grp:
        fid = f["fixture"]["id"]; ep = cache / f"events_{fid}.json"
        if ep.exists() and json.loads(ep.read_text(encoding="utf-8")).get("response"):
            continue
        if fetched >= a.max_events:
            print(f"  hit max-events cap ({a.max_events}); stopping fetch (resume later)"); break
        r = requests.get(BASE + "/fixtures/events", headers=H, params={"fixture": fid}, timeout=25)
        fetched += 1; time.sleep(a.interval)
        j = r.json()
        if j.get("response"):
            ep.write_text(json.dumps(j), encoding="utf-8")
    print(f"  fetched {fetched} new event files (cached total: {len(list(cache.glob('events_*.json')))})")

    elo = pd.read_csv(ROOT / "data/processed/elo_history.csv")
    mkt_path = ROOT / "data/processed/intl_market_sharp.csv"
    market = pd.read_csv(mkt_path) if mkt_path.exists() else None
    df = build_state_for_competition(cache, a.competition_id, elo, market_df=market)
    if df.empty:
        print(f"  no state rows built for {a.competition_id} (no events/fixtures returned — likely rate-limited or uncovered); skipping write")
        return
    outp = ROOT / f"data/processed/inplay_state_{a.competition_id.lower()}.parquet"
    df.to_parquet(outp, index=False)
    cov = df.groupby("match_id").p_home_market.first().notna().mean()
    print(f"  built {len(df)} state rows, {df.match_id.nunique()} matches, market coverage {cov:.0%} -> {outp.name}")


if __name__ == "__main__":
    main()
