"""Build leakage-safe multi-competition in-play state + target tables from StatsBomb events.

Decision points are a deterministic 5-minute grid; the STATE at minute m uses only events with
minute < m (strictly before -> no look-ahead). Targets (next goal, next card, next sub, final result)
use events at minute >= m and are returned in SEPARATE tables from the features.

Provider-aware semantics: goals = shots with outcome 'Goal' for the shooter's team, plus 'Own Goal For'
events credited to the beneficiary team (no inversion). Data provided by StatsBomb (non-commercial).
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

from wcdrawlab.ingest import canonical_team_name

GRID = list(range(5, 96, 5))  # decision minutes 5..95


def events_sha256(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def _card_name(e):
    for k in ("foul_committed", "bad_behaviour"):
        c = (e.get(k) or {}).get("card")
        if c:
            return c.get("name")
    return None


def extract_events(events: list) -> dict:
    """Return goals/cards/subs/shots as minute-stamped (minute, team, ...) lists."""
    goals, cards, subs, shots = [], [], [], []
    for e in events:
        t = (e.get("type") or {}).get("name")
        team = (e.get("team") or {}).get("name")
        minute = e.get("minute")
        if minute is None:
            continue
        if t == "Shot":
            sh = e.get("shot") or {}
            xg = sh.get("statsbomb_xg")
            is_goal = (sh.get("outcome") or {}).get("name") == "Goal"
            shots.append((minute, team, float(xg) if xg is not None else 0.0, int(is_goal)))
            if is_goal:
                goals.append((minute, team))
        elif t == "Own Goal For":
            goals.append((minute, team))  # beneficiary team (StatsBomb credits the benefiting side)
        elif t in ("Foul Committed", "Bad Behaviour"):
            cn = _card_name(e)
            if cn:
                cards.append((minute, team, cn))
        elif t == "Substitution":
            subs.append((minute, team))
    return {"goals": goals, "cards": cards, "subs": subs, "shots": shots}


def starting_xi(lineups: list) -> dict:
    """team_name -> list of starting player_ids (positions present => started)."""
    out = {}
    for tm in lineups or []:
        name = tm.get("team_name")
        xi = []
        for p in tm.get("lineup", []):
            pos = p.get("positions") or []
            if pos and (pos[0].get("start_reason") in ("Starting XI", None) or pos[0].get("from") in ("00:00", None)):
                # treat players with a position starting at 00:00 as starters
                if any(po.get("from") == "00:00" for po in pos) or pos[0].get("start_reason") == "Starting XI":
                    xi.append(p.get("player_id"))
        out[name] = xi
    return out


def _count_before(items, minute, team_pred):
    return sum(1 for it in items if it[0] < minute and team_pred(it))


def build_match(extracted: dict, home: str, away: str, *, sb_match_id, match_date, competition_id,
                competition_type, confederation, elo_delta_home, p_elo, coverage: dict,
                src_sha: str) -> tuple:
    """Return (state_rows, next_goal_rows, card_rows, sub_rows, match_target_row)."""
    ch, ca = canonical_team_name(home), canonical_team_name(away)
    def is_h(it): return canonical_team_name(it[1]) == ch
    def is_a(it): return canonical_team_name(it[1]) == ca
    g, c, s, sh = extracted["goals"], extracted["cards"], extracted["subs"], extracted["shots"]
    reds = [(m, t) for (m, t, nm) in c if nm in ("Red Card", "Second Yellow")]
    yels = [(m, t) for (m, t, nm) in c if nm == "Yellow Card"]

    final_h = sum(1 for it in g if is_h(it)); final_a = sum(1 for it in g if is_a(it))
    final_wld = "H" if final_h > final_a else ("A" if final_a > final_h else "D")

    state, ng, cardt, subt = [], [], [], []
    for m in GRID:
        sh_h = sum(x[2] for x in sh if x[0] < m and is_h(x))
        sh_a = sum(x[2] for x in sh if x[0] < m and is_a(x))
        key = {"sb_match_id": sb_match_id, "decision_minute": m}
        state.append({
            **key, "competition_id": competition_id, "competition_type": competition_type,
            "confederation": confederation, "match_date": match_date,
            "decision_timestamp": f"{match_date}+{m:02d}min", "home_team": home, "away_team": away,
            "score_home": _count_before(g, m, is_h), "score_away": _count_before(g, m, is_a),
            "red_home": _count_before(reds, m, is_h), "red_away": _count_before(reds, m, is_a),
            "yellow_home": _count_before(yels, m, is_h), "yellow_away": _count_before(yels, m, is_a),
            "subs_home": _count_before(s, m, is_h), "subs_away": _count_before(s, m, is_a),
            "live_xg_home": float(sh_h), "live_xg_away": float(sh_a), "live_xg_diff": float(sh_h - sh_a),
            "remaining_minutes": max(0, 95 - m),
            "elo_delta_home": elo_delta_home,
            "p_home_elo": p_elo[0], "p_draw_elo": p_elo[1], "p_away_elo": p_elo[2],
            "lineup_available": coverage["lineup"], "xg_available": coverage["xg"],
            "player_ids_available": coverage["player_ids"], "data_360_available": coverage["d360"],
            "event_coverage_ok": coverage["events_ok"], "source_events_sha256": src_sha,
        })
        state[-1]["score_diff"] = state[-1]["score_home"] - state[-1]["score_away"]
        # targets (minute >= m -> future)
        nxt = [it for it in sorted(g) if it[0] >= m]
        ng.append({**key, "next_goal_team": ("H" if nxt and is_h(nxt[0]) else "A" if nxt else "NONE")})
        cardt.append({**key, "red_after": int(any(r[0] >= m for r in reds)),
                      "yellow_after": int(any(y[0] >= m for y in yels))})
        subt.append({**key, "sub_after": int(any(x[0] >= m for x in s))})
    mt = {"sb_match_id": sb_match_id, "final_wld": final_wld,
          "final_score_home": final_h, "final_score_away": final_a}
    return state, ng, cardt, subt, mt
