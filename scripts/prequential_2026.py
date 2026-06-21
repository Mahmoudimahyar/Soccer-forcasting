"""Prequential (walk-forward) out-of-sample scorecard on FINISHED 2026 group matches.

For each finished 2026 match in chronological order: train each model ONLY on group matches
that kicked off strictly before it (history + earlier 2026), predict, then score against the
actual result. This is the genuine live out-of-sample test from the protocol (section 4D) — no
information after kickoff is used. Models: accepted candidate (V8 Elo-blend), B1 Elo, B0 prior.
(Market is not scored here: we have no stored pre-match odds for already-finished matches.)

Output: outputs/research/prequential_2026.csv (per-match) + console summary.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.evaluation import metric_report, normalize_probs, rps_3way, log_loss_3way  # noqa: E402
from wcdrawlab.research.runner import leakage_safe_feature_frame, load_research_config, draw_calibration_error  # noqa: E402
from wcdrawlab.research.candidate import CandidateModel  # noqa: E402
from wcdrawlab.models.baselines import TernaryEloModel, HistoricalPriorModel  # noqa: E402

TABLE = ROOT / "data" / "processed" / "research_modeling_table.csv"
OUT = ROOT / "outputs" / "research" / "prequential_2026.csv"


def main():
    config, _ = load_research_config(ROOT / "configs" / "research.yaml")
    df = pd.read_csv(TABLE, parse_dates=["kickoff_utc"])
    df = df[df["stage"].str.lower() == "group"].sort_values("kickoff_utc").reset_index(drop=True)
    df["is2026"] = df["tournament"].astype(str).str.contains("2026")

    targets = df[df["is2026"] & df["goals_a"].notna() & df["goals_b"].notna()].copy()
    rows = []
    for _, m in targets.iterrows():
        train = df[df["kickoff_utc"] < m["kickoff_utc"]].copy()
        if len(train) < 100:
            continue
        Xtr = leakage_safe_feature_frame(train, config)
        Xte = leakage_safe_feature_frame(m.to_frame().T, config).reindex(columns=Xtr.columns, fill_value=0.0)
        cand = CandidateModel().fit(Xtr, train["outcome"]).predict_proba(Xte)[0]
        elo = TernaryEloModel(r=0.4).predict_proba(m.to_frame().T)[0]
        prior = HistoricalPriorModel().fit(train["outcome"]).predict_proba(1)[0]
        rows.append({
            "match_id": m["match_id"], "matchday": m["matchday"],
            "team_a": m["team_a"], "team_b": m["team_b"], "outcome": m["outcome"],
            "cand_a": cand[0], "cand_d": cand[1], "cand_b": cand[2],
            "elo_a": elo[0], "elo_d": elo[1], "elo_b": elo[2],
            "prior_a": prior[0], "prior_d": prior[1], "prior_b": prior[2],
        })
    res = pd.DataFrame(rows)
    res.to_csv(OUT, index=False)

    def score(prefix):
        P = normalize_probs(res[[f"{prefix}_a", f"{prefix}_d", f"{prefix}_b"]].to_numpy())
        y = res["outcome"]
        m = metric_report(y, P)
        m["draw_cal"] = draw_calibration_error(y, P[:, 1])
        pred = np.array(["A", "D", "B"])[P.argmax(1)]
        m["acc"] = float((pred == y.to_numpy()).mean())
        return m

    print(f"Prequential out-of-sample over {len(res)} FINISHED 2026 group matches "
          f"(MD: {res.groupby('matchday').size().to_dict()})\n")
    hdr = f"{'model':<14}{'RPS':>8}{'LogLoss':>9}{'drawBrier':>11}{'drawCal':>9}{'acc':>7}"
    print(hdr); print("-" * len(hdr))
    for name, pfx in [("candidate_V8", "cand"), ("B1_elo", "elo"), ("B0_prior", "prior")]:
        s = score(pfx)
        print(f"{name:<14}{s['rps']:>8.3f}{s['log_loss']:>9.3f}{s['draw_brier']:>11.3f}"
              f"{s['draw_cal']:>9.3f}{s['acc']:>7.2f}")
    # uniform reference
    n = len(res); uni = np.full((n, 3), 1/3)
    print(f"{'uniform_1/3':<14}{rps_3way(res['outcome'], uni):>8.3f}{log_loss_3way(res['outcome'], uni):>9.3f}"
          f"{'-':>11}{'-':>9}{'-':>7}")
    print(f"\nactual 2026 draw rate (finished): {(res['outcome']=='D').mean():.3f}  "
          f"| candidate mean p_draw: {res['cand_d'].mean():.3f}")
    print("wrote:", OUT)


if __name__ == "__main__":
    main()
