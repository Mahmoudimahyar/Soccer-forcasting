from __future__ import annotations

from dataclasses import dataclass
from math import exp

import numpy as np
from scipy.stats import poisson

from wcdrawlab.evaluation import normalize_probs


@dataclass(frozen=True)
class InPlayState:
    minute: float
    goals_a: int
    goals_b: int
    red_cards_a: int = 0
    red_cards_b: int = 0
    xg_a: float | None = None
    xg_b: float | None = None
    event_observed_at_unix: float | None = None


@dataclass(frozen=True)
class InPlayConfig:
    max_goals_remaining: int = 8
    # Conservative, inspectable adjustments. These are research parameters, not truths.
    red_card_attack_penalty: float = 0.30
    red_card_opponent_attack_boost: float = 0.18
    trailing_attack_boost_per_goal: float = 0.14
    leading_attack_penalty_per_goal: float = 0.05
    xg_blend_strength: float = 0.35
    min_remaining_lambda: float = 0.01
    max_remaining_lambda: float = 5.0
    n_eff_base: float = 80.0


@dataclass(frozen=True)
class InPlayPrediction:
    p_a_win: float
    p_draw: float
    p_b_win: float
    lambda_a_remaining: float
    lambda_b_remaining: float
    p_draw_se: float
    p_draw_ci_low: float
    p_draw_ci_high: float
    entropy: float


def _remaining_lambdas(
    pregame_lambda_a: float,
    pregame_lambda_b: float,
    state: InPlayState,
    config: InPlayConfig,
) -> tuple[float, float]:
    effective_minutes = max(0.0, min(120.0, float(state.minute)))
    # 90 is intentional: this model predicts regulation result. Added time can be
    # handled later from event data once calibrated.
    time_fraction = max(0.0, (90.0 - effective_minutes) / 90.0)
    la = pregame_lambda_a * time_fraction
    lb = pregame_lambda_b * time_fraction

    # Score-state dynamics: trailing team becomes more aggressive; leading team modestly
    # reduces attacking intensity. These coefficients are fixed evaluator parameters for
    # autoresearch and should be tested, not tuned live.
    score_diff = state.goals_a - state.goals_b
    if score_diff < 0:
        la *= 1.0 + config.trailing_attack_boost_per_goal * abs(score_diff)
        lb *= max(0.2, 1.0 - config.leading_attack_penalty_per_goal * abs(score_diff))
    elif score_diff > 0:
        lb *= 1.0 + config.trailing_attack_boost_per_goal * abs(score_diff)
        la *= max(0.2, 1.0 - config.leading_attack_penalty_per_goal * abs(score_diff))

    # Red cards shift the remaining goal hazards. Multiple cards compound.
    if state.red_cards_a:
        la *= max(0.05, 1.0 - config.red_card_attack_penalty) ** state.red_cards_a
        lb *= (1.0 + config.red_card_opponent_attack_boost) ** state.red_cards_a
    if state.red_cards_b:
        lb *= max(0.05, 1.0 - config.red_card_attack_penalty) ** state.red_cards_b
        la *= (1.0 + config.red_card_opponent_attack_boost) ** state.red_cards_b

    # Optional xG surprise adjustment. It changes remaining scoring intensity only
    # slightly, and is skipped if the xG feed is unavailable.
    elapsed_fraction = max(1e-6, effective_minutes / 90.0)
    if state.xg_a is not None:
        expected_elapsed_a = pregame_lambda_a * elapsed_fraction
        surprise_a = np.clip(state.xg_a - expected_elapsed_a, -2.0, 2.0)
        la *= exp(config.xg_blend_strength * surprise_a / max(0.5, pregame_lambda_a))
    if state.xg_b is not None:
        expected_elapsed_b = pregame_lambda_b * elapsed_fraction
        surprise_b = np.clip(state.xg_b - expected_elapsed_b, -2.0, 2.0)
        lb *= exp(config.xg_blend_strength * surprise_b / max(0.5, pregame_lambda_b))

    return (
        float(np.clip(la, config.min_remaining_lambda, config.max_remaining_lambda)),
        float(np.clip(lb, config.min_remaining_lambda, config.max_remaining_lambda)),
    )


def update_inplay_probabilities(
    pregame_lambda_a: float,
    pregame_lambda_b: float,
    state: InPlayState,
    config: InPlayConfig | None = None,
) -> InPlayPrediction:
    """Compute regulation-time 1X2 probabilities conditional on live state.

    Future additional goals are modeled by independent remaining-time Poisson hazards.
    This is a transparent benchmark for research; it is not yet a production-approved
    execution model until calibrated on event-level historical data.
    """
    cfg = config or InPlayConfig()
    la, lb = _remaining_lambdas(pregame_lambda_a, pregame_lambda_b, state, cfg)
    goals = np.arange(cfg.max_goals_remaining + 1)
    pa = poisson.pmf(goals, la)
    pb = poisson.pmf(goals, lb)
    matrix = np.outer(pa, pb)
    matrix = matrix / matrix.sum()

    p_a = p_d = p_b = 0.0
    for add_a in range(matrix.shape[0]):
        for add_b in range(matrix.shape[1]):
            final_a = state.goals_a + add_a
            final_b = state.goals_b + add_b
            if final_a > final_b:
                p_a += matrix[add_a, add_b]
            elif final_a == final_b:
                p_d += matrix[add_a, add_b]
            else:
                p_b += matrix[add_a, add_b]
    probs = normalize_probs(np.array([[p_a, p_d, p_b]], dtype=float))[0]

    # Estimate uncertainty grows if only weak/no live information is available, and
    # shrinks modestly as the match clock resolves the outcome.
    evidence = cfg.n_eff_base + max(0.0, state.minute) * 0.5 + (25.0 if state.xg_a is not None and state.xg_b is not None else 0.0)
    se_draw = float(np.sqrt(probs[1] * (1.0 - probs[1]) / max(1.0, evidence)))
    lo = float(max(0.0, probs[1] - 1.96 * se_draw))
    hi = float(min(1.0, probs[1] + 1.96 * se_draw))
    entropy = float(-np.sum(np.where(probs > 0, probs * np.log(probs), 0.0)) / np.log(3.0))
    return InPlayPrediction(
        p_a_win=float(probs[0]), p_draw=float(probs[1]), p_b_win=float(probs[2]),
        lambda_a_remaining=la, lambda_b_remaining=lb,
        p_draw_se=se_draw, p_draw_ci_low=lo, p_draw_ci_high=hi, entropy=entropy,
    )
