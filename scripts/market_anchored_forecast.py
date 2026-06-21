"""Combine the real market consensus (B6) with the research model forecast.

The market no-vig consensus is the strongest available probability benchmark, so it is the
PRIMARY forecast for matches where odds exist; the model is a secondary view and its
disagreements are recorded as prospective, falsifiable hypotheses (to be scored after the
matches, never bet here). Outputs a combined table + an advancement simulation driven by the
market-primary probabilities.
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
import evaluate_baselines as eb  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs" / "research" / "forecasts"
SNAP = "2026-06-20"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    model = pd.read_csv(OUT / "forecast_2026_md2_md3.csv")
    mkt = pd.read_csv(PROC / "market_features_2026.csv")

    j = model.merge(mkt[["match_id", "p_a_market", "p_draw_market", "p_b_market",
                         "market_total_goals", "n_books"]], on="match_id", how="left")
    j["has_market"] = j["p_a_market"].notna().astype(int)

    # edges (model - market) where market exists
    j["edge_a"] = j["p_a"] - j["p_a_market"]
    j["edge_draw"] = j["p_draw"] - j["p_draw_market"]
    j["edge_b"] = j["p_b"] - j["p_b_market"]
    j["max_abs_edge"] = j[["edge_a", "edge_draw", "edge_b"]].abs().max(axis=1)

    # HEADLINE forecast = VALIDATED market+Elo blend where odds exist (beats raw market OOS by
    # ~5% composite, 4/4 folds; see notes/research/20260620_cycle_4.md), else model fallback.
    from wcdrawlab.ratings import ternary_elo_probs
    Pe = ternary_elo_probs(j["elo_delta"].to_numpy())  # parameter-free Elo
    Pm = j[["p_a_market", "p_draw_market", "p_b_market"]].to_numpy()
    BLEND_W = 0.40  # weight on Elo; validated optimum ~0.4-0.5 on intl OOS CV
    Pblend = normalize_probs((1 - BLEND_W) * np.nan_to_num(Pm) + BLEND_W * Pe)
    Pmodel = normalize_probs(j[["p_a", "p_draw", "p_b"]].to_numpy())
    has = (j["has_market"] == 1).to_numpy()
    Pfinal = np.where(has[:, None], Pblend, Pmodel)
    j[["p_a_final", "p_draw_final", "p_b_final"]] = normalize_probs(Pfinal)
    j["forecast_source"] = np.where(has, "market_elo_blend_0.4", "model_elo_blend_no_odds")

    # uncertainty on the final forecast
    tmp = j.rename(columns={"p_a_final": "p_a", "p_draw_final": "p_draw", "p_b_final": "p_b"}).copy()
    tmp = add_prediction_risk_columns(tmp, prob_cols=("p_a", "p_draw", "p_b"))
    j["prediction_entropy"] = tmp["prediction_entropy"]
    j["risk_band"] = tmp["risk_band"]

    cols = ["snapshot", "match_id", "matchday", "group", "team_a", "team_b", "forecast_source",
            "p_a_final", "p_draw_final", "p_b_final", "n_books",
            "p_a", "p_draw", "p_b", "p_a_market", "p_draw_market", "p_b_market",
            "edge_a", "edge_draw", "edge_b", "max_abs_edge", "risk_band"]
    j["snapshot"] = SNAP
    j[cols].to_csv(OUT / "forecast_2026_market_anchored.csv", index=False)

    pd.set_option("display.width", 220)

    def pct(df, c):
        return (df[c] * 100).round().astype(int)

    print("=== MODEL vs MARKET — biggest disagreements (|edge|) ===")
    big = j[j.has_market == 1].sort_values("max_abs_edge", ascending=False).head(10)
    t = big[["matchday", "team_a", "team_b"]].copy()
    t["model(a/d/b)"] = pct(big, "p_a").astype(str) + "/" + pct(big, "p_draw").astype(str) + "/" + pct(big, "p_b").astype(str)
    t["market(a/d/b)"] = pct(big, "p_a_market").astype(str) + "/" + pct(big, "p_draw_market").astype(str) + "/" + pct(big, "p_b_market").astype(str)
    t["max_edge"] = (big["max_abs_edge"] * 100).round().astype(int)
    print(t.to_string(index=False))

    # model's draw lean vs market (project theme)
    md = j[j.has_market == 1]
    print(f"\nmean model draw {md['p_draw'].mean():.3f} vs market draw {md['p_draw_market'].mean():.3f} "
          f"(model draw bias {md['edge_draw'].mean():+.3f})")
    print(f"mean |edge| {md['max_abs_edge'].mean():.3f}; model is under-confident on favorites "
          f"when market p>0.6: mean fav edge {md.loc[md.p_a_market>0.6,'edge_a'].mean():+.3f}")

    # advancement using market-primary probabilities
    common = ["match_id", "group", "team_a", "team_b", "goals_a", "goals_b", "tournament"]
    played = pd.read_csv(PROC / "research_modeling_table.csv")
    played = played[played["tournament"].astype(str).str.contains("2026")][common]
    up = pd.read_csv(PROC / "forecast_targets_2026.csv")[common]
    fixtures = pd.concat([played, up], ignore_index=True).reset_index(drop=True)
    # build aligned probs from j (market-primary where available, model-elo-blend otherwise).
    # Played fixtures use their goals in the simulator, so their probs are placeholders.
    fmap = j.set_index("match_id")[["p_a_final", "p_draw_final", "p_b_final"]].to_dict("index")
    probs = []
    for _, r in fixtures.iterrows():
        f = fmap.get(r["match_id"])
        probs.append([f["p_a_final"], f["p_draw_final"], f["p_b_final"]] if f else [1/3, 1/3, 1/3])
    probs = normalize_probs(np.array(probs))
    adv = simulate_group_stage(fixtures, probs, n_sims=20000, third_place_slots=8, seed=42)
    grpmap = (fixtures.set_index("team_a")["group"].to_dict() | fixtures.set_index("team_b")["group"].to_dict())
    adv["group"] = adv["team"].map(grpmap)
    adv = adv[["group", "team", "p_advance", "p_first", "p_second", "p_third_advance"]].sort_values(
        ["group", "p_advance"], ascending=[True, False])
    adv.to_csv(OUT / "advancement_2026_market.csv", index=False)
    print("\n=== ADVANCEMENT (market-anchored, 20k sims) — top of each group ===")
    print(adv.assign(p_advance=(adv.p_advance * 100).round().astype(int))
          .groupby("group").head(2).to_string(index=False))
    print("\nwrote:", OUT / "forecast_2026_market_anchored.csv", "and advancement_2026_market.csv")


if __name__ == "__main__":
    main()
