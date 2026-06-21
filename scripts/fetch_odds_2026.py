"""Fetch real 2026 World Cup odds from The Odds API and save a raw, timestamped snapshot.
Inspect-only summary printed; no secrets logged."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from _live_env import load_keys  # noqa: E402
load_keys()

from wcdrawlab.providers.odds_api import OddsAPIClient  # noqa: E402
import requests  # noqa: E402
import os  # noqa: E402

RAWDIR = ROOT / "data" / "raw" / "odds"
SNAP = "2026-06-20"


def main():
    RAWDIR.mkdir(parents=True, exist_ok=True)
    client = OddsAPIClient()
    rec = client.odds("soccer_fifa_world_cup", regions="us,uk,eu", markets="h2h,totals")
    events = rec.payload["data"]
    headers = rec.payload["headers"]
    raw_path = RAWDIR / f"odds_fifa_world_cup_{SNAP}.json"
    raw_path.write_text(json.dumps({"retrieved_at": rec.retrieved_at_utc,
                                    "source_url_redacted": rec.endpoint,
                                    "events": events}, indent=2))
    print("quota remaining:", headers.get("x-requests-remaining"), "used:", headers.get("x-requests-used"))
    print("events:", len(events), "| saved:", raw_path.name)
    if events:
        dates = sorted(e.get("commence_time", "") for e in events)
        print("commence range:", dates[0], "->", dates[-1])
        for e in events[:6]:
            nbooks = len(e.get("bookmakers", []))
            print(f"   {e.get('commence_time')} {e.get('home_team')} vs {e.get('away_team')} [{nbooks} books]")
        # show one full h2h example
        for e in events:
            for bk in e.get("bookmakers", []):
                for mk in bk.get("markets", []):
                    if mk.get("key") == "h2h":
                        print("\nsample h2h:", e.get("home_team"), "vs", e.get("away_team"),
                              "book=", bk.get("title"),
                              [(o["name"], o["price"]) for o in mk.get("outcomes", [])])
                        break
                else:
                    continue
                break
            break
        # all distinct team names (for canonicalization mapping)
        teams = sorted(set([e.get("home_team") for e in events] + [e.get("away_team") for e in events]))
        print("\ndistinct teams in odds feed:", teams)


def probe_af_raw():
    print("\n=== API-Football /status raw ===")
    af = os.environ.get("API_FOOTBALL_KEY")
    try:
        r = requests.get("https://v3.football.api-sports.io/status",
                         headers={"x-apisports-key": af}, timeout=20)
        print("http", r.status_code, "| keys:", list(r.json().keys()))
        print("response field type:", type(r.json().get("response")).__name__,
              "| errors:", r.json().get("errors"))
        print("body head:", json.dumps(r.json())[:400])
    except Exception as e:  # noqa: BLE001
        print("af raw failed:", repr(e))


if __name__ == "__main__":
    main()
    # API-Football is intentionally disabled (no valid key); diagnostics live in
    # scripts/probe_apis.py if needed. The odds pipeline does not call it.
