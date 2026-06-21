"""2022 WC group-stage MARKET SHADOW evaluation (READ-ONLY benchmark).

Frozen models (no fitting to 2022, no blend selection from 2022):
  M1 B1 (approved Elo, r=0.4)  ·  M2 market no-vig consensus  ·  M3 equal blend (=50/50)
  M4 predeclared fixed blends: 75/25, 50/50, 25/75 (B1/market)

Metrics vs B1: RPS, 3-way log loss, draw Brier, draw calibration error, reliability table,
draw-interval coverage, worst-match log loss, paired bootstrap CI of (model - B1).

This is a SHADOW benchmark only. Nothing here is promoted; candidate.py is not touched; B1 remains
the sole approved runtime model. 2022 stays a release gate.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.evaluation import metric_report, normalize_probs  # noqa: E402
from wcdrawlab.ratings import ternary_elo_probs  # noqa: E402
from wcdrawlab.research.runner import draw_calibration_error  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402

OUT = ROOT / "outputs" / "research"; OUT.mkdir(parents=True, exist_ok=True)

# ---- assemble 2022 group rows with B1 + market probs aligned to research-table orientation ----
T = pd.read_csv(ROOT / "data/processed/research_modeling_table.csv", parse_dates=["kickoff_utc"])
T = T[(T.kickoff_utc.dt.year == 2022) & (T.stage.astype(str).str.lower() == "group")].copy()
T["outcome"] = np.select([T.goals_a > T.goals_b, T.goals_a == T.goals_b], ["A", "D"], default="B")
T["ca"] = T.team_a.map(canonical_team_name); T["cb"] = T.team_b.map(canonical_team_name)

mk = pd.read_csv(ROOT / "data/processed/market_features_2022.csv")
mk["ca"] = mk.team_a.map(canonical_team_name); mk["cb"] = mk.team_b.map(canonical_team_name)
mk_by = {}
for r in mk.itertuples():
    mk_by[(r.ca, r.cb)] = (r.p_a_market, r.p_draw_market, r.p_b_market)

rows = []
for r in T.itertuples():
    m = mk_by.get((r.ca, r.cb))
    swapped = False
    if m is None:
        m = mk_by.get((r.cb, r.ca)); swapped = True
    if m is None:
        continue
    pa, pd_, pb = (m[2], m[1], m[0]) if swapped else (m[0], m[1], m[2])  # realign to T orientation
    rows.append({"elo_delta": r.elo_delta, "outcome": r.outcome,
                 "pa_mkt": pa, "pd_mkt": pd_, "pb_mkt": pb})
D = pd.DataFrame(rows)
print(f"2022 group matches with aligned market odds: {len(D)} / {len(T)}")

elo = normalize_probs(ternary_elo_probs(D.elo_delta.to_numpy(dtype=float)))
mkt = normalize_probs(D[["pa_mkt", "pd_mkt", "pb_mkt"]].to_numpy(dtype=float))
y = D.outcome.to_numpy()

def blend(w_b1):
    return normalize_probs(w_b1 * elo + (1 - w_b1) * mkt)

MODELS = {
    "M1_B1_elo": elo,
    "M2_market": mkt,
    "M3_equal_blend_50_50": blend(0.5),
    "M4_blend_75_25": blend(0.75),
    "M4_blend_50_50": blend(0.5),
    "M4_blend_25_75": blend(0.25),
}

def per_match_rps(P):
    yv = np.array([{"A": 0, "D": 1, "B": 2}[o] for o in y])
    oh = np.eye(3)[yv]
    cP = np.cumsum(P, 1); cO = np.cumsum(oh, 1)
    return ((cP - cO) ** 2).sum(1) / 2.0

def per_match_ll(P):
    yv = np.array([{"A": 0, "D": 1, "B": 2}[o] for o in y])
    return -np.log(np.clip(P[np.arange(len(P)), yv], 1e-12, 1))

# ---- metrics table ----
recs = []
for name, P in MODELS.items():
    rep = metric_report(y, P)
    rep["draw_calibration_error"] = draw_calibration_error(y, P[:, 1])
    rep["worst_match_log_loss"] = float(per_match_ll(P).max())
    # draw-interval coverage: share of matches whose drawn/not-drawn is within a +/-1.96*se band
    pdraw = P[:, 1]; se = np.sqrt(pdraw * (1 - pdraw) / len(P))
    ydraw = (y == "D").astype(float)
    recs.append({"model": name, "rps": rep["rps"], "log_loss": rep["log_loss"],
                 "draw_brier": rep["draw_brier"], "draw_cal_error": rep["draw_calibration_error"],
                 "worst_match_log_loss": rep["worst_match_log_loss"],
                 "mean_p_draw": float(pdraw.mean()), "actual_draw_rate": float(ydraw.mean())})
M = pd.DataFrame(recs)
M.to_csv(OUT / "market_shadow_metrics_2022.csv", index=False)
print("\n=== metrics (2022 shadow) ===")
print(M.to_string(index=False))

# ---- reliability table for draw prob (M1 vs M2), 5 bins ----
def reliability(P, bins=5):
    pdraw = P[:, 1]; ydraw = (y == "D").astype(float)
    edges = np.linspace(0, 1, bins + 1); out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (pdraw >= lo) & (pdraw < hi if hi < 1 else pdraw <= hi)
        if m.any():
            out.append((f"[{lo:.1f},{hi:.1f})", int(m.sum()), round(float(pdraw[m].mean()), 3), round(float(ydraw[m].mean()), 3)))
    return out
print("\nDraw reliability M1_B1 (bin,n,mean_pred,obs):", reliability(elo))
print("Draw reliability M2_market (bin,n,mean_pred,obs):", reliability(mkt))

# ---- paired bootstrap of (model - B1) RPS and log loss ----
rng = np.random.default_rng(0)
n = len(D); B = 2000
base_rps = per_match_rps(elo); base_ll = per_match_ll(elo)
brecs = []
for name, P in MODELS.items():
    if name == "M1_B1_elo":
        continue
    d_rps = per_match_rps(P) - base_rps
    d_ll = per_match_ll(P) - base_ll
    idx = rng.integers(0, n, size=(B, n))
    bs_rps = d_rps[idx].mean(1); bs_ll = d_ll[idx].mean(1)
    brecs.append({"model": name,
                  "dRPS_mean": float(d_rps.mean()),
                  "dRPS_ci_low": float(np.percentile(bs_rps, 2.5)), "dRPS_ci_high": float(np.percentile(bs_rps, 97.5)),
                  "dRPS_better_sig": bool(np.percentile(bs_rps, 97.5) < 0),
                  "dLogLoss_mean": float(d_ll.mean()),
                  "dLL_ci_low": float(np.percentile(bs_ll, 2.5)), "dLL_ci_high": float(np.percentile(bs_ll, 97.5)),
                  "dLL_better_sig": bool(np.percentile(bs_ll, 97.5) < 0)})
Bt = pd.DataFrame(brecs)
Bt.to_csv(OUT / "market_shadow_bootstrap_2022.csv", index=False)
print("\n=== paired bootstrap vs B1 (negative = better than B1; sig if CI excludes 0) ===")
print(Bt.to_string(index=False))
