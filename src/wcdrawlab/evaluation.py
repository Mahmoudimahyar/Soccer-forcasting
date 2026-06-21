from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

OUTCOME_ORDER = ["A", "D", "B"]


def outcome_to_index(y: pd.Series | list[str]) -> np.ndarray:
    mapper = {k: i for i, k in enumerate(OUTCOME_ORDER)}
    return np.asarray([mapper[v] for v in y])


def normalize_probs(p: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    p = np.clip(p, eps, 1.0)
    return p / p.sum(axis=1, keepdims=True)


def log_loss_3way(y_true: pd.Series | list[str], probs: np.ndarray) -> float:
    probs = normalize_probs(probs)
    idx = outcome_to_index(y_true)
    return float(-np.mean(np.log(probs[np.arange(len(idx)), idx])))


def rps_3way(y_true: pd.Series | list[str], probs: np.ndarray) -> float:
    """Ranked Probability Score for ordered outcomes [B loss/A win, draw, B win]? 

    We use [A, D, B] as the order. Lower is better.
    """
    probs = normalize_probs(probs)
    idx = outcome_to_index(y_true)
    y_onehot = np.zeros_like(probs)
    y_onehot[np.arange(len(idx)), idx] = 1.0
    return float(np.mean(np.sum((np.cumsum(probs, axis=1) - np.cumsum(y_onehot, axis=1)) ** 2, axis=1) / 2.0))


def brier_draw(y_true: pd.Series | list[str], p_draw: np.ndarray) -> float:
    y = np.asarray([1 if v == "D" else 0 for v in y_true])
    return float(brier_score_loss(y, p_draw))


def draw_calibration_table(y_true: pd.Series | list[str], p_draw: np.ndarray, bins: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"is_draw": [1 if v == "D" else 0 for v in y_true], "p_draw": p_draw})
    df["bin"] = pd.cut(df["p_draw"], bins=np.linspace(0, 1, bins + 1), include_lowest=True)
    tab = df.groupby("bin", observed=True).agg(n=("is_draw", "size"), pred=("p_draw", "mean"), actual=("is_draw", "mean")).reset_index()
    tab["abs_error"] = (tab["pred"] - tab["actual"]).abs()
    return tab


def expected_calibration_error_draw(y_true: pd.Series | list[str], p_draw: np.ndarray, bins: int = 10) -> float:
    tab = draw_calibration_table(y_true, p_draw, bins=bins)
    if tab.empty:
        return float("nan")
    return float((tab["n"] * tab["abs_error"]).sum() / tab["n"].sum())


def metric_report(y_true: pd.Series | list[str], probs: np.ndarray) -> dict[str, float]:
    probs = normalize_probs(probs)
    return {
        "log_loss": log_loss_3way(y_true, probs),
        "rps": rps_3way(y_true, probs),
        "draw_brier": brier_draw(y_true, probs[:, 1]),
        "draw_ece": expected_calibration_error_draw(y_true, probs[:, 1]),
    }
