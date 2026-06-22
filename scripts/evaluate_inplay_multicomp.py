"""Multi-competition leave-one-COMPETITION-out evaluation of in-play baselines (research-only).
Combines all available inplay_state_<comp>.parquet products and evaluates M0/M1/M2/M5 W/D/L with
true cross-competition holdouts + match-level bootstrap. This is the SHADOW-CANDIDATE bar test.
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.inplay_models.models import (  # noqa: E402
    M0_StaticB1, M1_TimeScore, M2_RemainingPoisson, M5_Ensemble, M2cal_CalibratedPoisson,
    M6_MarketInplay, TemperatureScaled)
from wcdrawlab.research import inplay_eval as E  # noqa: E402

OUT = ROOT / "outputs/research/inplay_multicomp"; OUT.mkdir(parents=True, exist_ok=True)

# load all competition state products
files = {"WC2022": ROOT / "data/processed/inplay_state_2022_group_stage.parquet"}
for p in glob.glob(str(ROOT / "data/processed/inplay_state_*.parquet")):
    name = Path(p).stem.replace("inplay_state_", "")
    if "2022_group_stage" in p:
        continue
    files[name.upper()] = Path(p)

frames = []
for comp, p in files.items():
    if Path(p).exists():
        d = pd.read_parquet(p); d["competition"] = comp; frames.append(d)
df = pd.concat(frames, ignore_index=True)
comps = sorted(df.competition.unique())
print(f"competitions: {comps} | rows: {len(df)} | matches: {df.match_id.nunique()}")
if len(comps) < 2:
    print("only one competition available -> cross-competition holdout NOT yet possible (need >=2)."); sys.exit(0)

WLD = {"M0_static_b1": M0_StaticB1, "M1_time_score": M1_TimeScore,
       "M2_remaining_poisson": M2_RemainingPoisson, "M6_market_inplay": M6_MarketInplay,
       "M5_ensemble": M5_Ensemble, "M2cal_calibrated_poisson": M2cal_CalibratedPoisson,
       "M5temp_ensemble": lambda: TemperatureScaled(M5_Ensemble),
       "M2temp_poisson": lambda: TemperatureScaled(M2_RemainingPoisson)}
Y = df.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy()

# leave-one-COMPETITION-out OOF predictions
oof = {k: np.zeros((len(df), 3)) for k in WLD}
for held in comps:
    tr, te = df[df.competition != held], df[df.competition == held]
    for k, M in WLD.items():
        oof[k][te.index.to_numpy()] = M().fit(tr).predict_wld(te)

rows = []
for k, P in oof.items():
    rows.append({"model": k, "rps": float(E.rps_per_row(P, Y).mean()),
                 "log_loss": float(E.logloss_per_row(P, Y).mean()), "draw_brier": E.draw_brier(P, Y)})
metrics = pd.DataFrame(rows); metrics.to_csv(OUT / "logo_competition_metrics.csv", index=False)
print("\n=== leave-one-competition-out W/D/L ==="); print(metrics.to_string(index=False))

# calibration slope/intercept for the Poisson vs its recalibrated variant
print("\n=== draw calibration (slope/intercept, ideal 1/0; ECE) ===")
for k in ["M2_remaining_poisson", "M2temp_poisson", "M5_ensemble", "M5temp_ensemble", "M2cal_calibrated_poisson"]:
    if k not in oof:
        continue
    s, ic = E.calibration_slope_intercept(oof[k][:, 1], (Y == 1).astype(int))
    print(f"  {k:<24}: slope={s:.3f} intercept={ic:+.3f} ECE={E.ece(oof[k][:, 1], (Y==1).astype(int)):.4f}")

# per-competition (held-out) breakdown
per = []
for held in comps:
    m = (df.competition == held).to_numpy()
    for k, P in oof.items():
        per.append({"held_out": held, "model": k, "n": int(m.sum()),
                    "rps": float(E.rps_per_row(P[m], Y[m]).mean())})
pd.DataFrame(per).to_csv(OUT / "logo_competition_per_comp.csv", index=False)

# match-level paired bootstrap vs M1 (each model), pooled across competitions
base = E.rps_per_row(oof["M1_time_score"], Y)
bt = []
for k, P in oof.items():
    if k == "M1_time_score":
        continue
    r = E.paired_match_bootstrap(E.rps_per_row(P, Y), base, df.match_id.to_numpy())
    bt.append({"model": k, **r})
boot = pd.DataFrame(bt); boot.to_csv(OUT / "logo_competition_bootstrap_vs_M1.csv", index=False)
print("\n=== match-level bootstrap vs M1 (neg=better) ==="); print(boot.to_string(index=False))

# KEY QUESTION: does market-anchored in-play (M6) beat Elo-anchored in-play (M2)?
if "M6_market_inplay" in oof:
    cmp = E.paired_match_bootstrap(E.rps_per_row(oof["M6_market_inplay"], Y),
                                   E.rps_per_row(oof["M2_remaining_poisson"], Y), df.match_id.to_numpy())
    print("\n=== M6 (market-anchored) vs M2 (Elo-anchored) in-play, RPS (neg=M6 better) ===")
    print(f"  dRPS_mean={cmp['delta_mean']:.4f} CI=[{cmp['ci_low']:.4f},{cmp['ci_high']:.4f}] "
          f"M6_better_sig={cmp['a_better_sig']} M6_worse_sig={cmp['a_worse_sig']}")

# does any model beat M1 on EACH held-out competition (the >=2-holdout SHADOW bar)?
print("\n=== SHADOW-CANDIDATE check: beats M1 on every held-out competition? ===")
pc = pd.DataFrame(per).pivot_table(index="model", columns="held_out", values="rps")
m1 = pc.loc["M1_time_score"]
for k in pc.index:
    if k in ("M0_static_b1", "M1_time_score"):
        continue
    beats = (pc.loc[k] < m1)
    print(f"  {k}: beats M1 on {int(beats.sum())}/{len(comps)} competitions -> "
          f"{'PASS(>=2)' if beats.all() and len(comps)>=2 else 'not yet'}")
print("\nwrote", OUT)
