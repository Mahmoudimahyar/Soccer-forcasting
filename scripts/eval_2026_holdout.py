"""Decisive OUT-OF-SAMPLE test: fit in-play models on the 5 pre-2026 competitions and predict the LIVE
2026 World Cup (never used in fitting; transparent models aren't fit at all). Reports RPS + match-level
paired bootstraps for the comparisons that matter, plus draw calibration on 2026.

Governance: 2026 is HELD OUT, never tuned to; paper-only; no model is promoted here.
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
    M6_MarketInplay, M2fit_FittedPoisson, TemperatureScaled)
from wcdrawlab.research import inplay_eval as E  # noqa: E402

MODELS = {"M0_static_b1": M0_StaticB1, "M1_time_score": M1_TimeScore,
          "M2_remaining_poisson": M2_RemainingPoisson, "M6_market_inplay": M6_MarketInplay,
          "M2cal_calibrated_poisson": M2cal_CalibratedPoisson, "M5_ensemble": M5_Ensemble,
          "M2fit_poisson": M2fit_FittedPoisson,
          "M2temp": lambda: TemperatureScaled(M2_RemainingPoisson),
          "M2fit_temp": lambda: TemperatureScaled(M2fit_FittedPoisson)}

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
HELD = "2026_WORLDCUP"
assert HELD in set(df.competition), "build inplay_state_2026_worldcup first"

tr, te = df[df.competition != HELD], df[df.competition == HELD].reset_index(drop=True)
Yte = te.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy()
print(f"train: {tr.competition.nunique()} comps / {tr.match_id.nunique()} matches | "
      f"HELD-OUT 2026: {te.match_id.nunique()} matches / {len(te)} rows")

fitted = M2fit_FittedPoisson().fit(tr)
print(f"M2fit learned mapping on train: base={fitted.base_:.3f} k={fitted.k_:.3f} (default base=1.350 k=0.200)")

P = {}
for k, M in MODELS.items():
    P[k] = M().fit(tr).predict_wld(te)
rps = {k: E.rps_per_row(P[k], Yte) for k in MODELS}

print("\n=== 2026 out-of-sample RPS (lower=better) ===")
for k in sorted(MODELS, key=lambda x: rps[x].mean()):
    print(f"  {k:<26} {rps[k].mean():.4f}")

mid = te.match_id.to_numpy()
def boot(a, b):  # a vs b, neg => a better
    r = E.paired_match_bootstrap(rps[a], rps[b], mid)
    return f"dRPS {r['delta_mean']:+.4f} CI[{r['ci_low']:+.4f},{r['ci_high']:+.4f}] " \
           f"{'A BETTER*' if r['a_better_sig'] else ('A WORSE*' if r['a_worse_sig'] else 'ns')}"

print("\n=== match-level bootstraps on 2026 (n={} matches) ===".format(te.match_id.nunique()))
print(f"  in-play vs STATIC : M1 vs M0            -> {boot('M1_time_score','M0_static_b1')}")
print(f"  best vs static    : M5 vs M0            -> {boot('M5_ensemble','M0_static_b1')}")
print(f"  ensemble vs base  : M5 vs M1            -> {boot('M5_ensemble','M1_time_score')}")
print(f"  recal vs base     : M2cal vs M1         -> {boot('M2cal_calibrated_poisson','M1_time_score')}")
print(f"  transparent vs base: M2 vs M1           -> {boot('M2_remaining_poisson','M1_time_score')}")
print(f"  fitted vs hand-set : M2fit vs M2          -> {boot('M2fit_poisson','M2_remaining_poisson')}")
print(f"  fitted+temp vs temp: M2fit_temp vs M2temp -> {boot('M2fit_temp','M2temp')}")

print("\n=== draw calibration on 2026 (slope~1, intercept~0 ideal; ECE) ===")
for k in ["M1_time_score", "M2_remaining_poisson", "M2cal_calibrated_poisson", "M5_ensemble"]:
    s, ic = E.calibration_slope_intercept(P[k][:, 1], (Yte == 1).astype(int))
    print(f"  {k:<26} slope={s:.3f} intercept={ic:+.3f} ECE={E.ece(P[k][:,1],(Yte==1).astype(int)):.4f}")
