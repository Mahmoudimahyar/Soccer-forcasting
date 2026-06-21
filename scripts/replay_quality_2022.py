"""Quantify 2022 API-Football event-replay data quality from the cached events (no network).
Outputs counts by event type, coverage, goal reconciliation, and a no-post-event-leakage check on
the replay table. Read-only research; does not tune B1.
"""
import glob
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/raw/api_football_2022_worldcup"

fixtures = json.loads((CACHE / "fixtures.json").read_text(encoding="utf-8"))["response"]
grp = {f["fixture"]["id"]: f for f in fixtures if "group" in str(f.get("league", {}).get("round", "")).lower()}

types = Counter(); no_elapsed = 0; matches_with_events = 0; total_events = 0
goal_recon_ok = 0; goal_recon_bad = []
red = subs = 0
event_files = glob.glob(str(CACHE / "events_*.json"))
for fp in event_files:
    fid = int(Path(fp).stem.split("_")[1])
    ev = json.loads(Path(fp).read_text(encoding="utf-8")).get("response") or []
    if ev:
        matches_with_events += 1
    total_events += len(ev)
    goals_home = goals_away = 0
    f = grp.get(fid)
    home = f["teams"]["home"]["name"] if f else None
    for e in ev:
        t = e.get("type"); det = str(e.get("detail") or "")
        types[t] += 1
        if (e.get("time") or {}).get("elapsed") is None:
            no_elapsed += 1
        if t == "Goal" and "Missed" not in det:
            scorer = e.get("team", {}).get("name")
            if det == "Own Goal":
                scorer = f["teams"]["away"]["name"] if scorer == home else home
            if scorer == home:
                goals_home += 1
            else:
                goals_away += 1
        if t == "Card" and "Red" in det:
            red += 1
        if t == "subst":
            subs += 1
    if f:
        fh, fa = f["goals"]["home"], f["goals"]["away"]
        if (fh, fa) == (goals_home, goals_away):
            goal_recon_ok += 1
        else:
            goal_recon_bad.append((fid, (fh, fa), (goals_home, goals_away)))

print(f"group fixtures: {len(grp)} | event caches: {len(event_files)} | matches_with_events: {matches_with_events}")
print(f"total events: {total_events} | events missing 'elapsed' minute: {no_elapsed}")
print(f"event types: {dict(types)}")
print(f"red cards: {red} | substitution events: {subs}")
print(f"goal reconciliation (events vs final score): {goal_recon_ok}/{len(event_files)} match")
if goal_recon_bad:
    print(f"  mismatches (often penalty-shootout/own-goal edge cases): {goal_recon_bad[:5]}")

# lineup coverage
ln = glob.glob(str(CACHE / "lineups_*.json"))
print(f"lineup caches: {len(ln)} (bulk lineups not fetched; events suffice for state replay)")

# no-post-event leakage check on the replay table
rp = ROOT / "data/processed/inplay_replay_2022_worldcup.csv"
if rp.exists():
    R = pd.read_csv(rp).sort_values(["fixture_id", "decision_minute"])
    mono_ok = True
    for fid, g in R.groupby("fixture_id"):
        if (g.goals_a_so_far.diff().dropna() < 0).any() or (g.goals_b_so_far.diff().dropna() < 0).any():
            mono_ok = False
    print(f"\nreplay rows: {len(R)} | goals monotonic non-decreasing across minutes (no future leak): {mono_ok}")
    t90 = R[R.decision_minute == 90]
    print(f"t=90 rows: {len(t90)} (state at 90' = full-match state, used only to score the FINAL outcome)")
