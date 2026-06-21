"""Normalize the raw Odds API snapshot into leakage-safe market features (baseline B6).

For each event: convert every book's h2h to a no-vig 3-way probability, take the consensus
(median across books, renormalized), and the median totals line. Map to the 2026 fixtures
by (commence date, canonical team pair) and align orientation to our team_a/team_b.

Output: data/processed/market_features_2026.csv
  match_id, p_a_market, p_draw_market, p_b_market, market_total_goals, n_books,
  market_is_missing, market_snapshot
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from wcdrawlab.market import no_vig_from_decimal_odds  # noqa: E402

RAW = ROOT / "data" / "raw" / "odds" / "odds_fifa_world_cup_2026-06-20.json"
PROC = ROOT / "data" / "processed"
SNAP = "2026-06-20"

EXTRA = {
    "Bosnia & Herzegovina": "Bosnia",
    "USA": "United States",
    "Czech Republic": "Czechia",
    "DR Congo": "Congo DR",
    "South Korea": "Korea Republic",
    "Curaçao": "Curacao",
}


def canon(n: str) -> str:
    return EXTRA.get(str(n).strip(), canonical_team_name(n))


def consensus_event(event) -> dict | None:
    home, away = canon(event["home_team"]), canon(event["away_team"])
    p_vectors = []  # each [p_home, p_draw, p_away]
    totals = []
    for bk in event.get("bookmakers", []):
        h = d = a = None
        for mk in bk.get("markets", []):
            if mk.get("key") == "h2h":
                for o in mk.get("outcomes", []):
                    nm = o.get("name")
                    if nm == event["home_team"]:
                        h = o["price"]
                    elif nm == event["away_team"]:
                        a = o["price"]
                    elif nm == "Draw":
                        d = o["price"]
            elif mk.get("key") == "totals":
                pts = [o.get("point") for o in mk.get("outcomes", []) if o.get("point") is not None]
                if pts:
                    totals.append(float(np.median(pts)))
        if h and d and a and h > 1 and d > 1 and a > 1:
            pv = no_vig_from_decimal_odds(np.array([h]), np.array([d]), np.array([a]))[0]
            p_vectors.append(pv)
    if not p_vectors:
        return None
    cons = np.median(np.vstack(p_vectors), axis=0)
    cons = cons / cons.sum()
    return {
        "home": home, "away": away,
        "commence_date": event["commence_time"][:10],
        "p_home": cons[0], "p_draw": cons[1], "p_away": cons[2],
        "market_total_goals": float(np.median(totals)) if totals else np.nan,
        "n_books": len(p_vectors),
    }


def main():
    data = json.loads(RAW.read_text())
    events = data["events"]
    cons = [c for c in (consensus_event(e) for e in events) if c]
    market = pd.DataFrame(cons)
    market["pair"] = market.apply(lambda r: frozenset((r["home"], r["away"])), axis=1)

    targets = pd.read_csv(PROC / "forecast_targets_2026.csv", parse_dates=["kickoff_utc"])
    targets["date"] = targets["kickoff_utc"].dt.strftime("%Y-%m-%d")
    targets["pair"] = targets.apply(lambda r: frozenset((r["team_a"], r["team_b"])), axis=1)

    rows = []
    unmatched_targets, unmatched_mkt = [], set(range(len(market)))
    for _, t in targets.iterrows():
        # match on team pair; prefer same/adjacent date
        cand = market[market["pair"] == t["pair"]]
        if cand.empty:
            unmatched_targets.append((t["match_id"], t["team_a"], t["team_b"], t["date"]))
            continue
        # nearest by date
        cand = cand.assign(ddiff=(pd.to_datetime(cand["commence_date"]) - pd.to_datetime(t["date"])).abs())
        m = cand.sort_values("ddiff").iloc[0]
        unmatched_mkt.discard(m.name)
        # align orientation to team_a/team_b
        if m["home"] == t["team_a"]:
            p_a, p_b = m["p_home"], m["p_away"]
        else:
            p_a, p_b = m["p_away"], m["p_home"]
        rows.append({
            "match_id": t["match_id"], "matchday": t["matchday"], "group": t["group"],
            "team_a": t["team_a"], "team_b": t["team_b"],
            "p_a_market": p_a, "p_draw_market": m["p_draw"], "p_b_market": p_b,
            "market_total_goals": m["market_total_goals"], "n_books": int(m["n_books"]),
            "market_is_missing": 0, "market_snapshot": SNAP,
        })
    out = pd.DataFrame(rows)
    out.to_csv(PROC / "market_features_2026.csv", index=False)

    print(f"odds events: {len(events)} | consensus events: {len(market)} | "
          f"matched to targets: {len(out)}/{len(targets)}")
    if unmatched_targets:
        print("targets WITHOUT market (likely already kicked off or thin market):")
        for mid, a, b, d in unmatched_targets:
            print(f"   {d} {a} vs {b} ({mid})")
    leftover = market.iloc[sorted(unmatched_mkt)] if unmatched_mkt else None
    if leftover is not None and len(leftover):
        print("odds events not matched to a target:")
        for _, r in leftover.iterrows():
            print(f"   {r['commence_date']} {r['home']} vs {r['away']}")
    print("\nMD2 market consensus (no-vig %):")
    md2 = out[out.matchday == 2][["group", "team_a", "team_b", "p_a_market", "p_draw_market", "p_b_market", "n_books"]].copy()
    for c in ("p_a_market", "p_draw_market", "p_b_market"):
        md2[c] = (md2[c] * 100).round().astype(int)
    print(md2.to_string(index=False))
    print("\nwrote:", PROC / "market_features_2026.csv")


if __name__ == "__main__":
    main()
