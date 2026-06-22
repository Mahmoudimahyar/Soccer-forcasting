"""Fetch the PLAYER PLANE (lineups + per-player stats + team statistics incl. xG) for a competition's
finished matches from API-Football (Pro plan), into an append-only, idempotent, throttled cache.

Leakage discipline (enforced downstream in player_plane_dataset.py, not here):
  - lineups (startXI/formation) are known ~1h BEFORE kickoff  -> legal pre-match feature
  - per-player ratings/minutes are FINAL (post-match)         -> only usable as PRIOR-match form
  - team expected_goals is a FINAL total                      -> match-level signal/target, not in-play

This script only RETRIEVES + caches raw provider JSON. It never trades, never touches protected code.
Usage: python scripts/fetch_player_plane.py --competition-id euro2024 --key-env API_FOOTBALL_KEY
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except Exception:
    pass
import os
import requests

BASE = "https://v3.football.api-sports.io"
ENDPOINTS = {"lineups": "/fixtures/lineups", "players": "/fixtures/players",
             "statistics": "/fixtures/statistics"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--competition-id", required=True, help="matches data/raw/api_football_<id>/fixtures.json")
    p.add_argument("--key-env", default="API_FOOTBALL_KEY")
    p.add_argument("--interval", type=float, default=0.4, help="seconds between calls (Pro=5/sec)")
    p.add_argument("--max-calls", type=int, default=2000, help="hard budget cap for this run")
    p.add_argument("--rounds", default="all", choices=["all", "group"], help="which finished matches")
    a = p.parse_args()
    H = {"x-apisports-key": os.getenv(a.key_env) or ""}
    assert H["x-apisports-key"], f"{a.key_env} not set"

    cache = ROOT / f"data/raw/api_football_{a.competition_id.lower()}"
    fxp = cache / "fixtures.json"
    assert fxp.exists(), f"no cached fixtures: {fxp}"
    fixtures = json.loads(fxp.read_text(encoding="utf-8"))["response"]
    fin = [f for f in fixtures if f.get("fixture", {}).get("status", {}).get("short") == "FT"]
    if a.rounds == "group":
        fin = [f for f in fin if "group" in str(f.get("league", {}).get("round", "")).lower()]
    print(f"{a.competition_id}: {len(fin)} finished matches ({a.rounds})")

    pdir = cache / "player_plane"; pdir.mkdir(parents=True, exist_ok=True)
    calls = 0
    for f in fin:
        fid = f["fixture"]["id"]
        for tag, ep in ENDPOINTS.items():
            outp = pdir / f"{tag}_{fid}.json"
            if outp.exists() and json.loads(outp.read_text(encoding="utf-8")).get("response"):
                continue
            if calls >= a.max_calls:
                print(f"  hit max-calls cap ({a.max_calls}); stopping (resume later)")
                _summary(pdir); return
            r = requests.get(BASE + ep, headers=H, params={"fixture": fid}, timeout=30)
            calls += 1; time.sleep(a.interval)
            j = r.json()
            if j.get("response"):
                outp.write_text(json.dumps(j), encoding="utf-8")
            elif j.get("errors"):
                print(f"  WARN fid={fid} {tag}: {j.get('errors')}")
    print(f"  made {calls} calls")
    _summary(pdir)


def _summary(pdir: Path):
    for tag in ENDPOINTS:
        n = len(list(pdir.glob(f"{tag}_*.json")))
        print(f"  cached {tag}: {n}")


if __name__ == "__main__":
    main()
