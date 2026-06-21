from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
from typing import Any

import numpy as np
import pandas as pd

from wcdrawlab.evaluation import normalize_probs
from wcdrawlab.elo import EloUpdateConfig, update_elo_after_match_table, write_elo_outputs
from wcdrawlab.features import add_low_block_risk, add_travel_fatigue
from wcdrawlab.market import edge_scan
from wcdrawlab.models.baselines import TernaryEloModel, GaussianDrawEloModel
from wcdrawlab.pipeline import build_features
from wcdrawlab.risk import RiskConfig, add_prediction_risk_columns
from wcdrawlab.simulation.group_simulator import simulate_group_stage
from wcdrawlab.simulation.utility import match_advance_utilities


PREDICTION_TARGETS: dict[str, str] = {
    "p_a_model": "Probability team_a wins in regulation/group-stage result time.",
    "p_draw_model": "Probability the match ends level in regulation/group-stage result time.",
    "p_b_model": "Probability team_b wins in regulation/group-stage result time.",
    "fair_odds_draw": "Model-implied fair decimal odds for the draw = 1 / p_draw_model.",
    "p_advance_a": "Current simulated probability team_a advances from the group stage.",
    "p_advance_b": "Current simulated probability team_b advances from the group stage.",
    "draw_utility_a": "For team_a, P(advance|draw) - P(advance|loss).",
    "draw_utility_b": "For team_b, P(advance|draw) - P(advance|loss).",
    "mutual_draw_utility": "min(draw_utility_a, draw_utility_b); high values mean a draw helps both teams.",
    "must_win_pressure_max": "max(P(advance|win) - P(advance|draw)) across the two teams.",
    "outcome_sd_draw": "Irreducible standard deviation of the draw event sqrt(p_draw*(1-p_draw)).",
    "prob_se_draw": "Approximate standard error of the estimated draw probability.",
    "prob_ci_low_draw/prob_ci_high_draw": "Approximate interval for the draw probability estimate.",
    "prediction_entropy": "Normalized uncertainty of the full 1X2 probability vector.",
    "risk_band": "Human-readable uncertainty band: low, medium, or high.",
    "edge_draw": "p_draw_model - no-vig market draw probability.",
    "bet_draw": "True only when model edge clears the configured safety threshold and odds exceed fair odds.",
}


@dataclass(frozen=True)
class LivePredictionConfig:
    """Configuration for live post-game updates and remaining-match predictions.

    The default live model is intentionally conservative. It is designed to run even
    before a trained historical model is plugged in. It blends Elo-shape probabilities,
    a Gaussian draw benchmark, and no-vig market probabilities when available, then
    applies a small tournament-state adjustment after group utilities are simulated.
    """

    ternary_weight: float = 0.45
    gaussian_weight: float = 0.20
    market_weight: float = 0.35
    utility_draw_boost: float = 0.28
    must_win_draw_penalty: float = 0.22
    low_block_draw_boost: float = 0.10
    max_draw_adjustment: float = 0.10
    min_probability: float = 0.01
    max_draw_probability: float = 0.55
    risk_n_eff: float = 120.0
    n_sims: int = 500
    utility_sims: int = 100
    random_seed: int = 42
    update_elo_after_match: bool = True
    elo_k: float = 60.0
    elo_scale: float = 400.0
    elo_home_advantage: float = 0.0
    elo_round_change: bool = True


@dataclass
class LiveUpdateResult:
    updated_matches: pd.DataFrame
    features: pd.DataFrame
    predictions: pd.DataFrame
    advancement: pd.DataFrame
    edges: pd.DataFrame
    output_paths: dict[str, Path]
    updated_elo: pd.DataFrame | None = None
    elo_audit: pd.DataFrame | None = None


