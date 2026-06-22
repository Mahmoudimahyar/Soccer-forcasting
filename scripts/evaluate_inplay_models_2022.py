"""Leave-one-group-out evaluation of in-play baselines on the 2022 state dataset (research-only).
Match-level bootstrap; time/score/event breakdowns. Writes outputs/research/inplay_2022_metrics/.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.inplay_models.models import (  # noqa: E402
    M0_StaticB1, M1_TimeScore, M2_RemainingPoisson, M5_Ensemble, M3_GoalHazard, M4_CompetingRisk)

OUT = ROOT / "outputs/research/inplay_2022_metrics"; OUT.mkdir(parents=True, exist_ok=True)
df = pd.read_parquet(ROOT / "data/processed/inplay_state_2022_group_stage.parquet").reset_index(drop=True)
groups = sorted(df.group.unique())
Y = df.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy()
oh = np.eye(3)[Y]

def per_row_rps(P):
    return ((np.cumsum(P, 1) - np.cumsum(oh, 1)) ** 2).sum(1) / 2.0
def per_row_ll(P):
    return -np.log(np.clip(P[np.arange(len(P)), Y], 1e-12, 1))

WLD = {"M0_static_b1": M0_StaticB1, "M1_time_score": M1_TimeScore,
       "M2_remaining_poisson": M2_RemainingPoisson, "M5_ensemble": M5_Ensemble}

# --- LOGO out-of-fold W/D/L predictions ---
oof = {k: np.zeros((len(df), 3)) for k in WLD}
for g in groups:
    tr, te = df[df.group != g], df[df.group == g]
    for k, M in WLD.items():
        oof[k][te.index.to_numpy()] = M().fit(tr).predict_wld(te)

rows = []
for k, P in oof.items():
    draw = P[:, 1]; ydraw = (Y == 1).astype(float)
    rows.append({"model": k, "rps": float(per_row_rps(P).mean()), "log_loss": float(per_row_ll(P).mean()),
                 "draw_brier": float(((draw - ydraw) ** 2).mean()),
                 "mean_entropy": float((-(P * np.log(np.clip(P, 1e-12, 1)))).sum(1).mean() / np.log(3))})
metrics = pd.DataFrame(rows); metrics.to_csv(OUT / "wld_metrics.csv", index=False)
print("=== W/D/L LOGO metrics ==="); print(metrics.to_string(index=False))

# --- match-level paired bootstrap vs M1 ---
rng = np.random.default_rng(0); matches = df.match_id.to_numpy(); uniq = np.unique(matches)
base = per_row_rps(oof["M1_time_score"])
def match_mean(v): return pd.Series(v).groupby(matches).mean()
bt = []
for k, P in oof.items():
    if k == "M1_time_score":
        continue
    d = match_mean(per_row_rps(P) - base)  # per-match delta vs M1
    idx = rng.integers(0, len(uniq), size=(2000, len(uniq)))
    bs = d.to_numpy()[idx].mean(1)
    bt.append({"model": k, "dRPS_vs_M1_mean": float(d.mean()),
               "ci_low": float(np.percentile(bs, 2.5)), "ci_high": float(np.percentile(bs, 97.5)),
               "better_than_M1_sig": bool(np.percentile(bs, 97.5) < 0),
               "worse_than_M1_sig": bool(np.percentile(bs, 2.5) > 0)})
boot = pd.DataFrame(bt); boot.to_csv(OUT / "wld_bootstrap_vs_M1.csv", index=False)
print("\n=== match-level bootstrap vs M1 (neg=better) ==="); print(boot.to_string(index=False))

# --- breakdowns (mean RPS by bucket) for each model ---
df["_bucket"] = pd.cut(df.decision_minute, [-1, 15, 30, 45, 60, 75, 200],
                       labels=["0-15", "16-30", "31-45", "46-60", "61-75", "76-90+"])
df["_state"] = np.where(df.score_diff == 0, "level", np.where(df.score_diff.abs() == 1, "1-goal", "2+goal"))
brk = []
for k, P in oof.items():
    r = per_row_rps(P)
    for col in ["_bucket", "_state", "decision_type"]:
        for val, sub in df.groupby(col, observed=True):
            brk.append({"model": k, "dimension": col, "value": str(val), "n": len(sub),
                        "mean_rps": float(r[sub.index.to_numpy()].mean())})
pd.DataFrame(brk).to_csv(OUT / "wld_breakdowns.csv", index=False)

# --- next-event models (LOGO) ---
def logo_binary(model_cls, target):
    pred = np.zeros(len(df))
    for g in groups:
        tr, te = df[df.group != g], df[df.group == g]
        pred[te.index.to_numpy()] = model_cls().fit(tr).predict_proba(te)
    y = df[target].astype(int).to_numpy()
    base_rate = y.mean()
    brier = float(((pred - y) ** 2).mean()); ll = float(-(y*np.log(np.clip(pred,1e-12,1))+(1-y)*np.log(np.clip(1-pred,1e-12,1))).mean())
    brier_base = float(((base_rate - y) ** 2).mean())
    return {"target": target, "n_pos": int(y.sum()), "base_rate": round(base_rate,4),
            "brier": round(brier,4), "brier_baserate": round(brier_base,4),
            "log_loss": round(ll,4), "beats_baserate": brier < brier_base}

m3 = logo_binary(M3_GoalHazard, "goal_within_5")
# M4 competing-risk: log loss vs base-rate on next_goal_team
y4 = df.next_goal_team.map({"home":0,"away":1,"none":2}).to_numpy(); oh4 = np.eye(3)[y4]
pred4 = np.zeros((len(df),3))
for g in groups:
    tr, te = df[df.group != g], df[df.group == g]
    pred4[te.index.to_numpy()] = M4_CompetingRisk().fit(tr).predict_proba(te)
base4 = np.tile(np.bincount(y4, minlength=3)/len(y4), (len(df),1))
m4 = {"target":"next_goal_team","model_log_loss":round(float(-np.log(np.clip(pred4[np.arange(len(df)),y4],1e-12,1)).mean()),4),
      "baserate_log_loss":round(float(-np.log(np.clip(base4[np.arange(len(df)),y4],1e-12,1)).mean()),4)}
m4["beats_baserate"] = m4["model_log_loss"] < m4["baserate_log_loss"]
pd.DataFrame([m3, m4]).to_csv(OUT / "next_event_metrics.csv", index=False)
print("\n=== next-event (LOGO) ==="); print(m3); print(m4)
print("\nwrote metrics to", OUT)
