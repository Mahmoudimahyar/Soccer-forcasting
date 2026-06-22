"""Canonical leakage-safe in-play STATE dataset builder from the validated 2022 WC event replay.

Each row = a decision point during a match. Features at decision minute t use ONLY events with
minute <= t (enforced via event_semantics). Targets may use future events (they are labels).
Research-only; no runtime use. Event data available: goals, cards (yellow/red/second-yellow), subs,
VAR. Shots/xG/corners/lineups are UNAVAILABLE (flagged, never imputed).
"""
from __future__ import annotations

import glob
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from wcdrawlab.evaluation import normalize_probs
from wcdrawlab.ratings import ternary_elo_probs
from wcdrawlab.research.event_semantics import interpret_event
from wcdrawlab.ingest import canonical_team_name

SCHEMA_VERSION = "inplay_state_v1"
FIXED_MINUTES = [0, 15, 30, 45, 60, 75, 85]
PROVIDER = "api_football"


def _cards_subs_state(events, home, away, t):
    """Counts of yellow/red/second-yellow cards and subs by team, for events with minute <= t."""
    s = {"yellow_home": 0, "yellow_away": 0, "red_home": 0, "red_away": 0,
         "secondyellow_home": 0, "secondyellow_away": 0, "subs_home": 0, "subs_away": 0}
    for e in events:
        m = (e.get("time") or {}).get("elapsed")
        if m is None or m > t:
            continue
        team = e.get("team", {}).get("name", "")
        side = "home" if team == home else ("away" if team == away else None)
        if side is None:
            continue
        etype, det = e.get("type"), str(e.get("detail") or "")
        if etype == "Card":
            if "Red" in det:
                s[f"red_{side}"] += 1
                if "Second" in det or "second" in det:
                    s[f"secondyellow_{side}"] += 1
            elif "Yellow" in det:
                s[f"yellow_{side}"] += 1
        elif etype == "subst":
            s[f"subs_{side}"] += 1
    return s


def _score_at(events, home, away, t):
    gh = ga = 0
    for e in events:
        if e.get("type") != "Goal":
            continue
        m = (e.get("time") or {}).get("elapsed")
        if m is None or m > t:
            continue
        c = interpret_event(e, home, away, PROVIDER)
        if not c["is_goal"]:
            continue
        if c["scoring_team_id"] == home:
            gh += 1
        elif c["scoring_team_id"] == away:
            ga += 1
    return gh, ga


def _goal_minutes(events, home, away):
    """List of (minute, scoring_side) for valid goals, sorted by minute."""
    out = []
    for e in events:
        if e.get("type") != "Goal":
            continue
        m = (e.get("time") or {}).get("elapsed")
        c = interpret_event(e, home, away, PROVIDER)
        if m is None or not c["is_goal"]:
            continue
        out.append((m, "home" if c["scoring_team_id"] == home else "away"))
    return sorted(out)


def _red_minutes(events, home, away):
    out = []
    for e in events:
        if e.get("type") == "Card" and "Red" in str(e.get("detail") or ""):
            m = (e.get("time") or {}).get("elapsed")
            if m is not None:
                out.append(m)
    return sorted(out)


def _elo_lookup_from_history(elo_history: pd.DataFrame) -> dict:
    """frozenset{canon teams} -> list of (pd.Timestamp date, listed_team_a, elo_a_pre, elo_b_pre).
    Date-tolerant matching (via _resolve_elo) handles timezone date-boundary differences."""
    e = elo_history.copy()
    e["ts"] = pd.to_datetime(e["date"], errors="coerce", utc=True)
    out: dict = {}
    for r in e.itertuples():
        key = frozenset((canonical_team_name(r.team_a), canonical_team_name(r.team_b)))
        out.setdefault(key, []).append((r.ts, canonical_team_name(r.team_a), float(r.elo_a_pre), float(r.elo_b_pre)))
    return out


def _resolve_elo(lookup: dict, date_str: str, pair: frozenset, tol_days: int = 2):
    """Nearest elo_history entry for the team pair within +/- tol_days of the fixture date."""
    entries = lookup.get(pair)
    if not entries:
        return None
    target = pd.to_datetime(date_str, errors="coerce", utc=True)
    if pd.isna(target):
        return entries[0][1:]
    best = min(entries, key=lambda x: abs((x[0] - target).days) if pd.notna(x[0]) else 10**6)
    if pd.notna(best[0]) and abs((best[0] - target).days) > tol_days:
        return None
    return best[1:]  # (listed_a, ea, eb)


