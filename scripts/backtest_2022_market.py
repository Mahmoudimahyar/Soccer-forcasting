"""Backtest on the 2022 World Cup group stage (48 matches) WITH real pre-kickoff market odds.

The market consensus is now backtestable for one fold. Questions answered:
  1) How does the no-vig market (B6) compare to Elo (B1) and the accepted candidate (V8)?
  2) Does blending the model with the market beat the market alone (i.e., does the model add
     anything to the market)?

Training for the learned models uses only data before 2022 (same as the fixed 2022 fold).
Market is a pre-kickoff snapshot ~90 min before each match (no post-kickoff info).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.evaluation import metric_report, normalize_probs  # noqa: E402
from wcdrawlab.research.runner import leakage_safe_feature_frame, load_research_config, draw_calibration_error  # noqa: E402
from wcdrawlab.research.candidate import CandidateModel  # noqa: E402
from wcdrawlab.models.baselines import TernaryEloModel, HistoricalPriorModel  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402

PROC = ROOT / "data" / "processed"
WEIGHTS = {"rps": 0.40, "log_loss": 0.25, "draw_brier": 0.20, "draw_calibration_error": 0.15}


def canon(n):
    return canonical_team_name(n)


def comp(m):
    return float(sum(WEIGHTS[k] * m[k] for k in WEIGHTS))


def scoreset(y, P, name):
    P = normalize_probs(P)
    m = metric_report(y, P)
    m["draw_calibration_error"] = draw_calibration_error(y, P[:, 1])
    m["composite"] = comp(m)
    pred = np.array(["A", "D", "B"])[P.argmax(1)]
    m["acc"] = float((pred == y.to_numpy()).mean())
    m["model"] = name
    return m


def main():
    config, _ = load_research_config(ROOT / "configs" / "research.yaml")
    df = pd.read_csv(PROC / "research_modeling_table.csv", parse_dates=["kickoff_utc"])
    df["year"] = df["kickoff_utc"].dt.year
    mkt = pd.read_csv(PROC / "market_features_2022.csv")
    mkt["pair"] = [frozenset((canon(a), canon(b))) for a, b in zip(mkt["team_a"], mkt["team_b"])]
    mkt_map = {r["pair"]: r for _, r in mkt.iterrows()}

    test = df[(df["year"] == 2022) & (df["stage"].str.lower() == "group")].copy()
    train = df[(df["year"] < 2022) & (df["stage"].str.lower() == "group")].copy()

    # align market to each test row's orientation
    P_mkt = np.full((len(test), 3), np.nan)
    for i, (_, r) in enumerate(test.iterrows()):
        m = mkt_map.get(frozenset((r["team_a"], r["team_b"])))
        if m is None:
            continue
        if m["team_a"] == r["team_a"]:
            P_mkt[i] = [m["p_a_market"], m["p_draw_market"], m["p_b_market"]]
        else:
            P_mkt[i] = [m["p_b_market"], m["p_draw_market"], m["p_a_market"]]
    matched = ~np.isnan(P_mkt[:, 0])
    print(f"2022 test matches: {len(test)} | matched to market: {int(matched.sum())}")
    test = test[matched].copy(); P_mkt = normalize_probs(P_mkt[matched])
    y = test["outcome"]

    # models
    Xtr = leakage_safe_feature_frame(train, config)
    Xte = leakage_safe_feature_frame(test, config).reindex(columns=Xtr.columns, fill_value=0.0)
    P_cand = CandidateModel().fit(Xtr, train["outcome"]).predict_proba(Xte)
    P_elo = TernaryEloModel(r=0.4).predict_proba(test)
    P_prior = HistoricalPriorModel().fit(train["outcome"]).predict_proba(len(test))
    P_blend = normalize_probs(0.5 * P_cand + 0.5 * P_mkt)
    P_blend_elo = normalize_probs(0.5 * P_elo + 0.5 * P_mkt)
    P_mkt_elo_70 = normalize_probs(0.7 * P_mkt + 0.3 * P_elo)

    rows = [
        scoreset(y, P_mkt, "B6_market_consensus"),
        scoreset(y, P_cand, "V8_candidate"),
        scoreset(y, P_elo, "B1_elo"),
        scoreset(y, P_prior, "B0_prior"),
        scoreset(y, P_blend, "blend_50_candidate_market"),
        scoreset(y, P_blend_elo, "blend_50_elo_market"),
        scoreset(y, P_mkt_elo_70, "blend_70market_30elo"),
    ]
    out = pd.DataFrame(rows)[["model", "rps", "log_loss", "draw_brier",
                              "draw_calibration_error", "composite", "acc"]].sort_values("composite")
    out.to_csv(ROOT / "outputs" / "research" / "backtest_2022_market.csv", index=False)
    pd.set_option("display.width", 160)
    print("\n=== 2022 WC GROUP STAGE — WITH REAL MARKET (lower better; sorted by composite) ===")
    print(out.round(4).to_string(index=False))

    mk = out[out.model == "B6_market_consensus"].iloc[0]
    print(f"\nMarket composite: {mk['composite']:.4f}  RPS: {mk['rps']:.4f}  LogLoss: {mk['log_loss']:.4f}")
    beats = out[out["composite"] < mk["composite"]]
    if len(beats):
        print("Models beating the market on composite:", list(beats[beats.model != 'B6_market_consensus']['model']))
    else:
        print("NOTHING beats the no-vig market on composite — market is the benchmark, as expected.")


if __name__ == "__main__":
    main()
