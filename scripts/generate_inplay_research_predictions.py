"""Generate out-of-fold full-envelope in-play predictions (RESEARCH-ONLY, leave-one-group-out).
Every row labeled research_only=True / not_runtime_approved. Writes a predictions CSV + failure stats.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.inplay_models.models import (  # noqa: E402
    M0_StaticB1, M1_TimeScore, M2_RemainingPoisson, M5_Ensemble, full_output_envelope)

OUT = ROOT / "outputs/research/inplay_2022_metrics"; OUT.mkdir(parents=True, exist_ok=True)
df = pd.read_parquet(ROOT / "data/processed/inplay_state_2022_group_stage.parquet").reset_index(drop=True)
groups = sorted(df.group.unique())
WLD = {"M0_static_b1": M0_StaticB1, "M1_time_score": M1_TimeScore,
       "M2_remaining_poisson": M2_RemainingPoisson, "M5_ensemble": M5_Ensemble}

frames = []
for k, M in WLD.items():
    oof = np.zeros((len(df), 3))
    for g in groups:
        tr, te = df[df.group != g], df[df.group == g]
        oof[te.index.to_numpy()] = M().fit(tr).predict_wld(te)
    env = full_output_envelope(df, oof, k)
    env.insert(0, "match_id", df.match_id.to_numpy()); env.insert(1, "decision_minute", df.decision_minute.to_numpy())
    env["not_runtime_approved"] = True; env["experimental"] = True
    frames.append(env)
allp = pd.concat(frames, ignore_index=True)
allp.to_csv(OUT / "research_predictions.csv", index=False)
print(f"wrote research_predictions.csv: {len(allp)} rows ({allp.model_id.nunique()} models x {len(df)} states), research_only=True")

# --- failure stats (on M2, the leader) for the failure-analysis report ---
Y = df.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy()
m2 = allp[allp.model_id == "M2_remaining_poisson"].reset_index(drop=True)
P = m2[["p_home_win", "p_draw", "p_away_win"]].to_numpy()
conf = P.max(1); pred = P.argmax(1)
wrong_conf = (pred != Y) & (conf > 0.7)
draw_rows = df.final_wld == "D"
draw_pdraw = P[draw_rows.to_numpy(), 1]
late = df.decision_minute >= 76
late_rps = (((np.cumsum(P, 1) - np.cumsum(np.eye(3)[Y], 1)) ** 2).sum(1) / 2.0)
print(f"overconfident-and-wrong rows (conf>0.7, wrong): {int(wrong_conf.sum())}/{len(df)}")
print(f"mean p(draw) on actual-draw rows: {float(draw_pdraw.mean()):.3f} (actual draws underweighted -> draw failure)")
print(f"late-game (>=76') mean RPS: {float(late_rps[late.to_numpy()].mean()):.3f} vs overall {float(late_rps.mean()):.3f}")
print(f"post-substitution rows mean RPS: {float(late_rps[(df.decision_type=='subst').to_numpy()].mean()):.3f}")
print(f"red-state rows (red_diff!=0): {int((df.red_diff!=0).sum())} (too few for inference)")
