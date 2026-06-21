from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd
import numpy as np

from wcdrawlab.data import asof_join_team_rating, chronological_split
from wcdrawlab.ratings import standardize_fifa_release
from wcdrawlab.features import (
    add_basic_outcome_columns,
    add_strength_deltas,
    build_pre_match_group_state,
    add_schedule_adjusted_state,
    add_low_block_risk,
    add_travel_fatigue,
)
from wcdrawlab.market import no_vig_from_decimal_odds, edge_scan
from wcdrawlab.models.baselines import HistoricalPriorModel, TernaryEloModel, GaussianDrawEloModel, MultinomialLogitModel
from wcdrawlab.models.scoreline import IndependentPoissonModel
from wcdrawlab.calibration import DrawLogitCalibrator
from wcdrawlab.evaluation import metric_report
from wcdrawlab.risk import RiskConfig, add_prediction_risk_columns


@dataclass
class PipelineResult:
    metrics: pd.DataFrame
    predictions: pd.DataFrame
    edges: pd.DataFrame


def build_features(matches: pd.DataFrame, elo: pd.DataFrame | None = None, fifa: pd.DataFrame | None = None, odds: pd.DataFrame | None = None) -> pd.DataFrame:
    df = matches.copy()
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)

    if elo is not None and not elo.empty:
        elo = elo.copy()
        elo["rating_date"] = pd.to_datetime(elo["rating_date"], utc=True)
        df = asof_join_team_rating(df, elo, "team_a", "kickoff_utc", "team", "rating_date", ["elo"], suffix="_a")
        df = asof_join_team_rating(df, elo, "team_b", "kickoff_utc", "team", "rating_date", ["elo"], suffix="_b")

    if fifa is not None and not fifa.empty:
        fifa = standardize_fifa_release(fifa.copy())
        fifa["release_date"] = pd.to_datetime(fifa["release_date"], utc=True)
        df = asof_join_team_rating(df, fifa, "team_a", "kickoff_utc", "team", "release_date", ["fifa_rank", "fifa_points", "fifa_points_z", "fifa_rank_percentile"], suffix="_a")
        df = asof_join_team_rating(df, fifa, "team_b", "kickoff_utc", "team", "release_date", ["fifa_rank", "fifa_points", "fifa_points_z", "fifa_rank_percentile"], suffix="_b")

    if odds is not None and not odds.empty:
        odds = odds.copy()
        odds["snapshot_time"] = pd.to_datetime(odds["snapshot_time"], utc=True)
        # Use the latest odds snapshot before kickoff per match.
        odds = odds.sort_values(["match_id", "snapshot_time"])
        last_odds = []
        for _, m in df[["match_id", "kickoff_utc"]].iterrows():
            o = odds[(odds["match_id"] == m["match_id"]) & (odds["snapshot_time"] <= m["kickoff_utc"])]
            if not o.empty:
                last_odds.append(o.iloc[-1])
        if last_odds:
            odds_latest = pd.DataFrame(last_odds)
            df = df.merge(odds_latest[["match_id", "odds_a", "odds_draw", "odds_b", "snapshot_time"]], on="match_id", how="left")
            valid_odds = df[["odds_a", "odds_draw", "odds_b"]].notna().all(axis=1)
            df["p_a_market"] = np.nan
            df["p_draw_market"] = np.nan
            df["p_b_market"] = np.nan
            if valid_odds.any():
                probs = no_vig_from_decimal_odds(df.loc[valid_odds, "odds_a"], df.loc[valid_odds, "odds_draw"], df.loc[valid_odds, "odds_b"])
                df.loc[valid_odds, "p_a_market"] = probs[:, 0]
                df.loc[valid_odds, "p_draw_market"] = probs[:, 1]
                df.loc[valid_odds, "p_b_market"] = probs[:, 2]

    # Make the downstream modules robust if optional data is absent.
    if "elo_a" not in df.columns:
        df["elo_a"] = np.nan
    if "elo_b" not in df.columns:
        df["elo_b"] = np.nan
    if df["elo_a"].isna().any() or df["elo_b"].isna().any():
        # Fallback neutral rating for rows without Elo, while preserving known rows.
        df["elo_a"] = df["elo_a"].fillna(1500.0)
        df["elo_b"] = df["elo_b"].fillna(1500.0)
    if "p_draw_market" not in df.columns:
        df["p_a_market"] = 1/3
        df["p_draw_market"] = 1/3
        df["p_b_market"] = 1/3
    if "market_total_goals" not in df.columns:
        df["market_total_goals"] = 2.35

    df = add_basic_outcome_columns(df) if {"goals_a", "goals_b"}.issubset(df.columns) else df
    df = add_strength_deltas(df)
    df = build_pre_match_group_state(df)
    df = add_schedule_adjusted_state(df)
    df = add_low_block_risk(df)
    df = add_travel_fatigue(df)
    return df


