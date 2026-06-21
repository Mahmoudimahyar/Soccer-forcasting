from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.stats import beta

from wcdrawlab.evaluation import normalize_probs


@dataclass(frozen=True)
class RiskConfig:
    """Configuration for predictive-risk summaries.

    n_eff controls the width of the probability-estimate interval. It is not the
    number of historical matches. It is an *effective* sample size after model
    complexity, temporal drift, and calibration uncertainty are considered.
    Lower values intentionally produce wider intervals.
    """

    n_eff: float = 150.0
    interval_alpha: float = 0.05
    eps: float = 1e-9


def categorical_variance(probs: np.ndarray) -> np.ndarray:
    """Outcome-level variance for each categorical indicator.

    If Y_j = 1 when outcome j occurs and 0 otherwise, then Var(Y_j)=p_j(1-p_j).
    This is irreducible aleatoric uncertainty: even a perfectly calibrated model
    with p_draw=0.30 still has sd_draw=sqrt(0.30*0.70)=0.458 for the event.
    """

    p = normalize_probs(probs)
    return p * (1.0 - p)


def categorical_covariance(probs: np.ndarray) -> np.ndarray:
    """Full covariance matrices for categorical outcomes.

    For one-hot categorical Y with probabilities p, Cov(Y_i,Y_j) = -p_i p_j
    when i != j, and p_i(1-p_i) on the diagonal.
    """

    p = normalize_probs(probs)
    mats = []
    for row in p:
        cov = -np.outer(row, row)
        np.fill_diagonal(cov, row * (1.0 - row))
        mats.append(cov)
    return np.asarray(mats)


def probability_standard_error(p: np.ndarray | pd.Series, n_eff: float = 150.0, eps: float = 1e-9) -> np.ndarray:
    """Approximate model-estimation standard error for a probability estimate.

    This treats the calibrated probability as the mean of a local binomial/Beta
    evidence pool with effective sample size n_eff. It is a pragmatic uncertainty
    proxy for ranking predictions by robustness, not a proof of posterior validity.
    """

    p = np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)
    n_eff = max(float(n_eff), 1.0)
    return np.sqrt(p * (1.0 - p) / n_eff)


def beta_probability_interval(
    p: np.ndarray | pd.Series,
    n_eff: float = 150.0,
    alpha: float = 0.05,
    eps: float = 1e-9,
) -> tuple[np.ndarray, np.ndarray]:
    """Beta approximation interval for an estimated probability.

    We use alpha_post = 1 + p*n_eff and beta_post = 1 + (1-p)*n_eff.
    This is intentionally conservative for small n_eff and avoids zero-width
    intervals for p near 0 or 1.
    """

    p = np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)
    n_eff = max(float(n_eff), 1.0)
    a = 1.0 + p * n_eff
    b = 1.0 + (1.0 - p) * n_eff
    lo = beta.ppf(alpha / 2.0, a, b)
    hi = beta.ppf(1.0 - alpha / 2.0, a, b)
    return lo, hi


def entropy(probs: np.ndarray, base: float = 3.0) -> np.ndarray:
    """Normalized entropy in [0,1] for a three-way probability vector.

    0 means near-certainty; 1 means maximum uncertainty at [1/3,1/3,1/3].
    """

    p = normalize_probs(probs)
    return -np.sum(p * np.log(np.clip(p, 1e-12, 1.0)), axis=1) / np.log(base)


def confidence_score(probs: np.ndarray) -> np.ndarray:
    """Simple confidence score: 1 - normalized entropy."""

    return 1.0 - entropy(probs)


def risk_band(p_max: np.ndarray | pd.Series, entropy_value: np.ndarray | pd.Series) -> np.ndarray:
    """Human-readable uncertainty band for match-outcome predictions.

    This combines sharpness (max probability) with entropy. It is meant for reports,
    not model training.
    """

    pmax = np.asarray(p_max, dtype=float)
    ent = np.asarray(entropy_value, dtype=float)
    out = np.full(len(pmax), "high", dtype=object)
    out[(pmax >= 0.55) & (ent <= 0.75)] = "medium"
    out[(pmax >= 0.68) & (ent <= 0.55)] = "low"
    return out


def add_prediction_risk_columns(
    df: pd.DataFrame,
    prob_cols: tuple[str, str, str] = ("p_a", "p_draw", "p_b"),
    config: RiskConfig | None = None,
) -> pd.DataFrame:
    """Append risk / standard-deviation columns to prediction rows.

    Adds two different uncertainty families:
    1. outcome_sd_*: irreducible event volatility sqrt(p(1-p));
    2. prob_se_* and *_ci_*: approximate uncertainty in the probability estimate.
    """

    cfg = config or RiskConfig()
    out = df.copy()
    probs = normalize_probs(out.loc[:, list(prob_cols)].to_numpy(dtype=float))
    variances = categorical_variance(probs)
    sds = np.sqrt(variances)
    prob_ses = probability_standard_error(probs, n_eff=cfg.n_eff, eps=cfg.eps)

    labels = ["a", "draw", "b"]
    for j, label in enumerate(labels):
        out[f"outcome_var_{label}"] = variances[:, j]
        out[f"outcome_sd_{label}"] = sds[:, j]
        out[f"prob_se_{label}"] = prob_ses[:, j]
        lo, hi = beta_probability_interval(probs[:, j], n_eff=cfg.n_eff, alpha=cfg.interval_alpha, eps=cfg.eps)
        out[f"prob_ci_low_{label}"] = lo
        out[f"prob_ci_high_{label}"] = hi

    out["prediction_entropy"] = entropy(probs)
    out["confidence_score"] = confidence_score(probs)
    out["max_outcome_prob"] = probs.max(axis=1)
    out["risk_band"] = risk_band(out["max_outcome_prob"], out["prediction_entropy"])
    return out


def add_draw_bet_risk_columns(
    df: pd.DataFrame,
    p_col: str = "p_draw_model",
    odds_col: str = "odds_draw",
    bankroll_col: str | None = None,
    stake_fraction: float = 1.0,
) -> pd.DataFrame:
    """Append expected-value and standard-deviation columns for draw bets.

    Profit is measured per 1 unit staked:
      X = odds-1 if the draw occurs, else -1.
    E[X] = p*(odds-1) - (1-p)
    Var(X) = E[X^2] - E[X]^2
    This is the risk that actually matters for bet sizing.
    """

    out = df.copy()
    p = np.clip(out[p_col].astype(float).to_numpy(), 1e-9, 1.0 - 1e-9)
    o = out[odds_col].astype(float).to_numpy()
    win_profit = o - 1.0
    lose_profit = -1.0
    ev = p * win_profit + (1.0 - p) * lose_profit
    e2 = p * (win_profit ** 2) + (1.0 - p) * (lose_profit ** 2)
    var = np.maximum(0.0, e2 - ev ** 2)
    sd = np.sqrt(var)
    out["draw_bet_ev_per_unit"] = ev
    out["draw_bet_var_per_unit"] = var
    out["draw_bet_sd_per_unit"] = sd
    out["draw_bet_sharpe_like"] = np.divide(ev, sd, out=np.zeros_like(ev), where=sd > 0)
    if bankroll_col and bankroll_col in out.columns:
        stake = out[bankroll_col].astype(float).to_numpy() * stake_fraction
        out["draw_bet_ev_currency"] = ev * stake
        out["draw_bet_sd_currency"] = sd * stake
    return out
