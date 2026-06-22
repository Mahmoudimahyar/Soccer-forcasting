"""Leakage-safe PLAYER-PLANE feature builder.

Turns cached API-Football player-plane JSON (lineups / players / statistics) into a per-match
pre-match feature table whose only player signal is computed from information knowable at kickoff:

  * starting XI + formation come from `/fixtures/lineups`, published ~1h BEFORE kickoff -> legal.
  * each starting player's strength is their PRIOR-FORM rating = mean match rating over matches that
    kicked off STRICTLY BEFORE this match. A player's rating in the current (or any later) match is
    never used -> no leakage. Players with no prior history contribute nothing (tracked as coverage).
  * team expected_goals (xG) is a FINAL total -> stored only as an outcome/diagnostic column, never as
    a feature.

Pure functions + a build entrypoint; no network here (fetching lives in scripts/fetch_player_plane.py).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def fixtures_index(fixtures_json_path: Path) -> dict:
    """fixture_id -> identity/result dict from a cached fixtures.json."""
    resp = json.loads(Path(fixtures_json_path).read_text(encoding="utf-8"))["response"]
    out = {}
    for f in resp:
        if f.get("fixture", {}).get("status", {}).get("short") != "FT":
            continue
        fid = f["fixture"]["id"]
        gh, ga = f["goals"]["home"], f["goals"]["away"]
        out[fid] = {
            "kickoff": _parse_dt(f["fixture"]["date"]),
            "home_id": f["teams"]["home"]["id"], "away_id": f["teams"]["away"]["id"],
            "home_name": f["teams"]["home"]["name"], "away_name": f["teams"]["away"]["name"],
            "goals_home": gh, "goals_away": ga,
            "final_wld": ("H" if gh > ga else "A" if ga > gh else "D"),
            "round": f.get("league", {}).get("round", ""),
        }
    return out


def player_match_records(player_plane_dir: Path, fidx: dict) -> pd.DataFrame:
    """Long table: one row per (player, match) with FINAL rating/minutes + the match kickoff.
    Used ONLY to compute prior form (date-filtered downstream)."""
    rows = []
    for pp in Path(player_plane_dir).glob("players_*.json"):
        fid = int(pp.stem.split("_")[1])
        if fid not in fidx:
            continue
        ko = fidx[fid]["kickoff"]
        data = json.loads(pp.read_text(encoding="utf-8")).get("response", [])
        for team in data:
            tid = team.get("team", {}).get("id")
            for pl in team.get("players", []):
                pid = pl.get("player", {}).get("id")
                st = (pl.get("statistics") or [{}])[0]
                games = st.get("games") or {}
                rating = games.get("rating")
                rows.append({
                    "match_id": fid, "kickoff": ko, "team_id": tid, "player_id": pid,
                    "minutes": games.get("minutes") or 0,
                    "rating": float(rating) if rating not in (None, "") else np.nan,
                    "started": not bool(games.get("substitute", True)),
                })
    return pd.DataFrame(rows)


def startxi_by_match(player_plane_dir: Path) -> dict:
    """fixture_id -> {team_id: {"xi": [player_ids], "formation": str}} from lineups (pre-match)."""
    out = {}
    for lp in Path(player_plane_dir).glob("lineups_*.json"):
        fid = int(lp.stem.split("_")[1])
        data = json.loads(lp.read_text(encoding="utf-8")).get("response", [])
        tt = {}
        for team in data:
            tid = team.get("team", {}).get("id")
            xi = [p["player"]["id"] for p in team.get("startXI", []) if p.get("player")]
            tt[tid] = {"xi": xi, "formation": team.get("formation")}
        out[fid] = tt
    return out


def team_xg(player_plane_dir: Path) -> dict:
    """fixture_id -> {team_id: xg_float} from statistics (FINAL total; outcome-only)."""
    out = {}
    for sp in Path(player_plane_dir).glob("statistics_*.json"):
        fid = int(sp.stem.split("_")[1])
        data = json.loads(sp.read_text(encoding="utf-8")).get("response", [])
        tt = {}
        for team in data:
            tid = team.get("team", {}).get("id")
            xg = np.nan
            for s in team.get("statistics", []):
                if str(s.get("type", "")).lower() == "expected_goals" and s.get("value") not in (None, ""):
                    xg = float(s["value"])
            tt[tid] = xg
        out[fid] = tt
    return out


def prior_form_lookup(records: pd.DataFrame) -> dict:
    """player_id -> sorted list of (kickoff, rating) with a rating, for fast date-filtered lookup."""
    lut: dict = {}
    r = records.dropna(subset=["rating"])
    for pid, grp in r.groupby("player_id"):
        lut[pid] = sorted((row.kickoff, row.rating) for row in grp.itertuples())
    return lut


def xi_prior_strength(xi: list, before: datetime, lut: dict) -> tuple:
    """Mean PRIOR-form rating across the starting XI, using only ratings dated strictly before `before`.
    Returns (mean_strength, coverage) where coverage = fraction of XI with any prior rating."""
    vals = []
    for pid in xi:
        hist = [rt for (ko, rt) in lut.get(pid, []) if ko < before]
        if hist:
            vals.append(sum(hist) / len(hist))
    cov = (len(vals) / len(xi)) if xi else 0.0
    return (float(np.mean(vals)) if vals else np.nan, cov)


def team_prior_minutes(records: pd.DataFrame) -> dict:
    """team_id -> list of (kickoff, player_id, minutes), for leakage-safe key-player identification."""
    lut: dict = {}
    for r in records.itertuples():
        lut.setdefault(r.team_id, []).append((r.kickoff, r.player_id, r.minutes or 0))
    return lut


def key_player_availability(team_min_list: list, before: datetime, xi: list, topk: int = 6) -> tuple:
    """Fraction of a team's top-`topk` players (by cumulative minutes in matches STRICTLY BEFORE
    `before`) who appear in today's starting XI. Captures rotation / key absences — orthogonal to Elo.
    Returns (availability, coverage)."""
    mins: dict = {}
    for (ko, pid, m) in team_min_list:
        if ko < before:
            mins[pid] = mins.get(pid, 0.0) + (m or 0)
    ranked = [pid for pid, mm in sorted(mins.items(), key=lambda x: -x[1]) if mm > 0][:topk]
    if not ranked:
        return (np.nan, 0.0)
    xis = set(xi)
    avail = sum(1 for pid in ranked if pid in xis) / len(ranked)
    return (float(avail), len(ranked) / topk)


def build_player_plane_features(comp_caches: dict) -> pd.DataFrame:
    """comp_caches: {competition_id: (player_plane_dir, fixtures_json_path)} ->
    per-match pre-match feature table. Prior form is computed from the POOLED cross-competition history
    (a player's earlier matches in ANY of these competitions), always date-filtered (leakage-safe)."""
    # pool all records first so prior form can span competitions
    all_recs = []
    per_comp = {}
    for comp, (ppdir, fxp) in comp_caches.items():
        fidx = fixtures_index(Path(fxp))
        recs = player_match_records(Path(ppdir), fidx)
        recs["competition"] = comp
        all_recs.append(recs)
        per_comp[comp] = (Path(ppdir), fidx)
    records = pd.concat(all_recs, ignore_index=True) if all_recs else pd.DataFrame()
    lut = prior_form_lookup(records)
    tmin = team_prior_minutes(records)

    rows = []
    for comp, (ppdir, fidx) in per_comp.items():
        sxi = startxi_by_match(ppdir)
        xg = team_xg(ppdir)
        for fid, meta in fidx.items():
            tt = sxi.get(fid)
            if not tt:
                continue
            ko = meta["kickoff"]
            h, a = meta["home_id"], meta["away_id"]
            h_xi, a_xi = tt.get(h, {}).get("xi", []), tt.get(a, {}).get("xi", [])
            hs, hc = xi_prior_strength(h_xi, ko, lut)
            as_, ac = xi_prior_strength(a_xi, ko, lut)
            hka, hkc = key_player_availability(tmin.get(h, []), ko, h_xi)
            aka, akc = key_player_availability(tmin.get(a, []), ko, a_xi)
            rows.append({
                "competition": comp, "match_id": fid, "kickoff_utc": ko.isoformat(),
                "home_id": h, "away_id": a, "home_name": meta["home_name"], "away_name": meta["away_name"],
                "home_xi_strength": hs, "away_xi_strength": as_,
                "strength_diff": (hs - as_) if (pd.notna(hs) and pd.notna(as_)) else np.nan,
                "home_cov": hc, "away_cov": ac,
                "home_key_avail": hka, "away_key_avail": aka,
                "keyavail_diff": (hka - aka) if (pd.notna(hka) and pd.notna(aka)) else np.nan,
                "keyavail_cov": min(hkc, akc),
                "home_formation": tt.get(h, {}).get("formation"), "away_formation": tt.get(a, {}).get("formation"),
                "final_wld": meta["final_wld"],
                "home_xg": (xg.get(fid, {}) or {}).get(h, np.nan), "away_xg": (xg.get(fid, {}) or {}).get(a, np.nan),
            })
    return pd.DataFrame(rows).sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)