def run_walkforward_backtest(features: pd.DataFrame, test_start: str, outdir: str | Path = "outputs") -> PipelineResult:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    played = features[features["goals_a"].notna() & features["goals_b"].notna()].copy()
    train, test = chronological_split(played, "kickoff_utc", test_start)
    train = add_basic_outcome_columns(train)
    test = add_basic_outcome_columns(test)

    metric_rows = []
    prediction_frames = []
    risk_config = RiskConfig(n_eff=max(30.0, min(float(len(train)), 400.0)))

    model_specs = {
        "historical_prior": HistoricalPriorModel().fit(train["outcome"]),
        "ternary_elo": TernaryEloModel(r=0.4),
        "gaussian_draw": GaussianDrawEloModel(),
        "multinomial_logit": MultinomialLogitModel(features=["elo_delta", "abs_elo_delta", "matchday", "prior_group_draws", "p_draw_market"]).fit(train, train["outcome"]),
    }
    for name, model in model_specs.items():
        probs = model.predict_proba(test)
        metric_rows.append({"model": name, **metric_report(test["outcome"], probs)})
        pred = test[["match_id", "kickoff_utc", "team_a", "team_b", "outcome"]].copy()
        pred[["p_a", "p_draw", "p_b"]] = probs
        pred["model"] = name
        pred = add_prediction_risk_columns(pred, config=risk_config)
        prediction_frames.append(pred)

    score_features = ["elo_delta", "abs_elo_delta", "matchday", "market_total_goals", "prior_group_draws", "p_draw_market", "low_block_risk", "travel_fatigue"]
    score_features = [c for c in score_features if c in train.columns]
    score = IndependentPoissonModel(score_features, rho=-0.05, diagonal_inflation=0.05)
    score.fit(train, train["goals_a"], train["goals_b"])
    base_test_probs = score.predict_proba(test)
    metric_rows.append({"model": "scoreline_poisson_dc_diag", **metric_report(test["outcome"], base_test_probs)})

    base_train_probs = score.predict_proba(train)
    cal_train = train.copy(); cal_train["p_draw_score"] = base_train_probs[:, 1]
    cal_test = test.copy(); cal_test["p_draw_score"] = base_test_probs[:, 1]
    cal_features = ["p_draw_score", "p_draw_market", "abs_elo_delta", "market_total_goals", "prior_group_draws", "low_block_risk", "travel_fatigue"]
    cal_features = [c for c in cal_features if c in cal_train.columns]
    cal = DrawLogitCalibrator(cal_features, C=0.5)
    cal.fit(cal_train, train["is_draw"])
    calibrated = cal.apply(base_test_probs, cal_test)
    metric_rows.append({"model": "scoreline_plus_draw_calibrator", **metric_report(test["outcome"], calibrated)})

    pred = test[["match_id", "kickoff_utc", "team_a", "team_b", "outcome"]].copy()
    pred[["p_a", "p_draw", "p_b"]] = calibrated
    pred["model"] = "scoreline_plus_draw_calibrator"
    pred = add_prediction_risk_columns(pred, config=risk_config)
    prediction_frames.append(pred)

    metrics = pd.DataFrame(metric_rows).sort_values("rps")
    predictions = pd.concat(prediction_frames, ignore_index=True)
    final = test.copy()
    final[["p_a_model", "p_draw_model", "p_b_model"]] = calibrated
    final = add_prediction_risk_columns(final, prob_cols=("p_a_model", "p_draw_model", "p_b_model"), config=risk_config)
    edges = edge_scan(final) if {"p_draw_market", "odds_draw"}.issubset(final.columns) else pd.DataFrame()

    metrics.to_csv(outdir / "metrics.csv", index=False)
    predictions.to_csv(outdir / "predictions.csv", index=False)
    if not edges.empty:
        edges.to_csv(outdir / "edges.csv", index=False)
    return PipelineResult(metrics=metrics, predictions=predictions, edges=edges)