def update_match_result(
    matches: pd.DataFrame,
    match_id: str,
    goals_a: int,
    goals_b: int,
    source: str = "manual",
    completed_at: str | None = None,
) -> pd.DataFrame:
    """Return a match table with one result inserted or corrected.

    This is the core after-game update. It does not assume the previous value was
    empty: corrections are allowed, but they are marked in the notes column.
    """

    if goals_a < 0 or goals_b < 0:
        raise ValueError("goals_a and goals_b must be non-negative integers.")
    out = matches.copy()
    if "match_id" not in out.columns:
        raise ValueError("matches table must include match_id.")
    idx = out.index[out["match_id"].astype(str) == str(match_id)]
    if len(idx) != 1:
        raise ValueError(f"match_id {match_id!r} not found uniquely; matched {len(idx)} rows.")
    i = idx[0]
    old_ga = out.at[i, "goals_a"] if "goals_a" in out.columns else np.nan
    old_gb = out.at[i, "goals_b"] if "goals_b" in out.columns else np.nan
    out.at[i, "goals_a"] = int(goals_a)
    out.at[i, "goals_b"] = int(goals_b)
    if "data_source" not in out.columns:
        out["data_source"] = ""
    if "notes" not in out.columns:
        out["notes"] = ""
    stamp = completed_at or pd.Timestamp.utcnow().isoformat()
    correction = "updated" if pd.notna(old_ga) and pd.notna(old_gb) else "final"
    out.at[i, "data_source"] = source
    note = f"{correction} result {goals_a}-{goals_b} at {stamp} from {source}"
    prior_note = str(out.at[i, "notes"]) if pd.notna(out.at[i, "notes"]) else ""
    out.at[i, "notes"] = (prior_note + " | " + note).strip(" |")
    return out


def append_update_log(log_path: str | Path, match_id: str, goals_a: int, goals_b: int, source: str, completed_at: str | None = None) -> Path:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([
        {
            "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
            "completed_at": completed_at or "",
            "match_id": match_id,
            "goals_a": int(goals_a),
            "goals_b": int(goals_b),
            "source": source,
        }
    ])
    if path.exists():
        old = pd.read_csv(path)
        row = pd.concat([old, row], ignore_index=True)
    row.to_csv(path, index=False)
    return path


def _market_probs(features: pd.DataFrame) -> np.ndarray:
    if {"p_a_market", "p_draw_market", "p_b_market"}.issubset(features.columns):
        arr = features[["p_a_market", "p_draw_market", "p_b_market"]].astype(float).to_numpy()
        bad = ~np.isfinite(arr).all(axis=1) | (arr.sum(axis=1) <= 0)
        arr[bad] = np.array([1 / 3, 1 / 3, 1 / 3])
        return normalize_probs(arr)
    return np.tile(np.array([1 / 3, 1 / 3, 1 / 3], dtype=float), (len(features), 1))


def initial_live_probabilities(features: pd.DataFrame, config: LivePredictionConfig | None = None) -> np.ndarray:
    """Conservative deployable probability blend for all fixtures.

    This is not a substitute for the trained backtest winner. It is the safe live
    fallback used by the after-game workflow, so the system can always refresh the
    group state and produce risk-aware probabilities.
    """

    cfg = config or LivePredictionConfig()
    feats = features.copy()
    if "elo_delta" not in feats.columns:
        feats["elo_delta"] = 0.0
    ternary = TernaryEloModel(r=0.4).predict_proba(feats)
    gaussian = GaussianDrawEloModel().predict_proba(feats)
    market = _market_probs(feats)

    weights = np.array([cfg.ternary_weight, cfg.gaussian_weight, cfg.market_weight], dtype=float)
    # If market is just neutral because odds are missing, do not let it dominate.
    neutral_market = np.all(np.isclose(market, np.array([1 / 3, 1 / 3, 1 / 3]), atol=1e-6), axis=1)
    probs = np.empty_like(ternary)
    for i in range(len(feats)):
        w = weights.copy()
        if neutral_market[i]:
            w[2] = 0.10
        w = w / w.sum()
        probs[i] = w[0] * ternary[i] + w[1] * gaussian[i] + w[2] * market[i]
    return normalize_probs(np.clip(probs, cfg.min_probability, 1.0))


def _one_hot_played_probs(features: pd.DataFrame, unplayed_probs: np.ndarray) -> np.ndarray:
    """Use actual result as probability 1.0 for played matches; model probs otherwise."""
    out = normalize_probs(unplayed_probs.copy())
    if {"goals_a", "goals_b"}.issubset(features.columns):
        played = features["goals_a"].notna() & features["goals_b"].notna()
        if played.any():
            ga = features.loc[played, "goals_a"].astype(float).to_numpy()
            gb = features.loc[played, "goals_b"].astype(float).to_numpy()
            onehot = np.zeros((played.sum(), 3), dtype=float)
            onehot[ga > gb, 0] = 1.0
            onehot[ga == gb, 1] = 1.0
            onehot[ga < gb, 2] = 1.0
            out[played.to_numpy()] = onehot
    return out


