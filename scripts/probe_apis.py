"""Cheap connectivity probe for the sanctioned APIs. Never prints secret values."""
from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from _live_env import load_keys  # noqa: E402

load_keys()
import os  # noqa: E402

ODDS = os.environ.get("ODDS_API_KEY")
AF = os.environ.get("API_FOOTBALL_KEY")


def probe_odds():
    print("\n=== The Odds API ===")
    if not ODDS:
        print("ODDS_API_KEY missing"); return
    try:
        r = requests.get("https://api.the-odds-api.com/v4/sports",
                         params={"apiKey": ODDS, "all": "true"}, timeout=20)
        print("status:", r.status_code,
              "| quota remaining:", r.headers.get("x-requests-remaining"),
              "used:", r.headers.get("x-requests-used"))
        if r.status_code < 400:
            sports = r.json()
            soc = [s for s in sports if "soccer" in s.get("key", "")]
            wc = [s for s in soc if "world" in s.get("key", "").lower()
                  or "fifa" in s.get("title", "").lower() or "world cup" in s.get("title", "").lower()]
            print(f"soccer sports: {len(soc)} ; world-cup-like:")
            for s in wc:
                print(f"   key={s['key']!r} title={s['title']!r} active={s.get('active')}")
            if not wc:
                print("   (no WC key; sample soccer keys:)",
                      [s["key"] for s in soc[:12]])
        else:
            print("body:", r.text[:300])
    except Exception as e:  # noqa: BLE001
        print("odds probe failed:", repr(e))


def probe_af():
    print("\n=== API-Football ===")
    if not AF:
        print("API_FOOTBALL_KEY missing"); return
    h = {"x-apisports-key": AF}
    try:
        r = requests.get("https://v3.football.api-sports.io/status", headers=h, timeout=20)
        print("status:", r.status_code)
        if r.status_code < 400:
            resp = r.json().get("response", {})
            sub = resp.get("subscription", {}); req = resp.get("requests", {})
            print("plan:", sub.get("plan"), "active:", sub.get("active"),
                  "| requests today:", req.get("current"), "/", req.get("limit_day"))
        else:
            print("body:", r.text[:300]); return
        # WC league 1, season 2026 fixtures count (costs 1 request)
        r2 = requests.get("https://v3.football.api-sports.io/fixtures",
                          headers=h, params={"league": 1, "season": 2026}, timeout=20)
        if r2.status_code < 400:
            data = r2.json()
            res = data.get("response", [])
            print(f"WC league=1 season=2026 fixtures returned: {len(res)} (errors={data.get('errors')})")
            for fx in res[:3]:
                t = fx.get("teams", {}); g = fx.get("goals", {}); fxd = fx.get("fixture", {})
                print(f"   {fxd.get('date')} {t.get('home',{}).get('name')} {g.get('home')}-{g.get('away')} "
                      f"{t.get('away',{}).get('name')} [{fxd.get('status',{}).get('short')}]")
        else:
            print("fixtures body:", r2.text[:200])
    except Exception as e:  # noqa: BLE001
        print("af probe failed:", repr(e))


if __name__ == "__main__":
    probe_odds()
    probe_af()
