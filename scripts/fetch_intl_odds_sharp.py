"""Capture a SHARPER market input for the same intl matches: the CLOSING line (snapshot ~5 min
before kickoff) and PINNACLE specifically (the sharpest book). Reuses the kickoff slots already
in intl_odds_raw.csv (no re-discovery). This lets us test whether the Elo blend's edge is real
alpha or just denoising of a softer T-90min consensus.

Output: data/processed/intl_odds_sharp.csv
  sport, commence_time, snapshot_time, home, away, n_books, has_pinnacle,
  cons_a/cons_d/cons_b (median no-vig at close), pin_a/pin_d/pin_b (Pinnacle no-vig at close)
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
RAW = ROOT / "data" / "processed" / "intl_odds_raw.csv"
OUT = ROOT / "data" / "processed" / "intl_odds_sharp.csv"
CREDIT_FLOOR = 4000


def canon(n):
    return canonical_team_name(n)


def novig(h, d, a):
    if h and d and a and h > 1 and d > 1 and a > 1:
        return no_vig_from_decimal_odds(np.array([h]), np.array([d]), np.array([a]))[0]
    return None


def book_probs(event, book_key=None):
    """no-vig probs from a specific book (book_key) or median across all books."""
    vecs = []
    for bk in event.get("bookmakers", []):
        if book_key is not None and bk.get("key") != book_key:
            continue
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
        v = novig(h, d, a)
        if v is not None:
            vecs.append(v)
    if not vecs:
        return None, 0
    arr = np.vstack(vecs)
    c = np.median(arr, axis=0); c = c / c.sum()
    return c, len(vecs)


def get(date_iso, sport):
    r = requests.get(f"https://api.the-odds-api.com/v4/historical/sports/{sport}/odds",
                     params={"apiKey": KEY, "regions": "eu", "markets": "h2h",
                             "oddsFormat": "decimal", "date": date_iso}, timeout=45)
    if r.status_code >= 400:
        return None, r.headers.get("x-requests-remaining")
    return r.json(), r.headers.get("x-requests-remaining")


def main():
    raw = pd.read_csv(RAW)
    slots = raw.groupby(["sport", "commence_time"]).size().reset_index()[["sport", "commence_time"]]
    done = set()
    rows = []
    if OUT.exists():
        prev = pd.read_csv(OUT)
        rows = prev.to_dict("records")
        done = set(zip(prev["sport"], prev["commence_time"], prev["home"], prev["away"]))
    rem = None
    for _, s in slots.iterrows():
        if rem is not None and int(rem) < CREDIT_FLOOR:
            print(f"[stop] credit floor ({rem})"); break
        ct = s["commence_time"]
        ct_dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        snap_at = (ct_dt - timedelta(minutes=5)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        j, rem = get(snap_at, s["sport"])
        if not j:
            continue
        for e in j.get("data", []):
            if e["commence_time"] != ct:
                continue
            key = (s["sport"], ct, canon(e["home_team"]), canon(e["away_team"]))
            if key in done:
                continue
            cons, nb = book_probs(e, None)
            pin, npin = book_probs(e, "pinnacle")
            if cons is None:
                continue
            rows.append({
                "sport": s["sport"], "commence_time": ct, "snapshot_time": j.get("timestamp"),
                "home": canon(e["home_team"]), "away": canon(e["away_team"]), "n_books": nb,
                "has_pinnacle": int(pin is not None),
                "cons_a": cons[0], "cons_d": cons[1], "cons_b": cons[2],
                "pin_a": pin[0] if pin is not None else np.nan,
                "pin_d": pin[1] if pin is not None else np.nan,
                "pin_b": pin[2] if pin is not None else np.nan,
            })
            done.add(key)
        pd.DataFrame(rows).to_csv(OUT, index=False)
    df = pd.DataFrame(rows)
    print(f"[done] slots={len(slots)} matches={len(df)} with_pinnacle={int(df['has_pinnacle'].sum())} "
          f"| credits remaining {rem}")
    print("median n_books at close:", int(df["n_books"].median()))


if __name__ == "__main__":
    main()
