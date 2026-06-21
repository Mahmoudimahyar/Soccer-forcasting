"""Build a leakage-safe in-play REPLAY table for the 2022 WC group stage from API-Football events.

Quota-aware + idempotent: events are cached under data/raw/api_football_2022_worldcup/ and never
re-fetched if present. Pre-match goal intensities come from a scoreline mapping fit on PRE-2022 goals
only. For each decision minute, the state uses ONLY events with elapsed <= minute (no later events,
no post-match summary). The in-play engine scores each frozen state against the final outcome.

Use: validate the in-play engine + identify missing data. NOT used to tune B1.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except Exception:
    pass
import requests  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from wcdrawlab.research.scoreline import ScorelineModel  # noqa: E402
from wcdrawlab.research.inplay_replay import replay_prediction  # noqa: E402
from wcdrawlab.inplay.engine import InPlayState  # noqa: E402
from wcdrawlab.evaluation import metric_report  # noqa: E402

import os
H = {"x-apisports-key": os.getenv("API_FOOTBALL_KEY") or ""}
BASE = "https://v3.football.api-sports.io"
CACHE = ROOT / "data/raw/api_football_2022_worldcup"
CACHE.mkdir(parents=True, exist_ok=True)
DAILY_CAP = 90       # stay under the 100/day free limit
MIN_INTERVAL = 7.0   # free plan = 10 requests/MINUTE -> ~8.5/min at 7s spacing
calls = 0


def get_cached(name, path, params):
    """Cache only VALID responses (with a non-empty 'response'); rate-limited/errored calls are not
    cached so they retry. Throttled to respect the per-minute limit."""
    global calls
    fp = CACHE / name
    if fp.exists():
        j = json.loads(fp.read_text(encoding="utf-8"))
        if j.get("response"):
            return j, False
    if calls >= DAILY_CAP:
        return None, False
    r = requests.get(BASE + path, headers=H, params=params, timeout=25)
    calls += 1
    time.sleep(MIN_INTERVAL)
    j = r.json()
    if j.get("response"):
        fp.write_text(json.dumps(j), encoding="utf-8")
        return j, True
    return j, True  # valid call made but empty (rate-limited/no data); not cached


fixtures = json.loads((CACHE / "fixtures.json").read_text(encoding="utf-8"))["response"]
grp = [f for f in fixtures if "group" in str(f.get("league", {}).get("round", "")).lower()]

# pre-2022 scoreline mapping (leakage-safe)
T = pd.read_csv(ROOT / "data/processed/research_modeling_table.csv", parse_dates=["kickoff_utc"])
T["yr"] = T.kickoff_utc.dt.year
g = T[(T.stage.astype(str).str.lower() == "group") & T.goals_a.notna()]
sm = ScorelineModel("poisson").fit(g[g.yr < 2022].elo_delta, g[g.yr < 2022].goals_a, g[g.yr < 2022].goals_b)
# 2022 elo_delta lookup by canonical unordered pair (sign oriented to research team_a)
elo22 = {}
for r in T[(T.yr == 2022) & (T.stage.astype(str).str.lower() == "group")].itertuples():
    elo22[frozenset((canonical_team_name(r.team_a), canonical_team_name(r.team_b)))] = \
        (canonical_team_name(r.team_a), float(r.elo_delta))

DEC_MIN = [15, 30, 45, 60, 75, 90]
rows = []
n_events_ok = 0
for f in grp:
    fid = f["fixture"]["id"]
    home = canonical_team_name(f["teams"]["home"]["name"]); away = canonical_team_name(f["teams"]["away"]["name"])
    gh, ga_ = f["goals"]["home"], f["goals"]["away"]
    if gh is None or ga_ is None:
        continue
    pair = frozenset((home, away))
    if pair not in elo22:
        continue
    ref_a, elo_delta = elo22[pair]  # ref_a is research team_a (canonical)
    a_is_home = (ref_a == home)
    je, _ = get_cached(f"events_{fid}.json", "/fixtures/events", {"fixture": fid})
    if not je or not je.get("response"):
        continue
    n_events_ok += 1
    events = je["response"]
    # orient lambdas to team_a
    la, lb = sm.lambdas([elo_delta]); la, lb = float(la[0]), float(lb[0])

    def state_at(minute):
        gA = gB = rA = rB = 0
        for e in events:
            el = (e.get("time") or {}).get("elapsed")
            if el is None or el > minute:
                continue
            etype = e.get("type"); det = str(e.get("detail") or "")
            eteam = canonical_team_name((e.get("team") or {}).get("name", ""))
            scoring_team = eteam
            if etype == "Goal":
                if det == "Own Goal":
                    scoring_team = home if eteam == away else away
                elif "Missed" in det or det == "Missed Penalty":
                    continue
                if scoring_team == ref_a:
                    gA += 1
                else:
                    gB += 1
            elif etype == "Card" and "Red" in det:
                if eteam == ref_a:
                    rA += 1
                else:
                    rB += 1
        return gA, gB, rA, rB

    final_a = gh if a_is_home else ga_
    final_b = ga_ if a_is_home else gh
    outcome = "A" if final_a > final_b else ("D" if final_a == final_b else "B")
    for minute in DEC_MIN:
        gA, gB, rA, rB = state_at(minute)
        pred = replay_prediction(la, lb, InPlayState(minute=minute, goals_a=gA, goals_b=gB,
                                                     red_cards_a=rA, red_cards_b=rB))
        rows.append({"fixture_id": fid, "team_a": ref_a, "team_b": (away if a_is_home else home),
                     "decision_minute": minute, "goals_a_so_far": gA, "goals_b_so_far": gB,
                     "red_a": rA, "red_b": rB, "p_a_win": pred.p_a_win, "p_draw": pred.p_draw,
                     "p_b_win": pred.p_b_win, "remaining_xg_total": pred.remaining_xg_total,
                     "risk_band": pred.risk_band, "final_outcome": outcome})

R = pd.DataFrame(rows)
R.to_csv(ROOT / "data/processed/inplay_replay_2022_worldcup.csv", index=False)
print(f"API calls this run: {calls} | matches with events: {n_events_ok} | replay rows: {len(R)}")

# in-play metric by minute bucket (validate engine sharpens with time)
print("\nin-play engine validation (by decision minute):")
for minute in DEC_MIN:
    sub = R[R.decision_minute == minute]
    if sub.empty:
        continue
    P = sub[["p_a_win", "p_draw", "p_b_win"]].to_numpy()
    rep = metric_report(sub.final_outcome.to_numpy(), P)
    print(f"  t={minute:>2}min  n={len(sub)}  RPS={rep['rps']:.4f}  logloss={rep['log_loss']:.4f}")
