"""Phase 3: enumerate the FULL StatsBomb Open Data competition catalogue with availability + suitability
+ domain-shift labels. Read-only download of the approved StatsBomb repo; matches-lists cached for
resume. Data provided by StatsBomb (non-commercial research).
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
CACHE = ROOT / "data/raw/statsbomb/matches"; CACHE.mkdir(parents=True, exist_ok=True)


def confederation(name, country, intl):
    n = name.lower()
    if not intl:
        return {"Spain": "UEFA", "England": "UEFA", "Germany": "UEFA", "France": "UEFA",
                "Italy": "UEFA", "Europe": "UEFA"}.get(country, "CLUB/" + str(country))
    if "world cup" in n:
        return "FIFA"
    if "european" in n or "euro" in n:
        return "UEFA"
    if "copa america" in n or "libertadores" in n:
        return "CONMEBOL"
    if "africa" in n:
        return "CAF"
    if "asian" in n:
        return "AFC"
    return "INTL/other"


def matches_count(cid, sid):
    fp = CACHE / f"{cid}_{sid}.json"
    if not fp.exists():
        try:
            r = requests.get(f"{BASE}/matches/{cid}/{sid}.json", timeout=40)
            fp.write_text(r.text, encoding="utf-8"); time.sleep(0.15)
        except Exception:
            return 0
    try:
        return len(json.loads(fp.read_text(encoding="utf-8")))
    except Exception:
        return 0


def main():
    comps = requests.get(f"{BASE}/competitions.json", timeout=40).json()
    rows = []
    for c in comps:
        cid, sid = c["competition_id"], c["season_id"]
        intl = c.get("competition_international", False)
        male = c.get("competition_gender") == "male"
        youth = c.get("competition_youth", False)
        events = bool(c.get("match_available"))
        d360 = bool(c.get("match_available_360"))
        name = c["competition_name"]; season = c["season_name"]
        try:
            yr = int("".join(ch for ch in season[:4] if ch.isdigit()) or 0)
        except Exception:
            yr = 0
        senior_intl_men = intl and male and not youth
        # domain shift vs the 2026 men's-senior-international target
        if senior_intl_men:
            shift = "low" if yr >= 2014 else ("med" if yr >= 2000 else "high")
        elif intl:
            shift = "high"   # women's / youth international
        else:
            shift = "high"   # club
        rows.append({
            "competition_id": cid, "season_id": sid, "competition_name": name, "season_name": season,
            "country": c.get("country_name"), "gender": c.get("competition_gender"),
            "youth": youth, "international": intl,
            "type": "international" if intl else "club",
            "format": "tournament" if intl else "league",
            "confederation": confederation(name, c.get("country_name"), intl),
            "n_matches": matches_count(cid, sid),
            "events": events, "lineups": events, "shots_xg": events,
            "cards": events, "subs": events, "player_ids": events, "data_360": d360,
            "suit_intl_inplay_transfer": "high" if senior_intl_men else "low",
            "suit_player_state": "high" if events else "none",
            "domain_shift_risk": shift,
        })
        print(f"  {name} {season}: {rows[-1]['n_matches']} matches | intl_men={senior_intl_men} 360={d360} shift={shift}")
    df = pd.DataFrame(rows).sort_values(["type", "confederation", "season_name"]).reset_index(drop=True)
    outp = ROOT / "data/reference/statsbomb_competition_catalog.csv"
    outp.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(outp, index=False)
    print(f"\nwrote {len(df)} competition-seasons -> {outp}")
    print(f"men's senior international: {(df.suit_intl_inplay_transfer=='high').sum()} "
          f"({int(df[df.suit_intl_inplay_transfer=='high'].n_matches.sum())} matches)")
    print(f"club: {(df.type=='club').sum()} | women/youth intl: {((df.type=='international') & (df.suit_intl_inplay_transfer=='low')).sum()}")


if __name__ == "__main__":
    main()
