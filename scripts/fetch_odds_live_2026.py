"""Budget-guarded Odds API snapshot fetcher for the 2026 WC group-stage shadow study.
h2h only, US region only, all books in ONE batched request. Hard 500-credit ceiling + >=10-min spacing
(persistent, fail-closed via OddsBudget). Immutable raw snapshots + normalized no-vig. Safe by default:
--dry-run plans without calling the provider or spending credits.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from wcdrawlab.operations.odds_budget import OddsBudget  # noqa: E402

RAW = ROOT / "data/raw/odds/live_2026"; NORM = ROOT / "data/processed/odds_live_2026"
BUDGET_STATE = ROOT / "outputs/live_shadow/odds_budget.json"
SPORT = "soccer_fifa_world_cup"


def _novig(event):
    rows = []
    h, a = event.get("home_team"), event.get("away_team")
    for bk in event.get("bookmakers", []):
        for mk in bk.get("markets", []):
            if mk.get("key") != "h2h":
                continue
            out = {o["name"]: o["price"] for o in mk.get("outcomes", []) if o.get("price")}
            if h in out and a in out and "Draw" in out:
                imp = np.array([1/out[h], 1/out["Draw"], 1/out[a]])
                rows.append((imp, float(imp.sum())))
    if not rows:
        return None
    p = np.mean([r[0]/r[0].sum() for r in rows], axis=0)
    return {"p_home": float(p[0]), "p_draw": float(p[1]), "p_away": float(p[2]),
            "n_books": len(rows), "raw_overround": float(np.mean([r[1] for r in rows]))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot-type", default="baseline", choices=["baseline", "T-90", "T-15", "final"])
    ap.add_argument("--max-credits", type=int, default=500)
    ap.add_argument("--min-interval-s", type=float, default=600.0)
    ap.add_argument("--execute", action="store_true", help="actually call the provider + spend credits")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True); NORM.mkdir(parents=True, exist_ok=True)
    budget = OddsBudget(BUDGET_STATE, max_credits=a.max_credits, min_interval_s=a.min_interval_s)
    ok, reason = budget.can_request(projected_credits=1)
    now = datetime.now(timezone.utc).isoformat()
    if not a.execute:
        print(f"DRY-RUN: snapshot={a.snapshot_type} | budget {budget.summary()} | would_request={ok} ({reason})")
        return
    if not ok:
        print(f"HALT (budget/rate): {reason} | {budget.summary()}"); return

    from _live_env import load_keys; load_keys()
    from wcdrawlab.providers.odds_api import OddsAPIClient
    client = OddsAPIClient()
    rec = client.odds(SPORT, regions="us", markets="h2h")
    events = rec.payload["data"]; headers = rec.payload.get("headers", {})
    used = headers.get("x-requests-used"); remaining = headers.get("x-requests-remaining")
    budget.record_request(credits=1)  # h2h x us = 1 credit/request

    raw_blob = json.dumps({"snapshot_type": a.snapshot_type, "snapshot_utc": now,
                           "provider_used": used, "provider_remaining": remaining,
                           "events": events}, sort_keys=True)
    h = hashlib.sha256(raw_blob.encode()).hexdigest()[:16]
    raw_path = RAW / f"odds_{a.snapshot_type}_{now.replace(':','').replace('-','')[:15]}_{h}.json"
    if not raw_path.exists():           # immutable first-write-wins
        raw_path.write_text(raw_blob, encoding="utf-8")
    norm = []
    for e in events:
        nv = _novig(e)
        if not nv:
            continue
        norm.append({"snapshot_type": a.snapshot_type, "snapshot_utc": now,
                     "provider_commence": e.get("commence_time"), "home_team": e.get("home_team"),
                     "away_team": e.get("away_team"), **nv,
                     "market_completeness": round(min(1.0, nv["n_books"]/8.0), 3)})
    import pandas as pd
    if norm:
        npath = NORM / f"novig_{a.snapshot_type}_{now.replace(':','').replace('-','')[:15]}.csv"
        pd.DataFrame(norm).to_csv(npath, index=False)
    print(f"captured {len(events)} events ({len(norm)} with h2h no-vig) | credits_used={budget.credits_used}/{a.max_credits} "
          f"| provider used={used} remaining={remaining}")
    print(f"raw: {raw_path.name}")


if __name__ == "__main__":
    main()
