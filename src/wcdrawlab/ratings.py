from __future__ import annotations

import numpy as np
import pandas as pd


def standardize_fifa_release(fifa: pd.DataFrame) -> pd.DataFrame:
    """Add within-release FIFA z-score and percentile.

    Raw FIFA points are not safely comparable across eras. This creates features
    that are comparable within each release date.
    """
    df = fifa.copy()
    required = {"release_date", "team", "fifa_points", "fifa_rank"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"FIFA dataframe missing columns: {missing}")
    g = df.groupby("release_date")
    mean = g["fifa_points"].transform("mean")
    sd = g["fifa_points"].transform("std").replace(0, np.nan)
    df["fifa_points_z"] = (df["fifa_points"] - mean) / sd
    # Better teams have smaller ranks, so convert to high-is-good percentile.
    n = g["fifa_rank"].transform("count")
    df["fifa_rank_percentile"] = 1.0 - ((df["fifa_rank"] - 1) / (n - 1).replace(0, np.nan))
    return df


def elo_expected_score(delta: np.ndarray | float, scale: float = 400.0) -> np.ndarray:
    """Standard Elo expected score for team A."""
    return 1.0 / (1.0 + 10.0 ** (-(np.asarray(delta, dtype=float)) / scale))


def ternary_elo_probs(delta: np.ndarray | float, r: float = 0.4, home_advantage: float = 0.0) -> np.ndarray:
    """Toy three-way Elo decomposition.

    Returns columns [A win, draw, B win]. The parameter r should be fitted, not trusted.
    This is a benchmark, not the final model.
    """
    p = elo_expected_score(np.asarray(delta, dtype=float) + home_advantage)
    p_a = p**2 + r * p * (1.0 - p)
    p_b = (1.0 - p) ** 2 + r * p * (1.0 - p)
    p_d = 1.0 - p_a - p_b
    probs = np.vstack([p_a, p_d, p_b]).T
    return np.clip(probs, 1e-9, 1.0)


def gaussian_draw_prob(delta: np.ndarray | float, draw_base: float = 0.30, draw_width: float = 240.0) -> np.ndarray:
    """Simple draw benchmark: peak near equal ratings, decays with abs rating gap."""
    delta = np.asarray(delta, dtype=float)
    return draw_base * np.exp(-(delta**2) / (2.0 * draw_width**2))
