"""Out-of-sample test: can any model beat the no-vig market consensus on international matches?

Expanding-window temporal cross-validation over the intl dataset (train on earlier matches,
test on later). Models compared to the RAW MARKET benchmark:
  - market_raw            : the no-vig consensus itself (the bar to beat)
  - market_draw_platt     : Platt-recalibrate the market's draw probability (correct draw bias)
  - market_elo_blend      : blend market with Elo at a weight chosen on the train fold
  - stack_logit           : multinomial logit on [market logits + Elo] (learns market corrections)
  - stack_logit_platt     : stack logit, then Platt draw recalibration

A model "beats the market" only if it lowers RPS / log-loss / composite vs market_raw
ROBUSTLY across the test folds (not on one fold by luck).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.evaluation import metric_report, normalize_probs  # noqa: E402
from wcdrawlab.research.runner import draw_calibration_error  # noqa: E402

DATA = ROOT / "data" / "processed" / "intl_market_dataset.csv"
WEIGHTS = {"rps": 0.40, "log_loss": 0.25, "draw_brier": 0.20, "draw_calibration_error": 0.15}
YI = {"A": 0, "D": 1, "B": 2}


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def comp(m):
    return float(sum(WEIGHTS[k] * m[k] for k in WEIGHTS))


def scores(y, P):
    P = normalize_probs(P)
    m = metric_report(y, P)
    m["draw_calibration_error"] = draw_calibration_error(y, P[:, 1])
    m["composite"] = comp(m)
    return m


def platt_draw(p_draw_tr, ydraw_tr, P_test):
    lr = LogisticRegression(C=1.0, max_iter=1000)
    lr.fit(logit(p_draw_tr).reshape(-1, 1), ydraw_tr.astype(int))
    nd = lr.predict_proba(logit(P_test[:, 1]).reshape(-1, 1))[:, 1]
    ab = P_test[:, [0, 2]]; s = np.clip(ab.sum(1, keepdims=True), 1e-9, None)
    out = np.column_stack([(1 - nd) * ab[:, 0] / s.ravel(), nd, (1 - nd) * ab[:, 1] / s.ravel()])
    return normalize_probs(out)


def mkt(df):
    return normalize_probs(df[["p_a_market", "p_draw_market", "p_b_market"]].to_numpy())


def best_blend_weight(tr):
    from wcdrawlab.ratings import ternary_elo_probs
    Pm = mkt(tr)
    Pe = ternary_elo_probs(tr["elo_delta"].to_numpy())
    y = tr["outcome"]
    best_w, best_c = 0.0, 1e9
    for w in np.linspace(0, 0.6, 13):
        c = comp(scores(y, normalize_probs((1 - w) * Pm + w * Pe)))
        if c < best_c:
            best_c, best_w = c, w
    return best_w


def stack_features(df):
    Pm = mkt(df)
    return np.column_stack([logit(Pm[:, 0]), logit(Pm[:, 1]), logit(Pm[:, 2]),
                            df["elo_delta"].to_numpy(), df["abs_elo_delta"].to_numpy()])


def main():
    df = pd.read_csv(DATA, parse_dates=["kickoff_utc"]).sort_values("kickoff_utc").reset_index(drop=True)
    # quality filter: require a reasonable book count
    df = df[df["n_books"] >= 3].reset_index(drop=True)
    n = len(df)
    print(f"dataset: {n} matches | {df['kickoff_utc'].min().date()} -> {df['kickoff_utc'].max().date()}")

    nfold = 5
    bins = np.array_split(np.arange(n), nfold)
    from wcdrawlab.ratings import ternary_elo_probs
    agg = {k: [] for k in ["market_raw", "market_draw_platt", "market_elo_blend",
                           "stack_logit", "stack_logit_platt"]}
    for i in range(1, nfold):
        tr_idx = np.concatenate(bins[:i]); te_idx = bins[i]
        tr, te = df.iloc[tr_idx], df.iloc[te_idx]
        y_te = te["outcome"]
        ydraw_tr = (tr["outcome"] == "D").to_numpy()
        Pm_te = mkt(te)

        # market raw
        agg["market_raw"].append(scores(y_te, Pm_te))
        # market draw platt
        agg["market_draw_platt"].append(scores(y_te, platt_draw(mkt(tr)[:, 1], ydraw_tr, Pm_te)))
        # market + elo blend (weight from train)
        w = best_blend_weight(tr)
        Pblend = normalize_probs((1 - w) * Pm_te + w * ternary_elo_probs(te["elo_delta"].to_numpy()))
        agg["market_elo_blend"].append(scores(y_te, Pblend))
        # stacked logit
        sc = StandardScaler()
        Xtr = sc.fit_transform(stack_features(tr)); Xte = sc.transform(stack_features(te))
        lr = LogisticRegression(C=1.0, max_iter=2000)
        lr.fit(Xtr, tr["outcome"].map(YI))
        raw = lr.predict_proba(Xte); full = np.zeros((len(te), 3))
        for j, c in enumerate(lr.classes_):
            full[:, int(c)] = raw[:, j]
        Pstack = normalize_probs(full)
        agg["stack_logit"].append(scores(y_te, Pstack))
        # stacked + platt draw
        rawtr = lr.predict_proba(Xtr); ftr = np.zeros((len(tr), 3))
        for j, c in enumerate(lr.classes_):
            ftr[:, int(c)] = rawtr[:, j]
        agg["stack_logit_platt"].append(scores(y_te, platt_draw(normalize_probs(ftr)[:, 1], ydraw_tr, Pstack)))

    print(f"\nExpanding-window CV ({nfold-1} test folds). Mean OOS metrics (lower better):\n")
    hdr = f"{'model':<20}{'RPS':>8}{'LogLoss':>9}{'drawBrier':>11}{'drawCal':>9}{'composite':>11}"
    print(hdr); print("-" * len(hdr))
    base = np.mean([f["composite"] for f in agg["market_raw"]])
    out_rows = []
    for name, folds in agg.items():
        mean = {k: float(np.mean([f[k] for f in folds])) for k in ["rps", "log_loss", "draw_brier", "draw_calibration_error", "composite"]}
        delta = (base - mean["composite"]) / base * 100
        tag = "" if name == "market_raw" else f"  ({delta:+.2f}% vs market)"
        print(f"{name:<20}{mean['rps']:>8.4f}{mean['log_loss']:>9.4f}{mean['draw_brier']:>11.4f}"
              f"{mean['draw_calibration_error']:>9.4f}{mean['composite']:>11.4f}{tag}")
        out_rows.append({"model": name, **mean, "rel_vs_market_pct": round(delta, 3)})
    # robustness: how many folds each model beats market on composite
    print("\nfolds beating market (composite), out of", nfold - 1, ":")
    for name, folds in agg.items():
        if name == "market_raw":
            continue
        wins = sum(1 for k in range(len(folds)) if folds[k]["composite"] < agg["market_raw"][k]["composite"])
        print(f"  {name:<20} {wins}/{nfold-1}")
    pd.DataFrame(out_rows).to_csv(ROOT / "outputs" / "research" / "beat_market_cv.csv", index=False)
    print("\nwrote:", ROOT / "outputs" / "research" / "beat_market_cv.csv")


if __name__ == "__main__":
    main()
