"""Fetch per-shot xG timelines from StatsBomb Open Data (free, NON-COMMERCIAL research use; attribution:
"Data provided by StatsBomb"). Extracts ONLY shot events (minute/second/period/team/xg/outcome) into a
compact parquet — does not retain the full event files. Read-only download of an official open dataset
(raw.githubusercontent.com); no auth, no scraping, no protected code touched.

Usage: python scripts/fetch_statsbomb_xg.py --competition-id 43 --season-id 106 --tag WC2022
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--competition-id", type=int, required=True)
    p.add_argument("--season-id", type=int, required=True)
    p.add_argument("--tag", required=True, help="our competition tag, e.g. WC2022")
    p.add_argument("--interval", type=float, default=0.2)
    a = p.parse_args()

    matches = requests.get(f"{BASE}/matches/{a.competition_id}/{a.season_id}.json", timeout=40).json()
    print(f"{a.tag}: {len(matches)} StatsBomb matches")
    rows = []
    for i, m in enumerate(matches):
        mid = m["match_id"]
        home = m["home_team"]["home_team_name"]; away = m["away_team"]["away_team_name"]
        try:
            ev = requests.get(f"{BASE}/events/{mid}.json", timeout=60).json()
        except Exception as e:
            print(f"  WARN match {mid}: {e}"); continue
        time.sleep(a.interval)
        for e in ev:
            if e.get("type", {}).get("name") != "Shot":
                continue
            sh = e.get("shot", {})
            rows.append({
                "sb_match_id": mid, "match_date": m["match_date"],
                "home_team": home, "away_team": away,
                "stage": m.get("competition_stage", {}).get("name"),
                "period": e.get("period"), "minute": e.get("minute"), "second": e.get("second"),
                "team": e.get("team", {}).get("name"),
                "xg": sh.get("statsbomb_xg"),
                "is_goal": int(sh.get("outcome", {}).get("name") == "Goal"),
            })
        if (i + 1) % 16 == 0:
            print(f"  ...{i+1}/{len(matches)} matches, {len(rows)} shots so far")
    df = pd.DataFrame(rows)
    outp = ROOT / f"data/processed/statsbomb_shots_{a.tag.lower()}.parquet"
    df.to_parquet(outp, index=False)
    print(f"  wrote {len(df)} shots ({df.sb_match_id.nunique()} matches, {int(df.is_goal.sum())} goals) -> {outp.name}")


if __name__ == "__main__":
    main()
