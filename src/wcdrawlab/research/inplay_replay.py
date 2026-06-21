"""Research-only in-play replay layer (transparent remaining-time Poisson).

Thin wrapper over the existing `wcdrawlab.inplay.engine.update_inplay_probabilities` that adds the
deliverables requested for the in-play objective: remaining expected goals and a risk band, plus a
replay harness that scores a sequence of decision-time states using ONLY information available at
each decision minute (no post-match data).

Real event-time scoring requires timestamped historical event feeds (currently unavailable — see
BLOCKERS.md). This module provides the transparent benchmark + deterministic behavior tests; it is
not a runtime-approved model (B1/Elo remains the only approved model).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from wcdrawlab.inplay.engine import InPlayConfig, InPlayState, update_inplay_probabilities
from wcdrawlab.research.scoreline import ScorelineModel


def event_known_by(elapsed_minute, decision_minute) -> bool:
    """An event is usable at a decision minute only if it has already happened (elapsed <= decision)."""
    return elapsed_minute is not None and elapsed_minute <= decision_minute


def pre_match_odds_eligible(snapshot_utc, kickoff_utc) -> bool:
    """A pre-match odds snapshot is usable only if observed strictly before kickoff."""
    return pd.Timestamp(snapshot_utc) < pd.Timestamp(kickoff_utc)


def lineup_eligible(published_utc, decision_utc) -> bool:
    """A lineup/standings/tournament-state fact is usable only if published at/before the decision."""
    return pd.Timestamp(published_utc) <= pd.Timestamp(decision_utc)


def state_from_events(events: list[dict], decision_minute: int, team_a: str,
                      home_team: str, away_team: str) -> dict:
    """Leakage-safe match state oriented to team_a, using ONLY events with elapsed <= decision_minute.
    events: API-Football-style [{time:{elapsed}, team:{name}, type, detail}]. Own goals credit the
    opponent; missed penalties are ignored; red cards counted from Card/'Red' detail."""
    gA = gB = rA = rB = 0
    for e in events:
        elapsed = (e.get("time") or {}).get("elapsed")
        if not event_known_by(elapsed, decision_minute):
            continue  # future event -> excluded (no leakage)
        etype = e.get("type"); det = str(e.get("detail") or "")
        eteam = (e.get("team") or {}).get("name", "")
        if etype == "Goal":
            if "Missed" in det:
                continue
            scorer = (home_team if eteam == away_team else away_team) if det == "Own Goal" else eteam
            if scorer == team_a:
                gA += 1
            else:
                gB += 1
        elif etype == "Card" and "Red" in det:
            if eteam == team_a:
                rA += 1
            else:
                rB += 1
    return {"goals_a": gA, "goals_b": gB, "red_cards_a": rA, "red_cards_b": rB}


def risk_band(entropy: float) -> str:
    """Normalized 3-way entropy (0..1) -> qualitative risk band for decision gating."""
    if entropy < 0.55:
        return "low"
    if entropy < 0.85:
        return "medium"
    return "high"


def pregame_lambdas_from_elo(elo_delta: float, model: ScorelineModel | None = None) -> tuple[float, float]:
    """Pre-match goal intensities from elo_delta via the (calibrated or default) scoreline mapping."""
    m = model or ScorelineModel(mode="poisson")
    la, lb = m.lambdas([elo_delta])
    return float(la[0]), float(lb[0])


@dataclass(frozen=True)
class InPlayReplayOutput:
    minute: float
    p_a_win: float
    p_draw: float
    p_b_win: float
    remaining_xg_a: float
    remaining_xg_b: float
    remaining_xg_total: float
    p_draw_ci_low: float
    p_draw_ci_high: float
    entropy: float
    risk_band: str


def replay_prediction(pregame_lambda_a: float, pregame_lambda_b: float, state: InPlayState,
                      config: InPlayConfig | None = None) -> InPlayReplayOutput:
    pred = update_inplay_probabilities(pregame_lambda_a, pregame_lambda_b, state, config)
    return InPlayReplayOutput(
        minute=float(state.minute),
        p_a_win=pred.p_a_win, p_draw=pred.p_draw, p_b_win=pred.p_b_win,
        remaining_xg_a=pred.lambda_a_remaining, remaining_xg_b=pred.lambda_b_remaining,
        remaining_xg_total=pred.lambda_a_remaining + pred.lambda_b_remaining,
        p_draw_ci_low=pred.p_draw_ci_low, p_draw_ci_high=pred.p_draw_ci_high,
        entropy=pred.entropy, risk_band=risk_band(pred.entropy),
    )


def replay_match(pregame_lambda_a: float, pregame_lambda_b: float, snapshots, config=None) -> list[dict]:
    """Score a sequence of decision-time snapshots. Each snapshot is a dict with keys
    minute, goals_a, goals_b, and optionally red_cards_a/red_cards_b/xg_a/xg_b — all of which must
    reflect ONLY events known at/before that minute (leakage-safe by construction of the caller).
    Returns one prediction dict per snapshot."""
    out = []
    for s in snapshots:
        state = InPlayState(
            minute=float(s["minute"]), goals_a=int(s["goals_a"]), goals_b=int(s["goals_b"]),
            red_cards_a=int(s.get("red_cards_a", 0)), red_cards_b=int(s.get("red_cards_b", 0)),
            xg_a=s.get("xg_a"), xg_b=s.get("xg_b"),
        )
        out.append(asdict(replay_prediction(pregame_lambda_a, pregame_lambda_b, state, config)))
    return out
