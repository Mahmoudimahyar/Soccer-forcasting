from __future__ import annotations

from pathlib import Path
import sys
import numpy as np
import pandas as pd

# Allow running without pip install -e .
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.features import add_basic_outcome_columns, add_strength_deltas, build_pre_match_group_state, add_schedule_adjusted_state, add_low_block_risk, add_travel_fatigue
from wcdrawlab.models.baselines import HistoricalPriorModel, TernaryEloModel, GaussianDrawEloModel, MultinomialLogitModel
from wcdrawlab.models.scoreline import IndependentPoissonModel
from wcdrawlab.calibration import DrawLogitCalibrator
from wcdrawlab.evaluation import metric_report, draw_calibration_table
from wcdrawlab.market import no_vig_from_decimal_odds, edge_scan, kelly_fraction
from wcdrawlab.simulation.group_simulator import simulate_group_stage
from wcdrawlab.simulation.utility import match_advance_utilities


def make_synthetic_matches(seed=7):
    rng = np.random.default_rng(seed)
    teams = [f"Team{i}" for i in range(1, 17)]
    elos = {t: 1350 + 35*i + rng.normal(0, 40) for i, t in enumerate(teams)}
    groups = {"A": teams[:4], "B": teams[4:8], "C": teams[8:12], "D": teams[12:16]}
    pair_order = [(0,1),(2,3),(0,2),(1,3),(0,3),(1,2)]
    rows = []
    match_id = 1
    date = pd.Timestamp("2026-06-11")
    for g, ts in groups.items():
        for k, (i,j) in enumerate(pair_order):
            a,b = ts[i], ts[j]
            delta = elos[a] - elos[b]
            # Synthetic goals: expected total lower when teams are close, slight favorite advantage.
            lam_a = np.exp(0.25 + delta/900)
            lam_b = np.exp(0.25 - delta/900)
            ga = rng.poisson(lam_a)
            gb = rng.poisson(lam_b)
            rows.append({
                "match_id": match_id,
                "kickoff_utc": date + pd.Timedelta(days=k//2, hours=match_id),
                "tournament": "Synthetic Cup",
                "stage": "group",
                "group": g,
                "matchday": k//2 + 1,
                "team_a": a,
                "team_b": b,
                "goals_a": ga,
                "goals_b": gb,
                "neutral": True,
                "elo_a": elos[a],
                "elo_b": elos[b],
                "fifa_points_z_a": (elos[a]-1600)/150 + rng.normal(0, 0.15),
                "fifa_points_z_b": (elos[b]-1600)/150 + rng.normal(0, 0.15),
                "market_total_goals": float(np.clip(2.6 - abs(delta)/1000 + rng.normal(0, 0.1), 1.8, 3.2)),
                "rest_days_a": rng.integers(3, 6),
                "rest_days_b": rng.integers(3, 6),
                "travel_miles_last7_a": rng.integers(0, 2500),
                "travel_miles_last7_b": rng.integers(0, 2500),
                "timezone_shift_a": rng.integers(0, 4),
                "timezone_shift_b": rng.integers(0, 4),
                "heat_index": rng.normal(82, 7),
                "fifa_rank_a": match_id + 10,
                "fifa_rank_b": match_id + 20,
            })
            match_id += 1
    df = pd.DataFrame(rows)
    df = add_basic_outcome_columns(df)
    df = add_strength_deltas(df)
    df = build_pre_match_group_state(df)
    df = add_schedule_adjusted_state(df)
    # synthetic odds from noisy probability guesses
    df["odds_a"] = np.clip(2.0 - df["elo_delta"]/800 + rng.normal(0, .1, len(df)), 1.25, 5.5)
    df["odds_b"] = np.clip(2.0 + df["elo_delta"]/800 + rng.normal(0, .1, len(df)), 1.25, 5.5)
    df["odds_draw"] = np.clip(3.25 + abs(df["elo_delta"])/350 + rng.normal(0, .15, len(df)), 2.6, 7.5)
    market = no_vig_from_decimal_odds(df["odds_a"], df["odds_draw"], df["odds_b"])
    df["p_a_market"] = market[:,0]
    df["p_draw_market"] = market[:,1]
    df["p_b_market"] = market[:,2]
    df["mutual_draw_utility"] = 0.0
    df["must_win_pressure_max"] = 0.0
    df["third_place_safety_min"] = 0.0
    df = add_low_block_risk(df)
    df = add_travel_fatigue(df)
    return df


def main():
    df = make_synthetic_matches()
    train = df.iloc[:16].copy()
    test = df.iloc[16:].copy()

    print("\n=== Synthetic data sample ===")
    print(df[["match_id", "group", "matchday", "team_a", "team_b", "goals_a", "goals_b", "outcome", "elo_delta"]].head())

    models = {
        "historical_prior": HistoricalPriorModel().fit(train["outcome"]),
        "ternary_elo": TernaryEloModel(r=0.4),
        "gaussian_draw": GaussianDrawEloModel(),
        "multinomial_logit": MultinomialLogitModel(features=["elo_delta", "abs_elo_delta", "matchday", "prior_group_draws", "p_draw_market"]).fit(train, train["outcome"]),
    }

    print("\n=== Baseline metrics ===")
    for name, model in models.items():
        probs = model.predict_proba(test)
        print(name, metric_report(test["outcome"], probs))

    score_features = ["elo_delta", "abs_elo_delta", "matchday", "market_total_goals", "prior_group_draws", "p_draw_market"]
    score_model = IndependentPoissonModel(score_features, rho=-0.05, diagonal_inflation=0.05)
    score_model.fit(train, train["goals_a"], train["goals_b"])
    base_probs = score_model.predict_proba(test)
    print("\n=== Scoreline model metrics ===")
    print(metric_report(test["outcome"], base_probs))

    calib_train_probs = score_model.predict_proba(train)
    cal_train = train.copy()
    cal_train["p_draw_score"] = calib_train_probs[:,1]
    cal_train["p_draw_market"] = train["p_draw_market"]
    cal_test = test.copy()
    cal_test["p_draw_score"] = base_probs[:,1]
    calibrator_features = ["p_draw_score", "p_draw_market", "abs_elo_delta", "market_total_goals", "prior_group_draws", "low_block_risk", "travel_fatigue"]
    calibrator = DrawLogitCalibrator(calibrator_features, C=0.5)
    calibrator.fit(cal_train, train["is_draw"])
    calibrated_probs = calibrator.apply(base_probs, cal_test)
    print("\n=== Calibrated draw metrics ===")
    print(metric_report(test["outcome"], calibrated_probs))
    print(draw_calibration_table(test["outcome"], calibrated_probs[:,1], bins=5))

    edge_df = test.copy()
    edge_df["p_draw_model"] = calibrated_probs[:,1]
    edge_df = edge_scan(edge_df, min_edge=0.02, safety_margin=0.01)
    edge_df["kelly_quarter"] = kelly_fraction(edge_df["p_draw_model"], edge_df["odds_draw"], fraction=0.25)
    print("\n=== Example edge scan ===")
    print(edge_df[["match_id", "team_a", "team_b", "p_draw_model", "p_draw_market", "odds_draw", "edge_draw", "fair_odds_draw", "bet_draw", "kelly_quarter"]].head(8))

    # Simulator demo on all fixtures with scoreline probabilities.
    all_probs = score_model.predict_proba(df)
    # Pretend last 8 matches are unplayed.
    future = df.copy()
    future.loc[future.index[-8:], ["goals_a", "goals_b"]] = np.nan
    sim = simulate_group_stage(future, all_probs, n_sims=200, third_place_slots=2, seed=123)
    print("\n=== Example simulation output ===")
    print(sim.head(10))

    target = future.iloc[-1]
    util = match_advance_utilities(future, all_probs, target["match_id"], target["team_a"], target["team_b"], n_sims=100, third_place_slots=2, seed=456)
    print("\n=== Example mutual draw utility for last fixture ===")
    print(target[["match_id", "team_a", "team_b"]].to_dict())
    print(util)


if __name__ == "__main__":
    main()
