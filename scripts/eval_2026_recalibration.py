"""Calibration improvement: cross-fitted TEMPERATURE SCALING of in-play probabilities.

All in-play models are draw-overconfident out-of-sample (see inplay_2026_holdout.md). Temperature
scaling adds ONE parameter T: p' = softmax(log(p)/T), fit by minimizing log-loss. T>1 tempers
overconfidence. It is leakage-safe and barely able to overfit (1 dof).

Protocol (no leakage, never tuned to 2026):
  1. base model fit on the 5 pre-2026 competitions
  2. T fit ONLY on training competitions, via leave-one-competition-out OOF preds within train
  3. apply base(fit on all train) + T to the held-out 2026 World Cup; compare calibration + RPS
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.inplay_models.models import (  # noqa: E402
    M1_TimeScore, M2_RemainingPoisson, M5_Ensemble)
from wcdrawlab.research import inplay_eval as E  # noqa: E402

HELD = "2026_WORLDCUP"
BASES = {"M1_time_score": M1_TimeScore, "M2_remaining_poisson": M2_RemainingPoisson,
         "M5_ensemble": M5_Ensemble}


def temperature(p, T):
    z = np.log(np.clip(p, 1e-9, 1.0)) / T
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_T(p, y):
    """1-D search for T minimizing log-loss."""
    grid = np.linspace(0.5, 3.0, 51)
    best, bT = 1e18, 1.0
    for T in grid:
        ll = E.logloss_per_row(temperature(p, T), y).mean()
        if ll < best:
            best, bT = ll, T
    return bT


def load():
    files = {"WC2022": ROOT / "data/processed/inplay_state_2022_group_stage.parquet"}
    for p in glob.glob(str(ROOT / "data/processed/inplay_state_*.parquet")):
        if "2022_group_stage" in p:
            continue
        files[Path(p).stem.replace("inplay_state_", "").upper()] = Path(p)
    frames = []
    for comp, p in files.items():
        if Path(p).exists():
            d = pd.read_parquet(p); d["competition"] = comp; frames.append(d)
    return pd.concat(frames, ignore_index=True)


def main():
    df = load()
    tr, te = df[df.competition != HELD], df[df.competition == HELD].reset_index(drop=True)
    Yte = te.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy()
    tr_comps = sorted(tr.competition.unique())
    print(f"train {len(tr_comps)} comps / {tr.match_id.nunique()} matches | held-out 2026: "
          f"{te.match_id.nunique()} matches / {len(te)} rows\n")

    rows = []
    for name, M in BASES.items():
        # OOF predictions within TRAIN to fit T (no leakage to 2026)
        oof = np.zeros((len(tr), 3)); tri = tr.reset_index(drop=True)
        for held in tr_comps:
            a, b = tri[tri.competition != held], tri[tri.competition == held]
            oof[b.index.to_numpy()] = M().fit(a).predict_wld(b)
        Ytr = tri.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy()
        T = fit_T(oof, Ytr)
        # base fit on ALL train, predict 2026, with and without T
        base = M().fit(tr).predict_wld(te)
        cal = temperature(base, T)
        for tag, P in [(name, base), (f"{name}+temp(T={T:.2f})", cal)]:
            s, ic = E.calibration_slope_intercept(P[:, 1], (Yte == 1).astype(int))
            rows.append({"model": tag, "rps_2026": float(E.rps_per_row(P, Yte).mean()),
                         "draw_ece": float(E.ece(P[:, 1], (Yte == 1).astype(int))),
                         "draw_slope": round(s, 3), "draw_intercept": round(ic, 3)})
        bs = E.paired_match_bootstrap(E.rps_per_row(cal, Yte), E.rps_per_row(base, Yte), te.match_id.to_numpy())
        print(f"{name}: T={T:.2f} | RPS {E.rps_per_row(base,Yte).mean():.4f}->{E.rps_per_row(cal,Yte).mean():.4f} "
              f"| draw ECE {E.ece(base[:,1],(Yte==1).astype(int)):.4f}->{E.ece(cal[:,1],(Yte==1).astype(int)):.4f} "
              f"| dRPS CI[{bs['ci_low']:+.4f},{bs['ci_high']:+.4f}]")
    out = ROOT / "outputs/research/inplay_multicomp/recalibration_2026.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print("\n=== full table ===")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nwrote", out)


if __name__ == "__main__":
    main()
