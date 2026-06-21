"""Tier-2 reproducible baseline suite B0-B7 with rigorous evaluation.

Folds (temporal): dev train<2010->2010, train<2014->2014, train<2018->2018;
gate train<2022->2022 (read ONCE); locked train<2026->2026 Matchday 1.
Selection is on DEV folds only; 2022 is a single gate read; 2026-MD1 is a locked transfer.

Metrics: RPS, 3-way log loss, draw Brier, draw calibration error, draw calibration slope/
intercept, reliability, draw-interval coverage, worst-fold, and PAIRED BOOTSTRAP CIs of every
model's per-match RPS/log-loss delta vs B1 (Elo-only).

Market rule: B6 (no-vig market) only where real timestamped odds exist (2022). B7 has a no-market
variant (all folds) and a market-enabled variant (2022 only). No fake odds; missing => unavailable.
Calibration rule: B7 draw recalibration is fit on TRAIN data only (latest pre-cutoff tournament as
calibration split), never on the test fold.

Outputs: outputs/research/tier2/{by_fold.csv, bootstrap_vs_elo.csv, calibration.csv,
reliability_dev.csv, predictions_2026_md1.csv}
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.evaluation import normalize_probs  # noqa: E402
from wcdrawlab.research.runner import draw_calibration_error  # noqa: E402
from wcdrawlab.ratings import ternary_elo_probs  # noqa: E402
from wcdrawlab.models.baselines import HistoricalPriorModel, TernaryEloModel, MultinomialLogitModel  # noqa: E402
from wcdrawlab.models.scoreline import IndependentPoissonModel  # noqa: E402
from wcdrawlab.market import no_vig_from_decimal_odds  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs" / "research" / "tier2"
WEIGHTS = {"rps": 0.40, "log_loss": 0.25, "draw_brier": 0.20, "draw_calibration_error": 0.15}
YI = {"A": 0, "D": 1, "B": 2}
MODEL_VERSION = "tier2-baselines-v1"

FOLDS = [("dev_2010", 2010, 2010, None), ("dev_2014", 2014, 2014, None),
         ("dev_2018", 2018, 2018, None), ("gate_2022", 2022, 2022, None),
         ("locked_2026_md1", 2026, 2026, 1)]
LOGIT = ["elo_delta", "abs_elo_delta", "matchday", "prior_group_draws",
         "prior_group_goals_per_match", "group_state_points_delta", "group_state_gd_delta",
         "venue_host_advantage", "confed_same"]
FIFA = ["fifa_z_delta", "abs_fifa_z_delta", "fifa_rank_pct_delta"]
HOST = ["elo_delta", "abs_elo_delta", "venue_host_advantage"]
POIS = ["elo_delta", "abs_elo_delta", "venue_host_advantage"]


# ---------- per-match metrics ----------
def per_match_rps(P, y):
    P = normalize_probs(P); idx = y.map(YI).to_numpy()
    cp = np.cumsum(P, axis=1); obs = np.zeros_like(P)
    for i, o in enumerate(idx):
        obs[i, o:] = 1.0
    return ((cp - obs) ** 2).sum(axis=1) / 2.0

def per_match_ll(P, y):
    P = normalize_probs(P); idx = y.map(YI).to_numpy()
    return -np.log(np.clip(P[np.arange(len(P)), idx], 1e-12, 1))

def per_match_draw_brier(P, y):
    P = normalize_probs(P); yd = (y.to_numpy() == "D").astype(float)
    return (P[:, 1] - yd) ** 2

def fold_metrics(P, y):
    rps = per_match_rps(P, y).mean(); ll = per_match_ll(P, y).mean()
    db = per_match_draw_brier(P, y).mean(); dce = draw_calibration_error(y, normalize_probs(P)[:, 1])
    comp = WEIGHTS["rps"]*rps + WEIGHTS["log_loss"]*ll + WEIGHTS["draw_brier"]*db + WEIGHTS["draw_calibration_error"]*dce
    pred = np.array(["A", "D", "B"])[normalize_probs(P).argmax(1)]
    return {"rps": rps, "log_loss": ll, "draw_brier": db, "draw_calibration_error": dce,
            "composite": comp, "accuracy": float((pred == y.to_numpy()).mean())}


def draw_calib_slope_intercept(P, y):
    """Logistic recalibration of draw prob: is_draw ~ a + b*logit(p_draw). slope b~1, intercept a~0 ideal."""
    p = np.clip(normalize_probs(P)[:, 1], 1e-4, 1 - 1e-4)
    z = np.log(p / (1 - p)).reshape(-1, 1); yd = (y.to_numpy() == "D").astype(int)
    if yd.sum() < 3 or yd.sum() > len(yd) - 3:
        return np.nan, np.nan
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(z, yd)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def reliability(P, y, bins=10):
    p = normalize_probs(P)[:, 1]; yd = (y.to_numpy() == "D").astype(float)
    edges = np.linspace(0, 1, bins + 1); rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if m.any():
            rows.append({"bin": f"[{lo:.1f},{hi:.1f})", "n": int(m.sum()),
                         "pred": round(float(p[m].mean()), 3), "actual": round(float(yd[m].mean()), 3)})
    return pd.DataFrame(rows)


def draw_interval_coverage(P, y, bins=10):
    p = normalize_probs(P)[:, 1]; yd = (y.to_numpy() == "D").astype(float)
    edges = np.linspace(0, 1, bins + 1); inside = total = 0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi)); n = int(m.sum())
        if n >= 5:
            pm = float(p[m].mean()); se = np.sqrt(max(pm*(1-pm), 1e-9)/n); total += 1
            inside += int(abs(float(yd[m].mean()) - pm) <= 1.645*se)
    return inside/total if total else float("nan")


# ---------- models ----------
def b0(tr, te): return HistoricalPriorModel().fit(tr["outcome"]).predict_proba(len(te)), {}
def b1(tr, te): return TernaryEloModel(r=0.4).predict_proba(te), {}
def b2(tr, te):
    cols = [c for c in FIFA if c in tr.columns]
    return MultinomialLogitModel(features=cols, C=0.5).fit(tr, tr["outcome"]).predict_proba(te), {}
def b3(tr, te):
    return MultinomialLogitModel(features=HOST, C=0.5).fit(tr, tr["outcome"]).predict_proba(te), {}
def _poisson(tr, te, rho, diag):
    m = IndependentPoissonModel(features=POIS, rho=rho, diagonal_inflation=diag)
    m.fit(tr, tr["goals_a"].astype(int), tr["goals_b"].astype(int))
    la, lb = m.predict_lambdas(te)
    return m.predict_proba(te), {"eg_a": la, "eg_b": lb}
def b4(tr, te): return _poisson(tr, te, 0.0, 0.0)
def b5(tr, te): return _poisson(tr, te, -0.05, 0.05)

def _general_logit(tr, te):
    cols = [c for c in LOGIT if c in tr.columns]
    return MultinomialLogitModel(features=cols, C=0.5).fit(tr, tr["outcome"]).predict_proba(te)

def _platt_draw(p_tr, yd_tr, P_te):
    def lg(p): p = np.clip(p, 1e-4, 1-1e-4); return np.log(p/(1-p))
    lr = LogisticRegression(C=1.0, max_iter=1000).fit(lg(p_tr).reshape(-1, 1), yd_tr.astype(int))
    nd = lr.predict_proba(lg(P_te[:, 1]).reshape(-1, 1))[:, 1]
    ab = P_te[:, [0, 2]]; s = np.clip(ab.sum(1, keepdims=True), 1e-9, None)
    return normalize_probs(np.column_stack([(1-nd)*ab[:, 0]/s.ravel(), nd, (1-nd)*ab[:, 1]/s.ravel()]))

def b7_nomarket(tr, te):
    """Blend B1+B5+general-logit, draw recalibrated with a TRAIN-ONLY calibration split
    (latest pre-cutoff tournament). 0.4 Elo weight (matches accepted candidate)."""
    base_te = normalize_probs(np.mean([b1(tr, te)[0], b5(tr, te)[0], _general_logit(tr, te)], axis=0))
    yrs = sorted(pd.to_datetime(tr["kickoff_utc"], utc=True).dt.year.unique())
    if len(yrs) >= 2:
        cy = yrs[-1]; ty = pd.to_datetime(tr["kickoff_utc"], utc=True).dt.year
        base_tr, calib = tr[ty < cy], tr[ty == cy]
        if len(base_tr) >= 30 and len(calib) >= 20:
            base_cal = normalize_probs(np.mean([b1(base_tr, calib)[0], b5(base_tr, calib)[0],
                                                _general_logit(base_tr, calib)], axis=0))
            return _platt_draw(base_cal[:, 1], (calib["outcome"] == "D").to_numpy().astype(float), base_te), {}
    return base_te, {}


def market_probs_2022(te):
    """Real no-vig consensus for 2022 test rows, aligned to team_a/team_b. None if unavailable."""
    mk = pd.read_csv(PROC / "market_features_2022.csv")
    mk["pair"] = [frozenset((canonical_team_name(a), canonical_team_name(b))) for a, b in zip(mk.team_a, mk.team_b)]
    mp = {r["pair"]: r for _, r in mk.iterrows()}
    P = np.full((len(te), 3), np.nan)
    for i, (_, r) in enumerate(te.iterrows()):
        m = mp.get(frozenset((r["team_a"], r["team_b"])))
        if m is None:
            continue
        P[i] = [m.p_a_market, m.p_draw_market, m.p_b_market] if m["team_a"] == r["team_a"] \
            else [m.p_b_market, m.p_draw_market, m.p_a_market]
    return P if not np.isnan(P).any() else (P if (~np.isnan(P[:, 0])).mean() > 0.9 else None)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(PROC / "research_modeling_table.csv", parse_dates=["kickoff_utc"])
    df["year"] = df["kickoff_utc"].dt.year

    base_models = {"B0_prior": b0, "B1_elo": b1, "B2_fifa": b2, "B3_elo_host": b3,
                   "B4_poisson": b4, "B5_dixon_coles": b5, "B7_nomarket": b7_nomarket}
    rows = []
    per_match = {}   # (fold, model) -> {"rps":arr,"ll":arr,"y":Series,"P":arr}
    for fname, before, ty, md in FOLDS:
        tr = df[df.year < before].copy(); te = df[df.year == ty].copy()
        if md is not None:
            te = te[te.matchday == md].copy()
        if tr.empty or te.empty:
            continue
        y = te["outcome"]
        models = dict(base_models)
        # B6 + B7_market only where real odds exist (2022)
        if ty == 2022:
            Pm = market_probs_2022(te)
            if Pm is not None and not np.isnan(Pm).any():
                models["B6_market"] = lambda tr, te, Pm=Pm: (normalize_probs(Pm), {})
                def b7_market(tr, te, Pm=Pm):
                    nm = b7_nomarket(tr, te)[0]
                    return normalize_probs(0.5 * normalize_probs(Pm) + 0.5 * nm), {}
                models["B7_market"] = b7_market
        for name, fn in models.items():
            P, extra = fn(tr, te); P = normalize_probs(P)
            m = fold_metrics(P, y)
            sl, ic = draw_calib_slope_intercept(P, y)
            m.update(model=name, fold=fname, n_train=len(tr), n_test=len(te),
                     draw_cal_slope=sl, draw_cal_intercept=ic, draw_interval_coverage=draw_interval_coverage(P, y))
            rows.append(m)
            per_match[(fname, name)] = {"rps": per_match_rps(P, y), "ll": per_match_ll(P, y), "y": y, "P": P}

    res = pd.DataFrame(rows)
    keep = ["model", "fold", "n_train", "n_test", "rps", "log_loss", "draw_brier",
            "draw_calibration_error", "draw_cal_slope", "draw_cal_intercept",
            "draw_interval_coverage", "composite", "accuracy"]
    res[keep].round(4).to_csv(OUT / "by_fold.csv", index=False)

    # worst-fold (dev only) per model
    dev = res[res.fold.str.startswith("dev_")]
    summ = dev.groupby("model").agg(dev_composite_mean=("composite", "mean"),
                                    dev_composite_worst=("composite", "max"),
                                    dev_rps_mean=("rps", "mean"),
                                    dev_logloss_mean=("log_loss", "mean")).round(4)

    # paired bootstrap vs B1 (Elo) on pooled DEV per-match deltas
    def pooled(model, metric):
        arrs = [per_match[(f, model)][metric] for f in ["dev_2010", "dev_2014", "dev_2018"] if (f, model) in per_match]
        return np.concatenate(arrs) if arrs else None
    rng = np.random.default_rng(0)
    boot_rows = []
    b1_rps = pooled("B1_elo", "rps"); b1_ll = pooled("B1_elo", "ll")
    for model in base_models:
        if model == "B1_elo":
            continue
        mr = pooled(model, "rps"); ml = pooled(model, "ll")
        if mr is None:
            continue
        d_rps = mr - b1_rps; d_ll = ml - b1_ll  # negative = better than Elo
        def ci(d):
            bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
            return float(np.mean(d)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
        mrd, rl, rh = ci(d_rps); mld, ll_, lh = ci(d_ll)
        boot_rows.append({"model": model, "vs": "B1_elo", "n_dev": len(d_rps),
                          "dRPS_mean": round(mrd, 4), "dRPS_ci": f"[{rl:.4f},{rh:.4f}]",
                          "RPS_better_sig": rh < 0, "RPS_worse_sig": rl > 0,
                          "dLogLoss_mean": round(mld, 4), "dLogLoss_ci": f"[{ll_:.4f},{lh:.4f}]"})
    boot = pd.DataFrame(boot_rows)
    boot.to_csv(OUT / "bootstrap_vs_elo.csv", index=False)

    # calibration table (dev pooled) + reliability for B1 and B7_nomarket
    res[["model", "fold", "draw_cal_slope", "draw_cal_intercept", "draw_calibration_error",
         "draw_interval_coverage"]].round(4).to_csv(OUT / "calibration.csv", index=False)
    yb = pd.concat([per_match[(f, "B7_nomarket")]["y"] for f in ["dev_2010", "dev_2014", "dev_2018"]])
    Pb = np.vstack([per_match[(f, "B7_nomarket")]["P"] for f in ["dev_2010", "dev_2014", "dev_2018"]])
    reliability(Pb, yb).to_csv(OUT / "reliability_dev_b7.csv", index=False)

    pd.set_option("display.width", 200)
    print("=== BY FOLD (composite, lower better) ===")
    print(res.pivot_table(index="model", columns="fold", values="composite").round(4).to_string())
    print("\n=== DEV summary (selection folds) ==="); print(summ.to_string())
    print("\n=== PAIRED BOOTSTRAP vs B1 (pooled DEV; dRPS<0 = better; sig if CI excludes 0) ===")
    print(boot.to_string(index=False))
    print("\n=== 2022 gate (single read) ===")
    print(res[res.fold == "gate_2022"][["model", "rps", "log_loss", "draw_calibration_error", "composite"]].round(4).to_string(index=False))
    print("\n=== 2026 MD1 locked (transfer only) ===")
    print(res[res.fold == "locked_2026_md1"][["model", "rps", "log_loss", "draw_calibration_error", "composite"]].round(4).to_string(index=False))
    print("\nwrote:", OUT)


if __name__ == "__main__":
    main()
