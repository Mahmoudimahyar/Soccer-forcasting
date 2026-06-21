"""Forecast the remaining 2026 World Cup group-stage matches (MD2 + MD3) and simulate
advancement, using FROZEN model architectures and only pre-decision information.

Models (frozen): B1 ternary-Elo (best DEV-mean) and B7 Platt-calibrated ensemble
(best DEV worst-fold). B7 is the headline forecaster; B1 is shown for comparison.

Prequential note: trained on all played WC group matches available now (1998-2022 +
completed 2026 matches). For each upcoming match, Elo and group state reflect only
results that finished before kickoff. MD3 forecasts will sharpen after MD2 completes;
re-run this script after each result with the after-game update workflow.

Outputs (outputs/research/forecasts/):
  forecast_2026_md2_md3.csv   per-match probs (B1 & B7) + uncertainty fields
  advancement_2026.csv        per-team advancement probability (Monte Carlo, best-third)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from wcdrawlab.evaluation import normalize_probs  # noqa: E402
from wcdrawlab.risk import add_prediction_risk_columns  # noqa: E402
from wcdrawlab.simulation.official_standings import simulate_group_stage_official as simulate_group_stage  # noqa: E402
import evaluate_baselines as eb  # noqa: E402  (reuse frozen predictors)

SNAPSHOT = "2026-06-20"  # decision-time snapshot stamp
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs" / "research" / "forecasts"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    played = pd.read_csv(PROC / "research_modeling_table.csv", parse_dates=["kickoff_utc"])
    upcoming = pd.read_csv(PROC / "forecast_targets_2026.csv", parse_dates=["kickoff_utc"])

    train = played  # all played WC group matches (frozen-architecture training set)

    # --- per-match forecasts for the 44 upcoming fixtures ---
    p_b1 = normalize_probs(eb.b1_elo(train, upcoming))
    p_b7 = normalize_probs(eb.b7_ensemble(train, upcoming))

    fc = upcoming[["match_id", "group", "matchday", "team_a", "team_b", "kickoff_utc",
                   "elo_a", "elo_b", "elo_delta", "points_a_pre", "points_b_pre",
                   "prior_group_draws"]].copy()
    fc["p_a_elo"], fc["p_draw_elo"], fc["p_b_elo"] = p_b1[:, 0], p_b1[:, 1], p_b1[:, 2]
    fc["p_a"], fc["p_draw"], fc["p_b"] = p_b7[:, 0], p_b7[:, 1], p_b7[:, 2]
    fc = add_prediction_risk_columns(fc, prob_cols=("p_a", "p_draw", "p_b"))
    fc["model"] = "B7_calibrated_ensemble"
    fc["snapshot"] = SNAPSHOT
    fc = fc.sort_values(["matchday", "kickoff_utc", "group"]).reset_index(drop=True)

    out_cols = ["snapshot", "match_id", "matchday", "group", "team_a", "team_b", "kickoff_utc",
                "elo_a", "elo_b", "elo_delta", "points_a_pre", "points_b_pre", "prior_group_draws",
                "p_a", "p_draw", "p_b", "p_a_elo", "p_draw_elo", "p_b_elo",
                "prob_se_draw", "prob_ci_low_draw", "prob_ci_high_draw",
                "prediction_entropy", "confidence_score", "max_outcome_prob", "risk_band"]
    fc[out_cols].to_csv(OUT / "forecast_2026_md2_md3.csv", index=False)

    # --- advancement simulation over all 72 group fixtures ---
    common = [c for c in played.columns if c in upcoming.columns]
    fixtures = pd.concat([played[common], upcoming[common]], ignore_index=True)
    fixtures = fixtures[fixtures["tournament"].astype(str).str.contains("2026")].reset_index(drop=True)
    probs_all = normalize_probs(eb.b7_ensemble(train, fixtures))
    adv = simulate_group_stage(fixtures, probs_all, n_sims=20000, third_place_slots=8, seed=42)
    adv["group"] = adv["team"].map(
        fixtures.assign(t=fixtures["team_a"]).set_index("team_a")["group"].to_dict()
        | fixtures.assign(t=fixtures["team_b"]).set_index("team_b")["group"].to_dict()
    )
    adv = adv[["group", "team", "p_advance", "p_first", "p_second", "p_third_advance"]]
    adv = adv.sort_values(["group", "p_advance"], ascending=[True, False]).reset_index(drop=True)
    adv.to_csv(OUT / "advancement_2026.csv", index=False)

    # --- console: the immediate objective (MD2), then advancement ---
    pd.set_option("display.width", 160)
    md2 = fc[fc.matchday == 2]
    print(f"=== 2026 MATCHDAY 2 FORECAST (snapshot {SNAPSHOT}, model B7) — {len(md2)} matches ===")
    show = md2[["group", "team_a", "team_b", "p_a", "p_draw", "p_b", "risk_band"]].copy()
    for c in ("p_a", "p_draw", "p_b"):
        show[c] = (show[c] * 100).round(0).astype(int)
    print(show.to_string(index=False))

    md3 = fc[fc.matchday == 3]
    print(f"\n=== 2026 MATCHDAY 3 FORECAST (provisional; sharpens after MD2) — {len(md3)} matches ===")
    show3 = md3[["group", "team_a", "team_b", "p_a", "p_draw", "p_b"]].copy()
    for c in ("p_a", "p_draw", "p_b"):
        show3[c] = (show3[c] * 100).round(0).astype(int)
    print(show3.to_string(index=False))

    print("\n=== ADVANCEMENT PROBABILITY (top 2 per group + best thirds; 20k sims) ===")
    print(adv.assign(p_advance=(adv.p_advance * 100).round(0).astype(int)).to_string(index=False))
    print("\nwrote:", OUT)


if __name__ == "__main__":
    main()