def build_state_for_competition(cache_dir: str | Path, competition_id: str,
                                elo_history: pd.DataFrame) -> pd.DataFrame:
    """Generalized in-play state builder for ANY cached competition (API-Football fixtures+events) +
    pre-match Elo from elo_history. Same schema as build_state_table; group = competition_id (the
    leave-one-COMPETITION-out fold unit); market columns NaN (optional). Research-only."""
    cache = Path(cache_dir)
    fixtures = {f["fixture"]["id"]: f for f in json.loads((cache / "fixtures.json").read_text(encoding="utf-8"))["response"]}
    grp = {i: f for i, f in fixtures.items() if "group" in str(f.get("league", {}).get("round", "")).lower()}
    elo = _elo_lookup_from_history(elo_history)
    rows = []
    for fid, f in sorted(grp.items()):
        ev_path = cache / f"events_{fid}.json"
        if not ev_path.exists():
            continue
        raw = ev_path.read_bytes()
        events = json.loads(raw)["response"]
        if not events:
            continue
        snap_hash = hashlib.sha256(raw).hexdigest()[:16]
        home = canonical_team_name(f["teams"]["home"]["name"]); away = canonical_team_name(f["teams"]["away"]["name"])
        rnd = str(f["league"]["round"]); matchday = int(rnd.split("-")[-1].strip()) if "-" in rnd else None
        date = str(f["fixture"].get("date", ""))[:10]
        fh, fa = f["goals"]["home"], f["goals"]["away"]
        if fh is None or fa is None:
            continue
        final_out = "H" if fh > fa else ("D" if fh == fa else "A")
        rec = _resolve_elo(elo, date, frozenset((home, away)))
        if rec is None:
            continue  # no pre-match Elo within tolerance -> skip (fail closed, no imputation)
        listed_a, ea, eb = rec
        elo_delta_home = (ea - eb) if listed_a == home else (eb - ea)
        ep = normalize_probs(ternary_elo_probs(np.array([elo_delta_home])))[0]
        goals = _goal_minutes(events, home, away); reds = _red_minutes(events, home, away)
        points = sorted(set(FIXED_MINUTES) | {(e.get("time") or {}).get("elapsed") for e in events
                                              if (e.get("time") or {}).get("elapsed") is not None})
        dtypes = {}
        for e in events:
            m = (e.get("time") or {}).get("elapsed")
            if m is not None:
                dtypes.setdefault(m, e.get("type"))
        for seq, t in enumerate(points):
            gh, ga = _score_at(events, home, away, t); cs = _cards_subs_state(events, home, away, t)
            fut = [g for g in goals if g[0] > t]
            def gw(h): return int(any(t < gm <= t + h for gm, _ in goals))
            def rw(h): return int(any(t < rm <= t + h for rm in reds))
            rows.append({"match_id": fid, "tournament": competition_id, "group": competition_id,
                "matchday": matchday, "kickoff_utc": f["fixture"].get("date"), "decision_minute": t,
                "event_sequence_number": seq, "decision_type": dtypes.get(t, "fixed"),
                "source_snapshot_sha256": snap_hash, "replay_schema_version": SCHEMA_VERSION,
                "home_team": home, "away_team": away, "neutral": True,
                "score_home": gh, "score_away": ga, "score_diff": gh - ga, "remaining_minutes": max(0, 90 - t),
                "wld_state": "H" if gh > ga else ("D" if gh == ga else "A"),
                "yellow_home": cs["yellow_home"], "yellow_away": cs["yellow_away"],
                "red_home": cs["red_home"], "red_away": cs["red_away"],
                "secondyellow_home": cs["secondyellow_home"], "secondyellow_away": cs["secondyellow_away"],
                "red_diff": cs["red_home"] - cs["red_away"], "subs_home": cs["subs_home"], "subs_away": cs["subs_away"],
                "unknown_lineup_flag": 1, "unknown_substitution_detail_flag": 0,
                "shots_available": 0, "xg_available": 0, "corners_available": 0, "setpieces_available": 0,
                "elo_delta_home": elo_delta_home, "p_home_elo": ep[0], "p_draw_elo": ep[1], "p_away_elo": ep[2],
                "p_home_market": np.nan, "p_draw_market": np.nan, "p_away_market": np.nan, "pregame_completeness": 0.5,
                "final_wld": final_out, "final_score_home": fh, "final_score_away": fa, "final_gd": fh - fa,
                "next_goal_team": fut[0][1] if fut else "none",
                "goal_within_1": gw(1), "goal_within_3": gw(3), "goal_within_5": gw(5), "goal_within_10": gw(10),
                "red_within_5": rw(5), "red_within_10": rw(10),
                "remaining_goals_home": sum(1 for gm, sd in goals if gm > t and sd == "home"),
                "remaining_goals_away": sum(1 for gm, sd in goals if gm > t and sd == "away")})
    return pd.DataFrame(rows)


