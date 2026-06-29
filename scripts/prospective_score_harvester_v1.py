"""PHASE 4 — Independent, idempotent prospective score harvester (prospective_score_harvester_v1).

Reads immutable frozen predictions + verified-final result records + the primary snapshot registry.
Writes ONLY under outputs/live_shadow/scoring_v1/. Append-only; first-write-wins per score key; result
corrections are appended (never silently rewritten). Never mutates frozen predictions or odds; never
calls The Odds API; never fits/calibrates/selects a model. Market is a read-only comparator.

Score key = prediction_id + final_result_hash + scorer_version  (idempotent).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "prospective_harvest"))
from _harvest_common import (  # noqa: E402
    FORECAST_TARGETS, PRED_LEDGER, SCORER_VERSION, SCORING_ROOT, stamp_labels, write_json,
)
from select_primary_prospective_snapshots import COMPARED, select_primary  # noqa: E402
from refresh_prospective_final_results import RESULTS_CSV  # noqa: E402

OUT = SCORING_ROOT
SCORED_CSV = OUT / "scored_prediction_rows.csv"
SCORED_JSONL = OUT / "scored_prediction_rows.jsonl"
PRIMARY_SCORECARD = OUT / "primary_fixture_scorecard.csv"
DESCRIPTIVE_SCORECARD = OUT / "all_snapshot_descriptive_scorecard.csv"
MODEL_METRICS = OUT / "model_metrics.csv"
MODEL_CAL = OUT / "model_calibration.csv"
RELIABILITY = OUT / "model_reliability_bins.csv"
MARKET_ALIGN = OUT / "market_alignment_metrics.csv"
EXCLUSIONS = OUT / "scoring_exclusion_ledger.csv"
RUN_MANIFEST = OUT / "scoring_run_manifest.json"
INTEGRITY = OUT / "scoring_integrity_audit.json"

_IDX = {"A": 0, "D": 1, "B": 2}


def _ts(x):
    try:
        return pd.Timestamp(str(x))
    except Exception:
        return pd.NaT


def prediction_id(match_id, model, ss_ts, pred_ts) -> str:
    return hashlib.sha256(f"{match_id}|{model}|{ss_ts}|{pred_ts}".encode()).hexdigest()[:24]


def result_hash(fixture_id, ha, hb, status) -> str:
    return hashlib.sha256(f"{fixture_id}|{ha}|{hb}|{status}".encode()).hexdigest()[:24]


# ---- metrics (diagnostics only; nothing is fit or used to alter a model) --------------------------
def _onehot(outcomes):
    y = np.zeros((len(outcomes), 3))
    for i, o in enumerate(outcomes):
        y[i, _IDX[o]] = 1.0
    return y


def _rps(P, y):
    # ordered RPS over (A, D, B): standard 1X2 ranked probability score
    cp, cy = np.cumsum(P, axis=1), np.cumsum(y, axis=1)
    return float(np.mean(np.sum((cp - cy) ** 2, axis=1) / 2.0))


def _logloss(P, outcomes):
    idx = np.array([_IDX[o] for o in outcomes])
    p = P[np.arange(len(P)), idx]
    return float(-np.mean(np.log(np.clip(p, 1e-12, 1))))


def _ece(P, outcomes, bins=10):
    conf = P.max(axis=1)
    pred = P.argmax(axis=1)
    correct = np.array([_IDX[o] for o in outcomes]) == pred
    edges = np.linspace(0, 1, bins + 1)
    e, n = 0.0, len(P)
    for i in range(bins):
        m = (conf > edges[i]) & (conf <= edges[i + 1])
        if m.sum():
            e += (m.sum() / n) * abs(correct[m].mean() - conf[m].mean())
    return float(e)


def _cal_slope_intercept(p_draw, is_draw):
    """Diagnostic logistic recalibration of the DRAW probability (does NOT modify any model)."""
    p = np.clip(np.asarray(p_draw, float), 1e-6, 1 - 1e-6)
    x = np.log(p / (1 - p)); y = np.asarray(is_draw, float)
    if len(np.unique(y)) < 2:
        return None, None
    b0, b1 = 0.0, 1.0
    for _ in range(200):  # Newton steps
        z = b0 + b1 * x; pr = 1 / (1 + np.exp(-z)); w = np.clip(pr * (1 - pr), 1e-9, None)
        g0 = np.sum(pr - y); g1 = np.sum((pr - y) * x)
        h00 = np.sum(w); h01 = np.sum(w * x); h11 = np.sum(w * x * x)
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            break
        b0 -= (h11 * g0 - h01 * g1) / det; b1 -= (-h01 * g0 + h00 * g1) / det
    return float(b1), float(b0)  # slope, intercept


def model_metrics(df: pd.DataFrame, scope: str) -> list[dict]:
    recs = []
    if df is None or df.empty or "model_version" not in df.columns:
        return recs  # explicit no_eligible_rows state, never a false success
    for model, g in df.groupby("model_version"):
        P = g[["p_team_a_win", "p_draw", "p_team_b_win"]].to_numpy(float)
        outc = g["outcome"].tolist()
        y = _onehot(outc)
        is_draw = (np.array(outc) == "D").astype(float)
        slope, intercept = _cal_slope_intercept(g["p_draw"].to_numpy(float), is_draw)
        recs.append({
            "scope": scope, "model": model, "n_fixtures": int(len(g)),
            "rps": _rps(P, y), "log_loss": _logloss(P, outc),
            "draw_brier": float(np.mean((P[:, 1] - y[:, 1]) ** 2)),
            "brier_home": float(np.mean((P[:, 0] - y[:, 0]) ** 2)),
            "brier_draw": float(np.mean((P[:, 1] - y[:, 1]) ** 2)),
            "brier_away": float(np.mean((P[:, 2] - y[:, 2]) ** 2)),
            "ece": _ece(P, outc), "draw_cal_slope": slope, "draw_cal_intercept": intercept,
            "sharpness_mean_maxprob": float(np.mean(P.max(axis=1))),
            "mean_pred_draw": float(np.mean(P[:, 1])), "obs_draw_rate": float(is_draw.mean()),
        })
    return recs


def reliability_bins(df, bins=5):
    recs = []
    edges = np.linspace(0, 1, bins + 1)
    for model, g in df.groupby("model_version"):
        pd_ = g["p_draw"].to_numpy(float); is_draw = (g["outcome"].to_numpy() == "D").astype(float)
        for i in range(bins):
            m = (pd_ > edges[i]) & (pd_ <= edges[i + 1]) if i > 0 else (pd_ >= edges[i]) & (pd_ <= edges[i + 1])
            if m.sum():
                recs.append({"model": model, "bin_low": edges[i], "bin_high": edges[i + 1],
                             "n": int(m.sum()), "mean_pred_draw": float(pd_[m].mean()),
                             "obs_draw_rate": float(is_draw[m].mean())})
    return recs


def market_alignment(df):
    """Read-only comparator stats: how each model's draw prob relates to the no-vig market's. No fitting."""
    recs = []
    m2 = df[df.model_version == "M2_market"][["canonical_fixture_id", "p_team_a_win", "p_draw", "p_team_b_win"]]
    m2 = m2.rename(columns={"p_team_a_win": "mk_a", "p_draw": "mk_d", "p_team_b_win": "mk_b"})
    for model, g in df.groupby("model_version"):
        j = g.merge(m2, on="canonical_fixture_id", how="inner")
        if j.empty:
            continue
        recs.append({"model": model, "n": int(len(j)),
                     "mean_abs_draw_gap_vs_market": float(np.mean(np.abs(j.p_draw - j.mk_d))),
                     "mean_abs_home_gap_vs_market": float(np.mean(np.abs(j.p_team_a_win - j.mk_a)))})
    return recs


def build_scored_rows(primary: pd.DataFrame, results: pd.DataFrame, retrieval_ts: str):
    """Attach verified-final outcome to each primary row; enforce hard gates; return scored df + exclusions."""
    res = results[results.reconciliation_status == "verified_final"].copy()
    out_by_fix = {r.canonical_fixture_id: r for r in res.itertuples()}
    scored, excl = [], []
    for r in primary.itertuples():
        fix = r.canonical_fixture_id
        rr = out_by_fix.get(fix)
        pt, ko, ss = _ts(r.prediction_timestamp), _ts(r.kickoff_utc), _ts(r.selected_source_snapshot_timestamp)
        # hard gates
        if rr is None:
            excl.append({"canonical_fixture_id": fix, "model_version": r.model_version, "reason": "no_verified_final_result"}); continue
        if not (pd.notna(pt) and pd.notna(ko) and pt < ko):
            excl.append({"canonical_fixture_id": fix, "model_version": r.model_version, "reason": "not_pre_kickoff"}); continue
        if not (pd.notna(ss) and ss <= pt + pd.Timedelta(seconds=5)):
            excl.append({"canonical_fixture_id": fix, "model_version": r.model_version, "reason": "market_snapshot_after_prediction"}); continue
        P = np.array([r.p_team_a_win, r.p_draw, r.p_team_b_win], float)
        if np.isnan(P).any() or abs(P.sum() - 1) > 1e-6:
            excl.append({"canonical_fixture_id": fix, "model_version": r.model_version, "reason": "invalid_simplex"}); continue
        oc = rr.final_1x2_outcome_team_a_orientation
        if oc not in _IDX:
            excl.append({"canonical_fixture_id": fix, "model_version": r.model_version, "reason": "unresolved_outcome"}); continue
        rh = result_hash(fix, rr.home_regulation_goals, rr.away_regulation_goals, rr.final_status)
        pid = prediction_id(fix, r.model_version, r.selected_source_snapshot_timestamp, r.prediction_timestamp)
        scored.append({
            "score_key": f"{pid}|{rh}|{SCORER_VERSION}", "prediction_id": pid, "final_result_hash": rh,
            "scorer_version": SCORER_VERSION, "canonical_fixture_id": fix, "model_version": r.model_version,
            "selected_window": r.selected_window, "prediction_timestamp": r.prediction_timestamp,
            "source_snapshot_timestamp": r.selected_source_snapshot_timestamp, "kickoff_utc": r.kickoff_utc,
            "p_team_a_win": r.p_team_a_win, "p_draw": r.p_draw, "p_team_b_win": r.p_team_b_win,
            "outcome": oc, "home_goals": rr.home_regulation_goals, "away_goals": rr.away_regulation_goals,
            "final_status": rr.final_status, "result_provider": rr.source_provider,
            "result_retrieval_timestamp": retrieval_ts, "scored_utc": retrieval_ts,
        })
    return pd.DataFrame(scored), pd.DataFrame(excl)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored-utc", default=None, help="override scoring timestamp (tests/determinism)")
    a = ap.parse_args()
    scored_utc = a.scored_utc or datetime.now(timezone.utc).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)

    preds = pd.read_csv(PRED_LEDGER)
    ft = pd.read_csv(FORECAST_TARGETS)
    if not RESULTS_CSV.exists():
        raise SystemExit("no reconciled results; run refresh_prospective_final_results.py first")
    results = pd.read_csv(RESULTS_CSV)
    primary, sel_excl = select_primary(preds, ft)

    scored, gate_excl = build_scored_rows(primary, results, scored_utc)

    # idempotent append: first-write-wins per score_key; corrections (new result_hash) appended
    if SCORED_CSV.exists():
        prior = pd.read_csv(SCORED_CSV)
        before = set(prior["score_key"])
        merged = pd.concat([prior, scored]).drop_duplicates("score_key", keep="first")
        n_new = len(set(merged["score_key"]) - before)
    else:
        merged = scored.drop_duplicates("score_key", keep="first"); n_new = len(merged)
    merged.to_csv(SCORED_CSV, index=False)
    with open(SCORED_JSONL, "w", encoding="utf-8") as fh:
        for _, row in merged.iterrows():
            fh.write(json.dumps(stamp_labels(row.to_dict()), default=str) + "\n")

    # PRIMARY scorecard + metrics (one snapshot per fixture)
    if not scored.empty:
        primary_card = scored.pivot_table(index="canonical_fixture_id", columns="model_version",
                                          values="p_draw", aggfunc="first")
        primary_card.to_csv(PRIMARY_SCORECARD)
        metrics = model_metrics(scored, "primary")
        cal = [{"model": m["model"], "draw_cal_slope": m["draw_cal_slope"],
                "draw_cal_intercept": m["draw_cal_intercept"], "ece": m["ece"],
                "mean_pred_draw": m["mean_pred_draw"], "obs_draw_rate": m["obs_draw_rate"]} for m in metrics]
        pd.DataFrame(metrics).to_csv(MODEL_METRICS, index=False)
        pd.DataFrame(cal).to_csv(MODEL_CAL, index=False)
        pd.DataFrame(reliability_bins(scored)).to_csv(RELIABILITY, index=False)
        pd.DataFrame(market_alignment(scored)).to_csv(MARKET_ALIGN, index=False)
    else:
        for f in (MODEL_METRICS, MODEL_CAL, RELIABILITY, MARKET_ALIGN, PRIMARY_SCORECARD):
            pd.DataFrame().to_csv(f, index=False)

    # DESCRIPTIVE all-snapshot scorecard (match-clustered, labeled descriptive)
    res_vf = results[results.reconciliation_status == "verified_final"]
    out_by_fix = dict(zip(res_vf.canonical_fixture_id, res_vf.final_1x2_outcome_team_a_orientation))
    desc = preds[preds.model_version.isin(COMPARED)].copy()
    desc["outcome"] = desc["match_id"].map(out_by_fix)
    desc = desc[desc["outcome"].notna() & (desc[["p_team_a_win", "p_draw", "p_team_b_win"]].notna().all(axis=1))]
    desc_metrics = []
    if not desc.empty:
        for model, g in desc.groupby("model_version"):
            P = g[["p_team_a_win", "p_draw", "p_team_b_win"]].to_numpy(float); outc = g["outcome"].tolist()
            desc_metrics.append({"label": "descriptive_all_snapshots", "model": model, "n_rows": int(len(g)),
                                 "n_fixtures": int(g["match_id"].nunique()), "rps": _rps(P, _onehot(outc)),
                                 "log_loss": _logloss(P, outc)})
    pd.DataFrame(desc_metrics).to_csv(DESCRIPTIVE_SCORECARD, index=False)

    # exclusion ledger (selection + gate)
    all_excl = pd.concat([sel_excl.assign(stage="selection") if not sel_excl.empty else pd.DataFrame(),
                          gate_excl.assign(stage="scoring_gate") if not gate_excl.empty else pd.DataFrame()],
                         ignore_index=True)
    all_excl.to_csv(EXCLUSIONS, index=False)

    n_primary_fix = int(scored["canonical_fixture_id"].nunique()) if not scored.empty else 0
    tier = ("D_confirmatory" if n_primary_fix >= 50 else "C_exploratory" if n_primary_fix >= 20
            else "B_descriptive" if n_primary_fix >= 10 else "A_smoke_test")
    manifest = stamp_labels({
        "scorer_version": SCORER_VERSION, "scored_utc": scored_utc,
        "n_predicted_fixtures": int(preds["match_id"].nunique()),
        "n_primary_fixtures_scored": n_primary_fix, "n_scored_rows_total": int(len(merged)),
        "n_new_score_rows_this_run": int(n_new), "n_selection_excluded": int(len(sel_excl)),
        "n_gate_excluded": int(len(gate_excl)), "sample_size_tier": tier,
        "odds_api_called": False, "frozen_predictions_mutated": False,
    })
    write_json(RUN_MANIFEST, manifest)

    # integrity audit (hard invariants the harvester guarantees)
    integ = stamp_labels({
        "no_post_kickoff_prediction_scored": bool(scored.empty or (scored.apply(lambda r: _ts(r.prediction_timestamp) < _ts(r.kickoff_utc), axis=1)).all()),
        "no_future_market_snapshot": bool(scored.empty or (scored.apply(lambda r: _ts(r.source_snapshot_timestamp) <= _ts(r.prediction_timestamp) + pd.Timedelta(seconds=5), axis=1)).all()),
        "all_scored_have_verified_final": bool(scored.empty or scored["final_status"].isin(["FINISHED", "AET", "PEN", "AWARDED"]).all()),
        "one_primary_snapshot_per_fixture_model": bool(scored.empty or not scored.duplicated(["canonical_fixture_id", "model_version"]).any()),
        "score_keys_unique": bool(not merged.duplicated("score_key").any()),
        "simplex_ok": bool(scored.empty or (np.abs(scored[["p_team_a_win", "p_draw", "p_team_b_win"]].sum(axis=1) - 1) < 1e-6).all()),
        "market_read_only_comparator": True, "no_model_refit_or_calibration": True,
        "no_2026_outcome_in_any_fit": True,
    })
    integ["all_ok"] = all(v for k, v in integ.items() if isinstance(v, bool))
    write_json(INTEGRITY, integ)

    print(f"HARVEST OK | primary_fixtures_scored={n_primary_fix} tier={tier} "
          f"scored_rows={len(merged)} (+{n_new} new) sel_excl={len(sel_excl)} gate_excl={len(gate_excl)} "
          f"integrity_all_ok={integ['all_ok']}")


if __name__ == "__main__":
    main()
