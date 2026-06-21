"""Evaluate baselines B0-B7 across the full leakage-safe fold hierarchy.

Fold hierarchy (master protocol):
  DEV  (model selection): train<2010 -> 2010 ; train<2014 -> 2014 ; train<2018 -> 2018
  GATE (release):         train<2022 -> 2022
  LOCKED (transfer only): train<2026 -> 2026 Matchday 1   (never used for selection)

Objective J = 0.40 RPS + 0.25 LogLoss + 0.20 draw-Brier + 0.15 draw-calibration-error.
Primary target is calibrated probability quality, NOT accuracy. We also report worst-fold.

Outputs (outputs/research/baselines/):
  by_fold.csv         metrics for every baseline x fold
  summary.csv         per-baseline DEV mean, DEV worst-fold, 2022, 2026MD1
  reliability_*.csv   draw reliability tables for the ensemble
  predictions_2026_md1.csv  per-match probs + uncertainty fields for the locked fold
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.evaluation import metric_report, normalize_probs  # noqa: E402
from wcdrawlab.research.runner import draw_calibration_error  # noqa: E402
from wcdrawlab.models.baselines import (  # noqa: E402
    HistoricalPriorModel, TernaryEloModel, MultinomialLogitModel,
)
from wcdrawlab.models.scoreline import IndependentPoissonModel  # noqa: E402
from wcdrawlab.calibration import IsotonicDrawCalibrator  # noqa: E402
from wcdrawlab.risk import add_prediction_risk_columns  # noqa: E402

TABLE = ROOT / "data" / "processed" / "research_modeling_table.csv"
OUT = ROOT / "outputs" / "research" / "baselines"

WEIGHTS = {"rps": 0.40, "log_loss": 0.25, "draw_brier": 0.20, "draw_calibration_error": 0.15}

LOGIT_FEATURES = [
    "elo_delta", "abs_elo_delta", "matchday", "prior_group_draws",
    "prior_group_goals_per_match", "group_state_points_delta", "group_state_gd_delta",
    "venue_host_advantage", "confed_same",
]
HOST_FEATURES = ["elo_delta", "abs_elo_delta", "venue_host_advantage"]
POISSON_FEATURES = ["elo_delta", "abs_elo_delta", "venue_host_advantage"]

FOLDS = [
    ("dev_2010", 2010, 2010, None),
    ("dev_2014", 2014, 2014, None),
    ("dev_2018", 2018, 2018, None),
    ("gate_2022", 2022, 2022, None),
    ("locked_2026_md1", 2026, 2026, 1),
]


def composite(m: dict) -> float:
    return float(sum(WEIGHTS[k] * m[k] for k in WEIGHTS))


def all_metrics(y, probs) -> dict:
    probs = normalize_probs(probs)
    m = metric_report(y, probs)  # log_loss, rps, draw_brier, draw_ece
    m["draw_calibration_error"] = draw_calibration_error(y, probs[:, 1])
    m["composite"] = composite(m)
    pred = np.array(["A", "D", "B"])[probs.argmax(1)]
    m["accuracy"] = float((pred == np.asarray(y)).mean())
    m["draw_rate_actual"] = float((np.asarray(y) == "D").mean())
    m["draw_rate_pred"] = float(probs[:, 1].mean())
    m["mean_entropy"] = float((-probs * np.log(np.clip(probs, 1e-12, 1)) / np.log(3)).sum(1).mean())
    return m


# ---- baseline predictors: each returns probs (n,3) for `test` given `train` ----------
def b0_prior(train, test):
    return HistoricalPriorModel().fit(train["outcome"]).predict_proba(len(test))

def b1_elo(train, test):
    return TernaryEloModel(r=0.4).predict_proba(test)

FIFA_FEATURES = ["fifa_z_delta", "abs_fifa_z_delta", "fifa_rank_pct_delta", "abs_fifa_rank_pct_delta"]

def b2_fifa(train, test):
    # Real FIFA-only baseline (release-normalized FIFA ranking deltas). Falls back to the
    # general feature logit if FIFA columns are absent.
    cols = [c for c in FIFA_FEATURES if c in train.columns] or \
           [c for c in LOGIT_FEATURES if c in train.columns]
    return MultinomialLogitModel(features=cols, C=0.5).fit(train, train["outcome"]).predict_proba(test)

def _general_logit(train, test):
    cols = [c for c in LOGIT_FEATURES if c in train.columns]
    return MultinomialLogitModel(features=cols, C=0.5).fit(train, train["outcome"]).predict_proba(test)

def b3_elo_host(train, test):
    return MultinomialLogitModel(features=HOST_FEATURES, C=0.5).fit(train, train["outcome"]).predict_proba(test)

def b4_poisson(train, test):
    m = IndependentPoissonModel(features=POISSON_FEATURES, rho=0.0)
    m.fit(train, train["goals_a"].astype(int), train["goals_b"].astype(int))
    return m.predict_proba(test)

def b5_dixon_coles(train, test):
    m = IndependentPoissonModel(features=POISSON_FEATURES, rho=-0.05, diagonal_inflation=0.05)
    m.fit(train, train["goals_a"].astype(int), train["goals_b"].astype(int))
    return m.predict_proba(test)

def _platt_draw_recalibrate(p_draw_train, y_is_draw_train, base_test):
    """Robust 2-parameter Platt scaling on logit(p_draw); rescales A/B proportionally.
    Far less prone to overfitting than isotonic on small tournament samples."""
    from sklearn.linear_model import LogisticRegression
    def logit(p):
        p = np.clip(p, 1e-4, 1 - 1e-4)
        return np.log(p / (1 - p))
    lr = LogisticRegression(C=1.0, max_iter=1000)
    lr.fit(logit(p_draw_train).reshape(-1, 1), y_is_draw_train.astype(int))
    new_draw = lr.predict_proba(logit(base_test[:, 1]).reshape(-1, 1))[:, 1]
    out = base_test.copy()
    nondraw = np.clip(1 - new_draw, 1e-9, None)
    ab = base_test[:, [0, 2]]
    ab_sum = np.clip(ab.sum(1, keepdims=True), 1e-9, None)
    out[:, 0] = nondraw * ab[:, 0] / ab_sum.ravel()
    out[:, 2] = nondraw * ab[:, 1] / ab_sum.ravel()
    out[:, 1] = new_draw
    return normalize_probs(out)


def b7_ensemble(train, test):
    """Average B1(elo)+B5(DC)+B2(logit), then robust Platt draw recalibration
    (2 params) fit in-sample on the full train blend."""
    members = [b1_elo, b5_dixon_coles, _general_logit]
    base_test = normalize_probs(np.mean([f(train, test) for f in members], axis=0))
    base_train = normalize_probs(np.mean([f(train, train) for f in members], axis=0))
    y_tr = (train["outcome"] == "D").to_numpy().astype(float)
    return _platt_draw_recalibrate(base_train[:, 1], y_tr, base_test)


BASELINES = {
    "B0_historical_prior": b0_prior,
    "B1_ternary_elo": b1_elo,
    "B2_fifa_only": b2_fifa,
    "B3_elo_plus_host": b3_elo_host,
    "B4_independent_poisson": b4_poisson,
    "B5_dixon_coles": b5_dixon_coles,
    "B7_calibrated_ensemble": b7_ensemble,
    # B6 no-vig market is intentionally absent: no real timestamped odds are available.
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(TABLE, parse_dates=["kickoff_utc"])
    df["year"] = df["kickoff_utc"].dt.year

    rows = []
    ens_test_pool = []  # for reliability
    for fold_name, before, test_year, md in FOLDS:
        train = df[df["year"] < before].copy()
        test = df[df["year"] == test_year].copy()
        if md is not None:
            test = test[test["matchday"] == md].copy()
        if train.empty or test.empty:
            print(f"[skip] {fold_name}: train={len(train)} test={len(test)}")
            continue
        y = test["outcome"]
        for name, fn in BASELINES.items():
            probs = fn(train, test)
            m = all_metrics(y, probs)
            m.update(model=name, fold=fold_name, n_train=len(train), n_test=len(test))
            rows.append(m)
            if name == "B7_calibrated_ensemble":
                tt = test.copy()
                tt[["p_a", "p_draw", "p_b"]] = normalize_probs(probs)
                tt["fold"] = fold_name
                ens_test_pool.append(tt)

    res = pd.DataFrame(rows)
    keep = ["model", "fold", "n_train", "n_test", "rps", "log_loss", "draw_brier",
            "draw_calibration_error", "composite", "accuracy", "draw_rate_actual",
            "draw_rate_pred", "mean_entropy"]
    res = res[keep].sort_values(["fold", "composite"])
    res.to_csv(OUT / "by_fold.csv", index=False)

    # summary: DEV mean + DEV worst-fold + gate + locked, per model
    dev = res[res.fold.str.startswith("dev_")]
    summ = []
    for name in BASELINES:
        d = dev[dev.model == name]
        g = res[(res.model == name) & (res.fold == "gate_2022")]
        lk = res[(res.model == name) & (res.fold == "locked_2026_md1")]
        summ.append({
            "model": name,
            "dev_composite_mean": round(d["composite"].mean(), 4),
            "dev_composite_worst": round(d["composite"].max(), 4),
            "dev_rps_mean": round(d["rps"].mean(), 4),
            "dev_logloss_mean": round(d["log_loss"].mean(), 4),
            "dev_drawbrier_mean": round(d["draw_brier"].mean(), 4),
            "dev_drawcal_mean": round(d["draw_calibration_error"].mean(), 4),
            "gate2022_composite": round(g["composite"].mean(), 4) if len(g) else None,
            "locked2026md1_composite": round(lk["composite"].mean(), 4) if len(lk) else None,
            "locked2026md1_drawcal": round(lk["draw_calibration_error"].mean(), 4) if len(lk) else None,
        })
    summary = pd.DataFrame(summ).sort_values("dev_composite_mean")
    summary.to_csv(OUT / "summary.csv", index=False)

    # reliability for the ensemble (pooled dev test) + uncertainty fields on locked fold
    from wcdrawlab.research.runner import draw_calibration_error as _dce  # noqa
    pool = pd.concat(ens_test_pool, ignore_index=True)
    dev_pool = pool[pool.fold.str.startswith("dev_")]
    rel = _reliability(dev_pool["outcome"], dev_pool["p_draw"].to_numpy())
    rel.to_csv(OUT / "reliability_ensemble_dev.csv", index=False)

    locked = pool[pool.fold == "locked_2026_md1"].copy()
    if not locked.empty:
        locked = add_prediction_risk_columns(locked, prob_cols=("p_a", "p_draw", "p_b"))
        cols = ["match_id", "group", "matchday", "team_a", "team_b", "elo_delta", "outcome",
                "p_a", "p_draw", "p_b", "prob_se_draw", "prob_ci_low_draw", "prob_ci_high_draw",
                "prediction_entropy", "confidence_score", "max_outcome_prob", "risk_band"]
        locked[[c for c in cols if c in locked.columns]].to_csv(OUT / "predictions_2026_md1.csv", index=False)

    cov = _draw_interval_coverage(dev_pool["outcome"], dev_pool["p_draw"].to_numpy())

    print("=== SUMMARY (sorted by DEV composite; lower is better) ===")
    print(summary.to_string(index=False))
    print("\n=== Ensemble draw reliability (pooled DEV) ===")
    print(rel.to_string(index=False))
    print(f"\nEnsemble DEV draw-interval coverage (bins inside 90% beta CI): {cov:.2f}")
    print("\nwrote:", OUT)


def _reliability(y, p_draw, bins=10) -> pd.DataFrame:
    y_d = (np.asarray(y) == "D").astype(float)
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p_draw >= lo) & ((p_draw < hi) if hi < 1 else (p_draw <= hi))
        if mask.any():
            out.append({"bin": f"[{lo:.1f},{hi:.1f})", "n": int(mask.sum()),
                        "pred_draw": round(float(p_draw[mask].mean()), 3),
                        "actual_draw": round(float(y_d[mask].mean()), 3)})
    return pd.DataFrame(out)


def _draw_interval_coverage(y, p_draw, bins=10) -> float:
    """Fraction of reliability bins whose empirical draw rate lies within a 90% CI
    around the predicted mean (binomial normal approx)."""
    y_d = (np.asarray(y) == "D").astype(float)
    edges = np.linspace(0, 1, bins + 1)
    inside, total = 0, 0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p_draw >= lo) & ((p_draw < hi) if hi < 1 else (p_draw <= hi))
        n = int(mask.sum())
        if n >= 5:
            p = float(p_draw[mask].mean())
            se = np.sqrt(max(p * (1 - p), 1e-9) / n)
            actual = float(y_d[mask].mean())
            total += 1
            inside += int(abs(actual - p) <= 1.645 * se)
    return inside / total if total else float("nan")


if __name__ == "__main__":
    main()