def build_state_table(cache_dir: str | Path, research_table: str | Path,
                      market_csv: str | Path | None = None) -> pd.DataFrame:
    cache = Path(cache_dir)
    fixtures = {f["fixture"]["id"]: f for f in json.loads((cache / "fixtures.json").read_text(encoding="utf-8"))["response"]}
    grp = {i: f for i, f in fixtures.items() if "group" in str(f.get("league", {}).get("round", "")).lower()}

    rt = pd.read_csv(research_table, parse_dates=["kickoff_utc"])
    rt = rt[(rt.kickoff_utc.dt.year == 2022) & (rt.stage.astype(str).str.lower() == "group")].copy()
    elo = {}
    group_of = {}
    for r in rt.itertuples():
        key = frozenset((canonical_team_name(r.team_a), canonical_team_name(r.team_b)))
        elo[key] = (canonical_team_name(r.team_a), float(r.elo_delta))
        if "group" in rt.columns and pd.notna(getattr(r, "group", None)):
            group_of[key] = str(r.group)
    mkt = {}
    if market_csv and Path(market_csv).exists():
        m = pd.read_csv(market_csv)
        for r in m.itertuples():
            mkt[frozenset((canonical_team_name(r.team_a), canonical_team_name(r.team_b)))] = \
                (canonical_team_name(r.team_a), r.p_a_market, r.p_draw_market, r.p_b_market)

    rows = []
    for fid, f in sorted(grp.items()):
        raw = (cache / f"events_{fid}.json").read_bytes()
        events = json.loads(raw)["response"]
        snap_hash = hashlib.sha256(raw).hexdigest()[:16]
        home = canonical_team_name(f["teams"]["home"]["name"]); away = canonical_team_name(f["teams"]["away"]["name"])
        rnd = str(f["league"]["round"]); matchday = int(rnd.split("-")[-1].strip()) if "-" in rnd else None
        ko = f["fixture"].get("date")
        fh, fa = f["goals"]["home"], f["goals"]["away"]
        final_out = "H" if fh > fa else ("D" if fh == fa else "A")

        pair = frozenset((home, away))
        group = group_of.get(pair, rnd)
        ref_a, elo_delta = elo.get(pair, (home, 0.0))
        elo_delta_home = elo_delta if ref_a == home else -elo_delta
        ep = normalize_probs(ternary_elo_probs(np.array([elo_delta_home])))[0]
        if pair in mkt:
            mref, pa, pdr, pb = mkt[pair]
            mp = (pa, pdr, pb) if mref == home else (pb, pdr, pa)
            mkt_complete = 1.0
        else:
            mp = (np.nan, np.nan, np.nan); mkt_complete = 0.0

        goals = _goal_minutes(events, home, away)
        reds = _red_minutes(events, home, away)

        # decision points: fixed minutes + event minutes
        event_minutes = sorted({(e.get("time") or {}).get("elapsed") for e in events
                                if (e.get("time") or {}).get("elapsed") is not None})
        dtypes = {}
        for e in events:
            m = (e.get("time") or {}).get("elapsed")
            if m is not None:
                dtypes.setdefault(m, e.get("type"))
        points = sorted(set(FIXED_MINUTES) | set(event_minutes))
        for seq, t in enumerate(points):
            gh, ga = _score_at(events, home, away, t)
            cs = _cards_subs_state(events, home, away, t)
            # targets
            future_goals = [g for g in goals if g[0] > t]
            next_goal_team = future_goals[0][1] if future_goals else "none"
            def goal_within(h): return int(any(t < gm <= t + h for gm, _ in goals))
            def red_within(h): return int(any(t < rm <= t + h for rm in reds))
            rem_home = sum(1 for gm, sd in goals if gm > t and sd == "home")
            rem_away = sum(1 for gm, sd in goals if gm > t and sd == "away")
            rows.append({
                # identity/timing
                "match_id": fid, "tournament": "WC2022", "group": group, "matchday": matchday,
                "kickoff_utc": ko, "decision_minute": t, "event_sequence_number": seq,
                "decision_type": dtypes.get(t, "fixed"), "source_snapshot_sha256": snap_hash,
                "replay_schema_version": SCHEMA_VERSION, "home_team": home, "away_team": away, "neutral": True,
                # match state
                "score_home": gh, "score_away": ga, "score_diff": gh - ga,
                "remaining_minutes": max(0, 90 - t),
                "wld_state": "H" if gh > ga else ("D" if gh == ga else "A"),
                # discipline
                "yellow_home": cs["yellow_home"], "yellow_away": cs["yellow_away"],
                "red_home": cs["red_home"], "red_away": cs["red_away"],
                "secondyellow_home": cs["secondyellow_home"], "secondyellow_away": cs["secondyellow_away"],
                "red_diff": cs["red_home"] - cs["red_away"],
                # subs
                "subs_home": cs["subs_home"], "subs_away": cs["subs_away"],
                "unknown_lineup_flag": 1, "unknown_substitution_detail_flag": 0,
                # event availability flags (unavailable on this provider plan)
                "shots_available": 0, "xg_available": 0, "corners_available": 0, "setpieces_available": 0,
                # pregame
                "elo_delta_home": elo_delta_home, "p_home_elo": ep[0], "p_draw_elo": ep[1], "p_away_elo": ep[2],
                "p_home_market": mp[0], "p_draw_market": mp[1], "p_away_market": mp[2],
                "pregame_completeness": round(0.5 + 0.5 * mkt_complete, 3),
                # targets
                "final_wld": final_out, "final_score_home": fh, "final_score_away": fa, "final_gd": fh - fa,
                "next_goal_team": next_goal_team,
                "goal_within_1": goal_within(1), "goal_within_3": goal_within(3),
                "goal_within_5": goal_within(5), "goal_within_10": goal_within(10),
                "red_within_5": red_within(5), "red_within_10": red_within(10),
                "remaining_goals_home": rem_home, "remaining_goals_away": rem_away,
            })
    return pd.DataFrame(rows)
