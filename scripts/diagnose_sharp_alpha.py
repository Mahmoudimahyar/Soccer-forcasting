"""Where does the alpha-vs-Pinnacle-close live? Big efficient tournaments (WC/Euro/Copa) vs
thinner international markets (Nations League / qualifiers / AFCON / Gold Cup). Fixed-weight
blend (parameter-free) of Pinnacle-close + Elo, compared to Pinnacle-close, per competition tier.
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
BIG = {"soccer_fifa_world_cup", "soccer_uefa_european_championship", "soccer_conmebol_copa_america"}


def comp(y, P):
    P = normalize_probs(P)
    m = metric_report(y, P)
    m["draw_calibration_error"] = draw_calibration_error(y, P[:, 1])
    return float(sum(W[k] * m[k] for k in W)), m["rps"]


def main():
    df = pd.read_csv(DATA, parse_dates=["kickoff_utc"])
    df = df[(df["has_pinnacle"] == 1) & (df["n_books_close"] >= 3)].reset_index(drop=True)
    Ppin = normalize_probs(df[["pin_a", "pin_d", "pin_b"]].to_numpy())
    Pe = ternary_elo_probs(df["elo_delta"].to_numpy())

    print(f"n (Pinnacle present): {len(df)}")
    print("\n--- sharpness of market sources (full sample) ---")
    for nm, cols in [("T90_consensus", ["p_a_market", "p_draw_market", "p_b_market"]),
                     ("close_consensus", ["cons_a", "cons_d", "cons_b"]),
                     ("pinnacle_close", ["pin_a", "pin_d", "pin_b"])]:
        c, r = comp(df["outcome"], df[cols].to_numpy())
        print(f"  {nm:<16} composite {c:.4f}  RPS {r:.4f}")

    for w in [0.3, 0.4, 0.5]:
        Pb = (1 - w) * Ppin + w * Pe
        print(f"\n=== blend = {1-w:.1f}*Pinnacle_close + {w:.1f}*Elo (parameter-free) ===")
        print(f"{'group':<34}{'n':>4}{'pinnacle':>10}{'blend':>9}{'delta%':>8}")
        for label, mask in [("BIG (WC/Euro/Copa)", df["sport"].isin(BIG)),
                            ("THIN (NL/qual/AFCON/Gold)", ~df["sport"].isin(BIG)),
                            ("ALL", pd.Series(True, index=df.index))]:
            idx = df.index[mask]
            cp, _ = comp(df.loc[idx, "outcome"], Ppin[idx])
            cb, _ = comp(df.loc[idx, "outcome"], Pb[idx])
            print(f"  {label:<32}{len(idx):>4}{cp:>10.4f}{cb:>9.4f}{(cp-cb)/cp*100:>7.1f}%")

    # per-competition at w=0.4
    w = 0.4; Pb = (1 - w) * Ppin + w * Pe
    print(f"\n--- per competition (blend {1-w:.1f}*Pin + {w:.1f}*Elo) ---")
    print(f"{'sport':<46}{'n':>4}{'pin':>9}{'blend':>9}{'delta%':>8}")
    for sp, g in df.groupby("sport"):
        idx = g.index
        cp, _ = comp(g["outcome"], Ppin[idx]); cb, _ = comp(g["outcome"], Pb[idx])
        print(f"  {sp:<44}{len(g):>4}{cp:>9.4f}{cb:>9.4f}{(cp-cb)/cp*100:>7.1f}%")


if __name__ == "__main__":
    main()
