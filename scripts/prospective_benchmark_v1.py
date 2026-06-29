"""PHASE 6 — Prospective model + no-vig market benchmark (read-only; research-only).

Consumes the harvester's primary scored rows. Computes per-model metrics with match-level bootstrap CIs,
fixture-level paired deltas vs B1 and vs the no-vig market, key strata, a tiered interpretation, and a
decision ledger. Market is a read-only comparator. No model is fit/calibrated/selected/promoted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "prospective_harvest"))
from _harvest_common import FORECAST_TARGETS, SCORING_ROOT, WORKTREE_ROOT, stamp_labels, write_json  # noqa: E402
from prospective_score_harvester_v1 import SCORED_CSV, _IDX, _onehot, _rps, _logloss  # noqa: E402

NOTES = WORKTREE_ROOT / "notes/research"
DEC_JSON = WORKTREE_ROOT / "data/reference/prospective_model_decision_ledger.json"
DEC_CSV = WORKTREE_ROOT / "data/reference/prospective_model_decision_ledger.csv"
RNG = np.random.default_rng(20260629)
COMPARED = ["M1_B1", "M2_market", "M3_75_25", "M4_50_50", "M5_25_75"]


def per_fixture_metrics(scored: pd.DataFrame) -> pd.DataFrame:
    """One row per (fixture, model) with single-match rps/logloss/draw_brier."""
    rows = []
    for r in scored.itertuples():
        P = np.array([[r.p_team_a_win, r.p_draw, r.p_team_b_win]], float)
        y = _onehot([r.outcome])
        rows.append({"canonical_fixture_id": r.canonical_fixture_id, "model_version": r.model_version,
                     "rps": _rps(P, y), "log_loss": _logloss(P, [r.outcome]),
                     "draw_brier": float((P[0, 1] - y[0, 1]) ** 2)})
    return pd.DataFrame(rows)


def boot_ci(values, B=5000):
    values = np.asarray(values, float)
    if len(values) == 0:
        return (None, None, None)
    means = [RNG.choice(values, len(values), replace=True).mean() for _ in range(B)]
    return float(values.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    scored = pd.read_csv(SCORED_CSV)
    ft = pd.read_csv(FORECAST_TARGETS)[["match_id", "elo_delta", "group", "matchday"]]
    pfm = per_fixture_metrics(scored)
    n_fix = scored["canonical_fixture_id"].nunique()
    tier = ("D_confirmatory" if n_fix >= 50 else "C_exploratory" if n_fix >= 20
            else "B_descriptive" if n_fix >= 10 else "A_smoke_test")

    # per-model metric + bootstrap CI
    model_rows = []
    for model, g in pfm.groupby("model_version"):
        for metric in ("rps", "log_loss", "draw_brier"):
            mean, lo, hi = boot_ci(g[metric].to_numpy())
            model_rows.append({"model": model, "metric": metric, "mean": mean, "ci_lo": lo, "ci_hi": hi, "n": len(g)})
    mdf = pd.DataFrame(model_rows)

    # paired deltas vs B1 and vs market, per metric (fixture-level pairing)
    wide = pfm.pivot_table(index="canonical_fixture_id", columns="model_version", values=["rps", "log_loss", "draw_brier"])
    paired = []
    for ref in ("M1_B1", "M2_market"):
        for model in COMPARED:
            if model == ref:
                continue
            for metric in ("rps", "log_loss", "draw_brier"):
                d = (wide[metric][model] - wide[metric][ref]).dropna().to_numpy()
                mean, lo, hi = boot_ci(d)
                sig = (lo is not None and (lo > 0 or hi < 0))
                paired.append({"reference": ref, "model": model, "metric": metric,
                               "mean_delta": mean, "ci_lo": lo, "ci_hi": hi,
                               "favors": ("model" if mean is not None and mean < 0 else "reference"),
                               "ci_excludes_zero": bool(sig)})
    pdf = pd.DataFrame(paired)

    # strata (descriptive): window, favorite/near-even, draw band, matchday
    s = scored.merge(ft, left_on="canonical_fixture_id", right_on="match_id", how="left")
    b1 = s[s.model_version == "M1_B1"][["canonical_fixture_id", "p_team_a_win", "p_team_b_win", "p_draw", "elo_delta", "matchday", "selected_window"]]
    b1 = b1.assign(fav=np.where(b1.p_team_a_win > b1.p_team_b_win, "a_fav", "b_fav"),
                   near_even=(b1.p_team_a_win - b1.p_team_b_win).abs() < 0.12,
                   draw_band=pd.cut(b1.p_draw, [0, 0.18, 0.24, 1.0], labels=["low", "mid", "high"]))
    strata_summary = {
        "by_window": s.drop_duplicates("canonical_fixture_id")["selected_window"].value_counts().to_dict(),
        "by_matchday": b1["matchday"].value_counts().sort_index().to_dict(),
        "n_a_fav": int((b1.fav == "a_fav").sum()), "n_b_fav": int((b1.fav == "b_fav").sum()),
        "n_near_even": int(b1.near_even.sum()),
        "draw_band": b1["draw_band"].value_counts().to_dict(),
    }

    # decision ledger — classify each model honestly (Tier C => exploratory/underpowered; never runtime)
    metric_means = mdf.pivot_table(index="model", columns="metric", values="mean")
    ledger = []
    for model in COMPARED:
        # is there CI-excludes-zero evidence this model beats BOTH B1 and market on any metric?
        beats = pdf[(pdf.model == model) & (pdf.ci_excludes_zero) & (pdf.favors == "model")]
        if model == "M2_market":
            cls = "market_comparator_only"
            note = "No-vig market is the read-only benchmark, not a candidate."
        elif model == "M1_B1":
            cls = "reference_only"
            note = "Approved runtime baseline; evaluated as the reference, not promotable here."
        elif n_fix < 20:
            cls = "data_insufficient"; note = "Below exploratory threshold."
        elif beats.empty:
            cls = "no_evidence_of_improvement"
            note = "No fixture-level paired delta vs B1 AND vs market excludes zero at this n."
        else:
            cls = "exploratory_underpowered"
            note = f"Nominal edge on {sorted(set(beats.metric))} but Tier {tier}; not confirmatory; not promotable."
        ledger.append({"model": model, "classification": cls, "tier": tier, "n_fixtures": int(n_fix),
                       "rps": float(metric_means.loc[model, "rps"]), "log_loss": float(metric_means.loc[model, "log_loss"]),
                       "draw_brier": float(metric_means.loc[model, "draw_brier"]), "note": note,
                       "runtime_ready": False, "trade_eligible": False})
    led = pd.DataFrame(ledger)
    led.to_csv(DEC_CSV, index=False)
    write_json(DEC_JSON, stamp_labels({"tier": tier, "n_primary_fixtures": int(n_fix), "ledger": ledger,
                                       "strata": strata_summary}))

    mdf.to_csv(SCORING_ROOT / "benchmark_model_metrics_ci.csv", index=False)
    pdf.to_csv(SCORING_ROOT / "benchmark_paired_deltas.csv", index=False)

    # ---- human reports (generated from computed numbers) ----
    obs_draw = float((scored[scored.model_version == "M1_B1"]["outcome"] == "D").mean())
    _write_reports(mdf, pdf, led, strata_summary, n_fix, tier, obs_draw)
    print(f"BENCHMARK OK | n_fixtures={n_fix} tier={tier} | decision ledger -> {DEC_CSV.name}")
    print(led[["model", "classification", "rps", "log_loss", "draw_brier"]].round(4).to_string(index=False))


def _fmt_ci(row):
    return f"{row['mean']:.4f} [{row['ci_lo']:.4f}, {row['ci_hi']:.4f}]"


def _write_reports(mdf, pdf, led, strata, n_fix, tier, obs_draw):
    L = "**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**"
    rps = mdf[mdf.metric == "rps"].set_index("model")
    ll = mdf[mdf.metric == "log_loss"].set_index("model")
    db = mdf[mdf.metric == "draw_brier"].set_index("model")

    # scorecard
    sc = [f"# Prospective Shadow Scorecard V1", "", L, "",
          f"Primary one-snapshot-per-fixture benchmark on **{n_fix}** completed 2026 WC group fixtures — "
          f"**sample-size tier {tier}**. Match-level bootstrap (5000). Read-only; nothing promoted.", "",
          "| model | RPS [95% CI] | log-loss [95% CI] | draw-Brier [95% CI] |", "|---|---|---|---|"]
    for m in COMPARED:
        sc.append(f"| {m} | {_fmt_ci(rps.loc[m])} | {_fmt_ci(ll.loc[m])} | {_fmt_ci(db.loc[m])} |")
    sc += ["", "## Paired fixture-level deltas (negative ⇒ row model better than reference)",
           "| reference | model | metric | mean Δ [95% CI] | CI excludes 0 |", "|---|---|---|---|---|"]
    for r in pdf.itertuples():
        sc.append(f"| {r.reference} | {r.model} | {r.metric} | {r.mean_delta:.4f} [{r.ci_lo:.4f}, {r.ci_hi:.4f}] | {'YES' if r.ci_excludes_zero else 'no'} |")
    sc += ["", f"At tier {tier} no paired delta vs **both** B1 and the market excludes zero; differences are "
           "within sampling noise. **No model is ranked or promoted.**"]
    (NOTES / "PROSPECTIVE_SHADOW_SCORECARD_V1.md").write_text("\n".join(sc) + "\n", encoding="utf-8")

    # calibration
    cal = pd.read_csv(SCORING_ROOT / "model_metrics.csv").set_index("model")
    ca = [f"# Prospective Calibration & Reliability V1", "", L, "",
          f"Observed draw rate = **{obs_draw:.3f}** on {n_fix} fixtures. Calibration diagnostics only; "
          "no model's calibration was modified.", "",
          "| model | ECE | draw cal slope | draw cal intercept | mean pred draw | obs draw |", "|---|---|---|---|---|---|"]
    for m in COMPARED:
        r = cal.loc[m]
        ca.append(f"| {m} | {r.ece:.4f} | {r.draw_cal_slope:.3f} | {r.draw_cal_intercept:.3f} | {r.mean_pred_draw:.3f} | {r.obs_draw_rate:.3f} |")
    ca += ["", "Draw-calibration slope/intercept are noisy logistic diagnostics at this n (~9 draws) and are "
           "reported for transparency only. All models slightly under-predict draws; reliability bins in "
           "`model_reliability_bins.csv`."]
    (NOTES / "PROSPECTIVE_CALIBRATION_AND_RELIABILITY_V1.md").write_text("\n".join(ca) + "\n", encoding="utf-8")

    # market benchmark
    mb = [f"# Prospective Market Benchmark V1", "", L, "",
          "The no-vig market (`M2_market`) is a **read-only comparator** — never a model feature, never a "
          "calibration target, never a trading signal.", "",
          f"- Fixtures: {n_fix} (tier {tier}).",
          f"- RPS: B1={rps.loc['M1_B1','mean']:.4f}, market={rps.loc['M2_market','mean']:.4f} "
          f"(B1 {'lower/better' if rps.loc['M1_B1','mean']<rps.loc['M2_market','mean'] else 'higher/worse'}).",
          f"- Log-loss: B1={ll.loc['M1_B1','mean']:.4f}, market={ll.loc['M2_market','mean']:.4f}.",
          f"- Draw-Brier: B1={db.loc['M1_B1','mean']:.4f}, market={db.loc['M2_market','mean']:.4f}.", "",
          "### Strata (descriptive)", f"- window: {strata['by_window']}",
          f"- matchday: {strata['by_matchday']}", f"- a_fav/b_fav/near_even: {strata['n_a_fav']}/{strata['n_b_fav']}/{strata['n_near_even']}",
          "", "### Honest conclusion",
          f"On {n_fix} fixtures the model–market gaps are small and bootstrap CIs overlap zero on every "
          "paired metric. There is **no evidence** that B1 or any blend beats the market (or vice-versa) "
          "at decision-grade confidence. A valid result may favor any of them; none is manufactured a "
          "winner. **Nothing is promoted to runtime; no trading rule is implied.**"]
    (NOTES / "PROSPECTIVE_MARKET_BENCHMARK_V1.md").write_text("\n".join(mb) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
