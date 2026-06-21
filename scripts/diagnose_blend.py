"""Scrutinize the Elo+market blend edge: is it a weight-fit artifact, and where does it come
from (deep World-Cup-grade markets vs thin Nations-League/qualifier markets)?

A FIXED blend weight needs no outcome fitting, so composite on the full sample is a fair
parameter-free comparison. We sweep the weight, then break the edge down by competition and by
bookmaker depth.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.evaluation import metric_report, normalize_probs  # noqa: E402
from wcdrawlab.research.runner import draw_calibration_error  # noqa: E402
from wcdrawlab.ratings import ternary_elo_probs  # noqa: E402

DATA = ROOT / "data" / "processed" / "intl_market_dataset.csv"
W = {"rps": 0.40, "log_loss": 0.25, "draw_brier": 0.20, "draw_calibration_error": 0.15}


def comp(y, P):
    P = normalize_probs(P)
    m = metric_report(y, P)
    m["draw_calibration_error"] = draw_calibration_error(y, P[:, 1])
    return float(sum(W[k] * m[k] for k in W)), m["rps"], m["log_loss"]


def main():
    df = pd.read_csv(DATA, parse_dates=["kickoff_utc"])
    df = df[df["n_books"] >= 3].reset_index(drop=True)
    y = df["outcome"]
    Pm = normalize_probs(df[["p_a_market", "p_draw_market", "p_b_market"]].to_numpy())
    Pe = ternary_elo_probs(df["elo_delta"].to_numpy())

    print(f"n={len(df)} | median n_books={int(df['n_books'].median())}")
    print("\n--- fixed-weight blend sweep (parameter-free; full sample) ---")
    print(f"{'w_elo':>6}{'composite':>11}{'RPS':>9}{'LogLoss':>9}")
    base = None
    for w in [0.0, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5]:
        c, r, ll = comp(y, (1 - w) * Pm + w * Pe)
        if w == 0:
            base = c
        tag = "" if w == 0 else f"  ({(base-c)/base*100:+.2f}%)"
        print(f"{w:>6.2f}{c:>11.4f}{r:>9.4f}{ll:>9.4f}{tag}")

    w = 0.3  # representative
    Pb = (1 - w) * Pm + w * Pe
    print(f"\n--- edge by competition at w_elo={w} (composite: market -> blend) ---")
    print(f"{'sport':<46}{'n':>4}{'mkt':>9}{'blend':>9}{'delta%':>8}{'books':>7}")
    for sp, g in df.groupby("sport"):
        idx = g.index
        cm, _, _ = comp(g["outcome"], Pm[idx])
        cb, _, _ = comp(g["outcome"], Pb[idx])
        print(f"{sp:<46}{len(g):>4}{cm:>9.4f}{cb:>9.4f}{(cm-cb)/cm*100:>7.1f}%{int(g['n_books'].median()):>7}")

    print(f"\n--- edge by bookmaker depth (n_books buckets) at w_elo={w} ---")
    df2 = df.assign(bucket=pd.cut(df["n_books"], [0, 8, 14, 100], labels=["thin(<=8)", "med(9-14)", "deep(15+)"]))
    for b, g in df2.groupby("bucket", observed=True):
        idx = g.index
        cm, _, _ = comp(g["outcome"], Pm[idx])
        cb, _, _ = comp(g["outcome"], Pb[idx])
        print(f"  {str(b):<12} n={len(g):>3}  market {cm:.4f} -> blend {cb:.4f}  ({(cm-cb)/cm*100:+.1f}%)")

    # World Cup-only (deepest, most relevant to 2026)
    wc = df[df["sport"] == "soccer_fifa_world_cup"]
    if len(wc):
        idx = wc.index
        cm, rm, _ = comp(wc["outcome"], Pm[idx])
        cb, rb, _ = comp(wc["outcome"], Pb[idx])
        print(f"\n--- WORLD CUP 2022 only (n={len(wc)}, the deep-market case) ---")
        print(f"  market composite {cm:.4f} (RPS {rm:.4f}) -> blend {cb:.4f} (RPS {rb:.4f})  ({(cm-cb)/cm*100:+.1f}%)")


if __name__ == "__main__":
    main()
