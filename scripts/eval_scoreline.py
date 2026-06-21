"""Ablation: scoreline 1X2 (Poisson, Dixon-Coles) on DEV folds (2010/2014/2018) vs V8/B1.
Manual fold split (the frozen runner can't supply goals, which the scoreline model needs at fit).
Same objective J + draw_calibration_error as the frozen evaluator. Selection on dev only.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.evaluation import metric_report  # noqa: E402
from wcdrawlab.research.runner import draw_calibration_error, composite_score  # noqa: E402
from wcdrawlab.research.scoreline import ScorelineModel  # noqa: E402

W = {"rps": 0.40, "log_loss": 0.25, "draw_brier": 0.20, "draw_calibration_error": 0.15}
T = pd.read_csv("data/processed/research_modeling_table.csv", parse_dates=["kickoff_utc"])
T["yr"] = T["kickoff_utc"].dt.year
T["stage_l"] = T.get("stage", "group").astype(str).str.lower()
T["outcome"] = np.select([T.goals_a > T.goals_b, T.goals_a == T.goals_b], ["A", "D"], default="B")
g = T[(T.stage_l == "group") & T.goals_a.notna() & T.goals_b.notna()].copy()

for mode in ["poisson", "dixon_coles"]:
    print(f"\n=== scoreline mode={mode} ===")
    comps = []
    for yr in [2010, 2014, 2018]:
        tr = g[g.yr < yr]; te = g[g.yr == yr]
        m = ScorelineModel(mode=mode).fit(tr.elo_delta, tr.goals_a, tr.goals_b)
        P = m.predict_proba(te[["elo_delta"]])
        rep = metric_report(te.outcome, P)
        rep["draw_calibration_error"] = draw_calibration_error(te.outcome, P[:, 1])
        J = composite_score(rep, W); comps.append(J)
        print(f"  dev_{yr}: rps={rep['rps']:.4f} ll={rep['log_loss']:.4f} dBrier={rep['draw_brier']:.4f} "
              f"dECE={rep['draw_calibration_error']:.4f} J={J:.4f}  (mu={m.mu:.3f} beta={m.beta:.3f} rho={m.rho:.3f})")
    print(f"  >>> dev mean J = {np.mean(comps):.4f}   (V8=0.3541, B1=0.3553)")

# sample scoreline outputs for one fixture (capability demo)
m = ScorelineModel(mode="dixon_coles").fit(g[g.yr < 2018].elo_delta, g[g.yr < 2018].goals_a, g[g.yr < 2018].goals_b)
o = m.outputs_for(120.0)
print("\nSample scoreline outputs (elo_delta=+120, DC):")
print(f"  xG: A={o.expected_goals_a:.2f} B={o.expected_goals_b:.2f} | 1X2={o.p_a_win:.3f}/{o.p_draw:.3f}/{o.p_b_win:.3f}")
print(f"  P(0-0)={o.p_00:.3f} P(1-1)={o.p_11:.3f} P(2-2)={o.p_22:.3f} | U1.5={o.p_under_15:.3f} U2.5={o.p_under_25:.3f} "
      f"BTTS_No={o.p_btts_no:.3f} | draw95CI=[{o.p_draw_ci_low:.3f},{o.p_draw_ci_high:.3f}]")