def add_tournament_utilities(
    features: pd.DataFrame,
    probs: np.ndarray,
    config: LivePredictionConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate advancement and match-specific advance utilities."""

    cfg = config or LivePredictionConfig()
    fixtures = features.reset_index(drop=True).copy()
    probs_all = _one_hot_played_probs(fixtures, probs)
    advancement = simulate_group_stage(fixtures, probs_all, n_sims=cfg.n_sims, seed=cfg.random_seed)
    adv_map = dict(zip(advancement["team"], advancement["p_advance"]))
    third_map = dict(zip(advancement["team"], advancement.get("p_third_advance", pd.Series(0, index=advancement.index))))

    out = fixtures.copy()
    out["p_advance_a"] = out["team_a"].map(adv_map).fillna(0.0)
    out["p_advance_b"] = out["team_b"].map(adv_map).fillna(0.0)
    out["p_third_advance_a"] = out["team_a"].map(third_map).fillna(0.0)
    out["p_third_advance_b"] = out["team_b"].map(third_map).fillna(0.0)

    utility_rows: list[dict[str, Any]] = []
    unplayed = out["goals_a"].isna() | out["goals_b"].isna()
    for _, r in out.loc[unplayed].iterrows():
        util = match_advance_utilities(
            out,
            probs_all,
            r["match_id"],
            r["team_a"],
            r["team_b"],
            n_sims=cfg.utility_sims,
            seed=cfg.random_seed,
        )
        util["match_id"] = r["match_id"]
        utility_rows.append(util)
    if utility_rows:
        util_df = pd.DataFrame(utility_rows)
        out = out.merge(util_df, on="match_id", how="left")
    else:
        for c in [
            "p_adv_a_if_win", "p_adv_a_if_draw", "p_adv_a_if_loss",
            "p_adv_b_if_win", "p_adv_b_if_draw", "p_adv_b_if_loss",
            "draw_utility_a", "draw_utility_b", "mutual_draw_utility",
            "must_win_pressure_a", "must_win_pressure_b", "must_win_pressure_max",
        ]:
            out[c] = np.nan
    return out, advancement


def state_adjust_probabilities(
    features_with_utilities: pd.DataFrame,
    initial_probs: np.ndarray,
    config: LivePredictionConfig | None = None,
) -> np.ndarray:
    """Apply a small, smooth draw adjustment from live tournament state.

    This is deliberately bounded. It is not a hard override. It expresses the
    probability-theory idea that tournament state changes the prior odds of teams
    preferring a low-risk draw, while preserving the A-vs-B split from the base model.
    """

    cfg = config or LivePredictionConfig()
    p = normalize_probs(initial_probs.copy())
    out = p.copy()
    df = features_with_utilities.reset_index(drop=True)
    unplayed = df["goals_a"].isna() | df["goals_b"].isna()
    if not unplayed.any():
        return out

    mutual = df.get("mutual_draw_utility", pd.Series(0.0, index=df.index)).fillna(0.0).astype(float).clip(-1, 1).to_numpy()
    must = df.get("must_win_pressure_max", pd.Series(0.0, index=df.index)).fillna(0.0).astype(float).clip(0, 1).to_numpy()
    low_block = df.get("low_block_risk", pd.Series(0.0, index=df.index)).fillna(0.0).astype(float).clip(0, 1).to_numpy()

    raw_adj = cfg.utility_draw_boost * mutual - cfg.must_win_draw_penalty * must + cfg.low_block_draw_boost * low_block
    raw_adj = np.clip(raw_adj, -cfg.max_draw_adjustment, cfg.max_draw_adjustment)
    idxs = np.where(unplayed.to_numpy())[0]
    for i in idxs:
        old_draw = out[i, 1]
        new_draw = float(np.clip(old_draw + raw_adj[i], cfg.min_probability, cfg.max_draw_probability))
        old_non = max(out[i, 0] + out[i, 2], cfg.min_probability)
        ratio_a = out[i, 0] / old_non
        out[i, 1] = new_draw
        out[i, 0] = (1.0 - new_draw) * ratio_a
        out[i, 2] = (1.0 - new_draw) * (1.0 - ratio_a)
    return normalize_probs(out)


def make_live_predictions(features: pd.DataFrame, config: LivePredictionConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return remaining-match predictions, advancement table, and edges.

    The function runs in two passes: initial probabilities -> tournament utilities ->
    state-adjusted final probabilities. It returns only unplayed matches in the main
    predictions table, but the advancement table uses both played and unplayed matches.
    """

    cfg = config or LivePredictionConfig()
    feats = features.copy().sort_values("kickoff_utc").reset_index(drop=True)
    initial = initial_live_probabilities(feats, cfg)
    with_utils, advancement = add_tournament_utilities(feats, initial, cfg)
    # Recompute low-block risk after utilities exist, then apply state adjustment.
    with_utils = add_low_block_risk(add_travel_fatigue(with_utils))
    final_probs = state_adjust_probabilities(with_utils, initial, cfg)
    unplayed = with_utils["goals_a"].isna() | with_utils["goals_b"].isna()
    pred = with_utils.loc[unplayed].copy()
    pred_probs = final_probs[unplayed.to_numpy()]
    pred[["p_a_model", "p_draw_model", "p_b_model"]] = pred_probs
    pred["fair_odds_draw"] = 1.0 / np.clip(pred["p_draw_model"].astype(float), 1e-9, 1.0)
    pred = add_prediction_risk_columns(
        pred,
        prob_cols=("p_a_model", "p_draw_model", "p_b_model"),
        config=RiskConfig(n_eff=cfg.risk_n_eff),
    )
    # Also add user-friendly favorite labels.
    labels = np.array(["team_a_win", "draw", "team_b_win"])
    pred["most_likely_outcome"] = labels[np.argmax(pred_probs, axis=1)]
    pred["most_likely_team_or_draw"] = np.select(
        [pred["most_likely_outcome"] == "team_a_win", pred["most_likely_outcome"] == "team_b_win"],
        [pred["team_a"], pred["team_b"]],
        default="Draw",
    )
    if {"p_draw_market", "odds_draw"}.issubset(pred.columns):
        edges = edge_scan(pred, p_model_col="p_draw_model", p_market_col="p_draw_market", odds_col="odds_draw")
    else:
        edges = pd.DataFrame()
    return pred, advancement, edges


def run_after_match_update(
    matches_path: str | Path,
    match_id: str,
    goals_a: int,
    goals_b: int,
    elo_path: str | Path | None = None,
    fifa_path: str | Path | None = None,
    odds_path: str | Path | None = None,
    output_dir: str | Path = "outputs/live",
    current_matches_path: str | Path | None = None,
    source: str = "manual",
    completed_at: str | None = None,
    config: LivePredictionConfig | None = None,
    current_elo_path: str | Path | None = None,
    update_elo: bool | None = None,
) -> LiveUpdateResult:
    """End-to-end after-game refresh: update match result, Elo table, rebuild data, predict remaining."""

    cfg = config or LivePredictionConfig()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    matches = pd.read_csv(matches_path, parse_dates=["kickoff_utc"])
    updated = update_match_result(matches, match_id, goals_a, goals_b, source=source, completed_at=completed_at)
    current_path = Path(current_matches_path) if current_matches_path else output / "current_matches.csv"
    current_path.parent.mkdir(parents=True, exist_ok=True)
    updated.to_csv(current_path, index=False)
    append_update_log(output / "update_log.csv", match_id, goals_a, goals_b, source, completed_at)

    # For live operation, prefer the already-updated current Elo table when it exists.
    # Fall back to the seed/baseline Elo file on the first update.
    elo_current_path = Path(current_elo_path) if current_elo_path else (output / "current_elo.csv")
    elo_source_path = elo_current_path if elo_current_path.exists() else (Path(elo_path) if elo_path and Path(elo_path).exists() else None)
    elo = pd.read_csv(elo_source_path, parse_dates=["rating_date"]) if elo_source_path is not None else None
    updated_elo = None
    elo_audit = None
    should_update_elo = cfg.update_elo_after_match if update_elo is None else bool(update_elo)
    if should_update_elo:
        base_elo = elo if elo is not None else pd.DataFrame(columns=["team", "rating_date", "elo", "source", "notes"])
        elo_cfg = EloUpdateConfig(
            k=cfg.elo_k,
            scale=cfg.elo_scale,
            home_advantage=cfg.elo_home_advantage,
            round_change=cfg.elo_round_change,
        )
        updated_elo, elo_audit = update_elo_after_match_table(
            base_elo,
            updated,
            match_id=match_id,
            goals_a=goals_a,
            goals_b=goals_b,
            completed_at=completed_at,
            config=elo_cfg,
        )
        write_elo_outputs(updated_elo, elo_audit, elo_current_path, output / "elo_update_log.csv")
        elo = updated_elo
    fifa = pd.read_csv(fifa_path, parse_dates=["release_date"]) if fifa_path and Path(fifa_path).exists() else None
    odds = pd.read_csv(odds_path, parse_dates=["snapshot_time"]) if odds_path and Path(odds_path).exists() else None
    features = build_features(updated, elo=elo, fifa=fifa, odds=odds)
    predictions, advancement, edges = make_live_predictions(features, cfg)

    features_path = output / "features_after_update.csv"
    predictions_path = output / "predictions_remaining.csv"
    advancement_path = output / "advancement_probabilities.csv"
    edges_path = output / "draw_edges.csv"
    targets_path = output / "prediction_targets.json"
    features.to_csv(features_path, index=False)
    predictions.to_csv(predictions_path, index=False)
    advancement.to_csv(advancement_path, index=False)
    if not edges.empty:
        edges.to_csv(edges_path, index=False)
    targets_path.write_text(json.dumps(PREDICTION_TARGETS, indent=2), encoding="utf-8")

    paths = {
        "current_matches": current_path,
        "features": features_path,
        "predictions": predictions_path,
        "advancement": advancement_path,
        "targets": targets_path,
    }
    if updated_elo is not None:
        paths["current_elo"] = elo_current_path
        paths["elo_update_log"] = output / "elo_update_log.csv"
    if not edges.empty:
        paths["edges"] = edges_path
    return LiveUpdateResult(updated, features, predictions, advancement, edges, paths, updated_elo=updated_elo, elo_audit=elo_audit)


def run_live_prediction_refresh(
    matches_path: str | Path,
    elo_path: str | Path | None = None,
    fifa_path: str | Path | None = None,
    odds_path: str | Path | None = None,
    output_dir: str | Path = "outputs/live",
    config: LivePredictionConfig | None = None,
) -> LiveUpdateResult:
    """Refresh predictions from the current match table without inserting a new result."""

    cfg = config or LivePredictionConfig()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    matches = pd.read_csv(matches_path, parse_dates=["kickoff_utc"])
    elo = pd.read_csv(elo_path, parse_dates=["rating_date"]) if elo_path and Path(elo_path).exists() else None
    fifa = pd.read_csv(fifa_path, parse_dates=["release_date"]) if fifa_path and Path(fifa_path).exists() else None
    odds = pd.read_csv(odds_path, parse_dates=["snapshot_time"]) if odds_path and Path(odds_path).exists() else None
    features = build_features(matches, elo=elo, fifa=fifa, odds=odds)
    predictions, advancement, edges = make_live_predictions(features, cfg)
    features_path = output / "features_current.csv"
    predictions_path = output / "predictions_remaining.csv"
    advancement_path = output / "advancement_probabilities.csv"
    edges_path = output / "draw_edges.csv"
    targets_path = output / "prediction_targets.json"
    features.to_csv(features_path, index=False)
    predictions.to_csv(predictions_path, index=False)
    advancement.to_csv(advancement_path, index=False)
    if not edges.empty:
        edges.to_csv(edges_path, index=False)
    targets_path.write_text(json.dumps(PREDICTION_TARGETS, indent=2), encoding="utf-8")
    paths = {
        "features": features_path,
        "predictions": predictions_path,
        "advancement": advancement_path,
        "targets": targets_path,
    }
    if updated_elo is not None:
        paths["current_elo"] = elo_current_path
        paths["elo_update_log"] = output / "elo_update_log.csv"
    if not edges.empty:
        paths["edges"] = edges_path
    return LiveUpdateResult(matches, features, predictions, advancement, edges, paths)
