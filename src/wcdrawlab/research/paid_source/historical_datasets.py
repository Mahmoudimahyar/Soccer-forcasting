"""Phase 4: causal, provenance-preserving historical dataset builders for API-Football corpus.

Causal invariants (all enforced here):
  - any in-play state feature at decision minute t uses ONLY events with elapsed <= t (no future goal/sub/card).
  - regulation targets use regulation goals only (elapsed <= 90); extra-time + shootout kept separate.
  - player-on-pitch uses only starting XI + substitutions with minute <= t.
  - own goals credited to the event `team` (beneficiary) — see result_semantics.
  - club and international rows are partitioned by comp_type and never mixed without labels.
research_only.
"""
from __future__ import annotations

from . import result_semantics as RS


def parse_lineup(team_lineup: dict) -> dict:
    starters = [{"player_id": (p.get("player") or {}).get("id"),
                 "pos": (p.get("player") or {}).get("pos"),
                 "number": (p.get("player") or {}).get("number")}
                for p in (team_lineup.get("startXI") or [])]
    bench = [{"player_id": (p.get("player") or {}).get("id"), "pos": (p.get("player") or {}).get("pos")}
             for p in (team_lineup.get("substitutes") or [])]
    return {"team_id": (team_lineup.get("team") or {}).get("id"),
            "formation": team_lineup.get("formation"), "starters": starters, "bench": bench}


def substitutions(events) -> list:
    """[{minute, team_id, in_player_id, out_player_id}] from subst events (player=in, assist=out in API-Football)."""
    subs = []
    for e in events:
        if (e.get("type") or "").lower() != "subst":
            continue
        subs.append({"minute": (e.get("time") or {}).get("elapsed"),
                     "team_id": (e.get("team") or {}).get("id"),
                     "in_player_id": (e.get("player") or {}).get("id"),
                     "out_player_id": (e.get("assist") or {}).get("id")})
    return subs


def players_on_pitch(starter_ids, subs, t):
    """Set of player_ids on the pitch at decision minute t. Uses ONLY subs with minute <= t (no future leak)."""
    on = set(pid for pid in starter_ids if pid is not None)
    for s in sorted([x for x in subs if x["minute"] is not None and x["minute"] <= t], key=lambda x: x["minute"]):
        if s["out_player_id"] in on:
            on.discard(s["out_player_id"])
        if s["in_player_id"] is not None:
            on.add(s["in_player_id"])
    return on


def events_up_to(events, t):
    return [e for e in events if (e.get("time") or {}).get("elapsed") is not None
            and (e.get("time") or {}).get("elapsed") <= t]


def regulation_state_at(events, home_id, away_id, t):
    """Regulation (home, away) score using only goals with elapsed <= min(t, 90). No ET/shootout."""
    return RS.derive_window_score(events, home_id, away_id, 0, min(t, 90))


def cards_table(events):
    """Per-card rows; classifies second yellow (player's 2nd yellow) vs direct red."""
    yel = {}
    rows = []
    for e in events:
        if (e.get("type") or "").lower() != "card":
            continue
        d = (e.get("detail") or "").lower()
        pid = (e.get("player") or {}).get("id")
        minute = (e.get("time") or {}).get("elapsed")
        team = (e.get("team") or {}).get("id")
        if "yellow" in d:
            yel[pid] = yel.get(pid, 0) + 1
            klass = "second_yellow" if yel[pid] >= 2 else "yellow"
        elif "red" in d:
            klass = "second_yellow_red" if yel.get(pid, 0) >= 1 else "direct_red"
        else:
            klass = "other"
        rows.append({"player_id": pid, "team_id": team, "minute": minute, "card_class": klass})
    return rows


def partition(comp_type):
    return "international" if comp_type == "international" else "club"
