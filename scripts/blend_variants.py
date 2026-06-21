"""Can we push the market+Elo edge further (without overfitting 341 matches)?
Expanding-window temporal CV, comparing blend variants to raw market. Robust winner = beats
market on most folds AND on the deep-market World Cup subset.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.evaluation import metric_report, normalize_probs  # noqa: E402
from wcdrawlab.research.runner import draw_calibration_error  # noqa: E402
from wcdrawlab.ratings import ternary_elo_probs  # noqa: E402

DATA = ROOT / "data" / "processed" / "intl_market_dataset.csv"
W = {"rps": 0.40, "log_loss": 0.25, "draw_brier": 0.20, "draw_calibration_error": 0.15}
YI = {"A": 0, "D": 1, "B": 2}


def comp(y, P):
    P = normalize_probs(P)
    m = metric_report(y, P)
    m["draw_calibration_error"] = draw_calibration_error(y, P[:, 1])
    return float(sum(W[k] * m[k] for k in W))


def mkt(d):
    return normalize_probs(d[["p_a_market", "p_draw_market", "p_b_market"]].to_numpy())


def fitted_elo(tr, te):
    """3-way logit of outcome on elo_delta (calibrates the Elo->prob curve on train)."""
    lr = LogisticRegression(C=1.0, max_iter=1000)
    lr.fit(tr[["elo_delta", "abs_elo_delta"]], tr["outcome"].map(YI))
    raw = lr.predict_proba(te[["elo_delta", "abs_elo_delta"]]); full = np.zeros((len(te), 3))
    for j, c in enumerate(lr.classes_):
        full[:, int(c)] = raw[:, j]
    return normalize_probs(full)


def best_w(tr, base_tr):
    Pm = mkt(tr); y = tr["outcome"]
    return min(np.linspace(0, 0.6, 13), key=lambda w: comp(y, (1 - w) * Pm + w * base_tr))


def main():
    df = pd.read_csv(DATA, parse_dates=["kickoff_utc"]).sort_values("kickoff_utc").reset_index(drop=True)
    df = df[df["n_books"] >= 3].reset_index(drop=True)
    n = len(df); bins = np.array_split(np.arange(n), 5)
    models = ["market_raw", "blend_ternaryElo", "blend_fittedEloLogit", "blend_depthAware"]
    agg = {m: [] for m in models}
    wc_agg = {m: {"P": [], "y": []} for m in models}

    for i in range(1, 5):
        tr = df.iloc[np.concatenate(bins[:i])]; te = df.iloc[bins[i]]
        y = te["outcome"]; Pm = mkt(te)
        Pe_te = ternary_elo_probs(te["elo_delta"].to_numpy()); Pe_tr = ternary_elo_probs(tr["elo_delta"].to_numpy())
        Pf_te = fitted_elo(tr, te)
        # weights from train
        w1 = best_w(tr, Pe_tr); w2 = best_w(tr, fitted_elo(tr, tr))
        preds = {
            "market_raw": Pm,
            "blend_ternaryElo": normalize_probs((1 - w1) * Pm + w1 * Pe_te),
            "blend_fittedEloLogit": normalize_probs((1 - w2) * Pm + w2 * Pf_te),
            # depth-aware: more Elo when fewer books (w = clip(4/n_books, .15,.5))
            "blend_depthAware": normalize_probs(
                (1 - np.clip(4 / te["n_books"].to_numpy(), .15, .5))[:, None] * Pm
                + np.clip(4 / te["n_books"].to_numpy(), .15, .5)[:, None] * Pe_te),
        }
        for m, P in preds.items():
            agg[m].append(comp(y, P))
            wcmask = (te["sport"] == "soccer_fifa_world_cup").to_numpy()
            if wcmask.any():
                wc_agg[m]["P"].append(P[wcmask]); wc_agg[m]["y"].append(y[wcmask])

    print("Expanding-window CV (4 folds). Mean OOS composite + folds-beating-market:\n")
    base = np.mean(agg["market_raw"])
    for m in models:
        mean = np.mean(agg[m])
        wins = sum(1 for k in range(4) if agg[m][k] < agg["market_raw"][k])
        tag = "" if m == "market_raw" else f"  ({(base-mean)/base*100:+.2f}% vs mkt, {wins}/4 folds)"
        print(f"  {m:<22}{mean:.4f}{tag}")
    print("\nWorld-Cup-only pooled OOS composite (deep market):")
    for m in models:
        if wc_agg[m]["P"]:
            P = np.vstack(wc_agg[m]["P"]); y = pd.concat(wc_agg[m]["y"])
            print(f"  {m:<22}{comp(y, P):.4f}")


if __name__ == "__main__":
    main()
