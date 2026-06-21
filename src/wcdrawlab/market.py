from __future__ import annotations

import numpy as np
import pandas as pd

from wcdrawlab.risk import add_draw_bet_risk_columns


def decimal_odds_to_implied(odds: np.ndarray | pd.DataFrame) -> np.ndarray:
    arr = np.asarray(odds, dtype=float)
    if (arr <= 1).any():
        raise ValueError("Decimal odds must be > 1.")
    return 1.0 / arr


def remove_overround(implied: np.ndarray) -> np.ndarray:
    arr = np.asarray(implied, dtype=float)
    return arr / arr.sum(axis=1, keepdims=True)


def no_vig_from_decimal_odds(odds_a, odds_d, odds_b) -> np.ndarray:
    odds = np.vstack([odds_a, odds_d, odds_b]).T.astype(float)
    return remove_overround(decimal_odds_to_implied(odds))


def fair_odds(p: np.ndarray | float, eps: float = 1e-9) -> np.ndarray:
    return 1.0 / np.clip(np.asarray(p, dtype=float), eps, 1.0)


def edge_scan(
    df: pd.DataFrame,
    p_model_col: str = "p_draw_model",
    p_market_col: str = "p_draw_market",
    odds_col: str = "odds_draw",
    min_edge: float = 0.04,
    safety_margin: float = 0.02,
) -> pd.DataFrame:
    out = df.copy()
    out["edge_draw"] = out[p_model_col] - out[p_market_col]
    out["fair_odds_draw"] = fair_odds(out[p_model_col])
    out["edge_required"] = min_edge + safety_margin
    out["bet_draw"] = (out["edge_draw"] >= out["edge_required"]) & (out[odds_col] > out["fair_odds_draw"])
    out = add_draw_bet_risk_columns(out, p_col=p_model_col, odds_col=odds_col)
    return out.sort_values("edge_draw", ascending=False)


def kelly_fraction(p: float | np.ndarray, decimal_odds: float | np.ndarray, fraction: float = 1.0) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    o = np.asarray(decimal_odds, dtype=float)
    b = o - 1.0
    q = 1.0 - p
    f = (b * p - q) / b
    return fraction * np.clip(f, 0.0, 1.0)
