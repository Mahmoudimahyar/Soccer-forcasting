"""TRUE-ALPHA test: does the Elo blend still beat the market when the market is SHARP
(closing line, and Pinnacle specifically) — or was the +5% just denoising a soft T-90 consensus?

For each market benchmark M in {T-90 consensus, closing consensus, Pinnacle close}, expanding-
window temporal CV comparing M vs blend(M + Elo) (weight fit on train). If the blend's edge
survives against Pinnacle-close, that is evidence of real alpha beyond denoising.
Also reports each market source's own OOS accuracy (which is sharpest).
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

DATA = ROOT / "data" / "processed" / "intl_market_sharp.csv"
W = {"rps": 0.40, "log_loss": 0.25, "draw_brier": 0.20, "draw_calibration_error": 0.15}

SOURCES = {
    "T90_consensus":  ["p_a_market", "p_draw_market", "p_b_market"],
    "close_consensus": ["cons_a", "cons_d", "cons_b"],
    "pinnacle_close":  ["pin_a", "pin_d", "pin_b"],
}


def comp(y, P):
    P = normalize_probs(P)
    m = metric_report(y, P)
    m["draw_calibration_error"] = draw_calibration_error(y, P[:, 1])
    return float(sum(W[k] * m[k] for k in W))


def rps_only(y, P):
    return metric_report(y, normalize_probs(P))["rps"]


def best_w(y, M, E):
    return min(np.linspace(0, 0.6, 25), key=lambda w: comp(y, (1 - w) * M + w * E))


def main():
    df = pd.read_csv(DATA, parse_dates=["kickoff_utc"]).sort_values("kickoff_utc").reset_index(drop=True)
    # require Pinnacle present for a fair like-for-like comparison across sources
    df = df[(df["has_pinnacle"] == 1) & (df["n_books_close"] >= 3)].reset_index(drop=True)
    n = len(df)
    print(f"matches (Pinnacle present, books>=3): {n} | {df['kickoff_utc'].min().date()} -> {df['kickoff_utc'].max().date()}")

    bins = np.array_split(np.arange(n), 5)

    # 1) which market source is sharpest (own OOS RPS, pooled over test folds)?
    print("\n--- market source sharpness (pooled OOS, lower RPS = sharper) ---")
    for name, cols in SOURCES.items():
        P_te, y_te = [], []
        for i in range(1, 5):
            te = df.iloc[bins[i]]
            P_te.append(normalize_probs(te[cols].to_numpy())); y_te.append(te["outcome"])
        P = np.vstack(P_te); y = pd.concat(y_te)
        print(f"  {name:<16} RPS {rps_only(y, P):.4f}  composite {comp(y, P):.4f}")

    # 2) does Elo blend beat each (sharper) market source, OOS?
    print("\n--- Elo blend vs each market (expanding-window CV, 4 folds) ---")
    for name, cols in SOURCES.items():
        m_c, b_c, wins, ws = [], [], 0, []
        for i in range(1, 5):
            tr, te = df.iloc[np.concatenate(bins[:i])], df.iloc[bins[i]]
            Mtr = normalize_probs(tr[cols].to_numpy()); Mte = normalize_probs(te[cols].to_numpy())
            Etr = ternary_elo_probs(tr["elo_delta"].to_numpy()); Ete = ternary_elo_probs(te["elo_delta"].to_numpy())
            w = best_w(tr["outcome"], Mtr, Etr); ws.append(w)
            cm = comp(te["outcome"], Mte); cb = comp(te["outcome"], normalize_probs((1 - w) * Mte + w * Ete))
            m_c.append(cm); b_c.append(cb); wins += int(cb < cm)
        mm, mb = np.mean(m_c), np.mean(b_c)
        print(f"  {name:<16} market {mm:.4f} -> blend {mb:.4f}  ({(mm-mb)/mm*100:+.2f}%, {wins}/4 folds, "
              f"mean w_elo {np.mean(ws):.2f})")

    print("\nReading: if blend beats T90_consensus but NOT pinnacle_close, the edge was denoising.")
    print("If blend still beats pinnacle_close, that is evidence of alpha beyond the sharp line.")


if __name__ == "__main__":
    main()
