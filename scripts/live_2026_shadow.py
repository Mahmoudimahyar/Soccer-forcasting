"""Prospective live-2026 SHADOW evaluation (read-only research; nothing promoted; B1 stays approved).

Frozen models (weights fixed for the whole evaluation):
  M1 = B1 Elo (approved)   M2 = market no-vig consensus
  M3 = 0.75*B1 + 0.25*mkt  M4 = 0.50/0.50   M5 = 0.25*B1 + 0.75*mkt

Modes:
  freeze : produce immutable pre-kickoff predictions for UPCOMING matches from the latest live odds
           snapshot + forecast targets, appended to outputs/research/live_2026_shadow_predictions.csv.
  score  : after results are known, score saved pre-match predictions -> metrics/calibration CSVs.

No live trading; candidate.py untouched. Predictions are append-only and never modified after kickoff.
Usage: python scripts/live_2026_shadow.py freeze   |   python scripts/live_2026_shadow.py score
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.evaluation import metric_report, normalize_probs  # noqa: E402
from wcdrawlab.ratings import ternary_elo_probs  # noqa: E402
from wcdrawlab.research.runner import draw_calibration_error  # noqa: E402
from wcdrawlab.research.inplay_replay import risk_band  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402

OUT = ROOT / "outputs" / "research"; OUT.mkdir(parents=True, exist_ok=True)
PRED = OUT / "live_2026_shadow_predictions.csv"
RAW = ROOT / "data/raw/odds/live_2026"
NORM = ROOT / "data/processed/odds_live_2026"; NORM.mkdir(parents=True, exist_ok=True)
BLENDS = {"M1_B1": 1.0, "M3_75_25": 0.75, "M4_50_50": 0.50, "M5_25_75": 0.25}  # B1 weight; M2 handled separately


def _novig(event):
    """no-vig consensus oriented to (home, away); returns (p_home,p_draw,p_away,n_books,overround)."""
    rows = []
    for bk in event.get("bookmakers", []):
        for mk in bk.get("markets", []):
            if mk.get("key") != "h2h":
                continue
            out = {o["name"]: o["price"] for o in mk.get("outcomes", []) if o.get("price")}
            h, a = event.get("home_team"), event.get("away_team")
            if h in out and a in out and "Draw" in out:
                imp = np.array([1/out[h], 1/out["Draw"], 1/out[a]])
                rows.append((imp, imp.sum()))
    if not rows:
        return None
    probs = np.mean([r[0]/r[0].sum() for r in rows], axis=0)
    return float(probs[0]), float(probs[1]), float(probs[2]), len(rows), float(np.mean([r[1] for r in rows]))


def load_latest_snapshot():
    files = sorted(glob.glob(str(RAW / "*.json")))
    if not files:
        return None, None
    snap = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
    ts = snap.get("snapshot_utc"); data = snap.get("data", [])
    by_pair = {}
    for ev in data:
        nv = _novig(ev)
        if nv is None:
            continue
        h = canonical_team_name(ev.get("home_team", "")); a = canonical_team_name(ev.get("away_team", ""))
        by_pair[frozenset((h, a))] = {"home": h, "away": a, "p_home": nv[0], "p_draw": nv[1],
                                      "p_away": nv[2], "n_books": nv[3], "overround": nv[4],
                                      "commence": ev.get("commence_time")}
    return ts, by_pair


def _envelope_row(match, model, snap_ts, p, mkt, n_books, overround, completeness, pred_ts):
    p = normalize_probs(np.array([p]))[0]
    ent = float(-(p * np.log(np.clip(p, 1e-12, 1))).sum() / np.log(3))
    n_eff = 50.0
    se = np.sqrt(p * (1 - p) / n_eff)
    return {
        "prediction_timestamp": pred_ts, "match_id": match["match_id"],
        "kickoff_utc": match["kickoff_utc"], "model_version": model,
        "approval_status": "approved" if model == "M1_B1" else "shadow",
        "source_snapshot_timestamp": snap_ts,
        "p_team_a_win": p[0], "p_draw": p[1], "p_team_b_win": p[2],
        "p_a_se": se[0], "p_draw_se": se[1], "p_b_se": se[2],
        "p_draw_ci_low": max(0.0, p[1] - 1.96 * se[1]), "p_draw_ci_high": min(1.0, p[1] + 1.96 * se[1]),
        "entropy": ent, "risk_band": risk_band(ent), "data_completeness": completeness,
        "p_a_market": (mkt[0] if mkt is not None else None),
        "p_draw_market": (mkt[1] if mkt is not None else None),
        "p_b_market": (mkt[2] if mkt is not None else None), "n_books": n_books, "overround": overround,
    }


def freeze():
    tg = pd.read_csv(ROOT / "data/processed/forecast_targets_2026.csv", parse_dates=["kickoff_utc"])
    now = pd.Timestamp.utcnow()
    up = tg[tg.kickoff_utc > now].copy()
    snap_ts, snap = load_latest_snapshot()
    pred_ts = now.isoformat()
    rows = []
    for m in up.itertuples():
        match = {"match_id": m.match_id, "kickoff_utc": m.kickoff_utc.isoformat()}
        elo = normalize_probs(ternary_elo_probs(np.array([float(m.elo_delta)])))[0]
        ca, cb = canonical_team_name(m.team_a), canonical_team_name(m.team_b)
        s = snap.get(frozenset((ca, cb))) if snap else None
        if s is not None and s["n_books"] >= 1:
            # orient market to team_a
            if s["home"] == ca:
                mkt = np.array([s["p_home"], s["p_draw"], s["p_away"]])
            else:
                mkt = np.array([s["p_away"], s["p_draw"], s["p_home"]])
            n_books, overround, completeness = s["n_books"], s["overround"], (1.0 if s["n_books"] >= 5 else 0.6)
        elif not bool(getattr(m, "market_is_missing", True)):
            mkt = np.array([m.p_a_market, m.p_draw_market, m.p_b_market]); n_books, overround, completeness = None, None, 0.5
        else:
            mkt = None; n_books = overround = None; completeness = 0.3
        # M1-M5
        rows.append(_envelope_row(match, "M1_B1", snap_ts, elo, mkt, n_books, overround, 1.0, pred_ts))
        if mkt is not None:
            rows.append(_envelope_row(match, "M2_market", snap_ts, mkt, mkt, n_books, overround, completeness, pred_ts))
            for name, wb1 in [("M3_75_25", 0.75), ("M4_50_50", 0.5), ("M5_25_75", 0.25)]:
                rows.append(_envelope_row(match, name, snap_ts, wb1 * elo + (1 - wb1) * mkt, mkt, n_books, overround, completeness, pred_ts))
    new = pd.DataFrame(rows)
    # normalized snapshot
    if snap:
        pd.DataFrame([{**{"snapshot_utc": snap_ts}, **{k: v for k, v in s.items() if k != "commence"}, "commence": s["commence"]}
                      for s in snap.values()]).to_csv(NORM / f"{(snap_ts or 'snap').replace(':','').replace('-','')}.csv", index=False)
    # append-only, immutable: drop (match_id, model_version, source_snapshot_timestamp) already present
    if PRED.exists():
        old = pd.read_csv(PRED)
        key = ["match_id", "model_version", "source_snapshot_timestamp"]
        merged = pd.concat([old, new]).drop_duplicates(subset=key, keep="first")
    else:
        merged = new
    merged.to_csv(PRED, index=False)
    print(f"freeze: snapshot={snap_ts} | upcoming matches={len(up)} | new rows={len(new)} | total preds={len(merged)}")
    print(f"  models per match: M1-M5 where market present; M1 only otherwise. Predictions immutable.")


def score():
    if not PRED.exists():
        print("no predictions yet"); return
    preds = pd.read_csv(PRED)
    res = pd.read_csv(ROOT / "data/processed/results_2026_footballdata.csv")
    fin = res[res.get("status", "FINISHED").astype(str).str.upper() == "FINISHED"].copy() if "status" in res else res
    fin["pair"] = fin.apply(lambda r: frozenset((canonical_team_name(r.team_a), canonical_team_name(r.team_b))), axis=1)
    fin["oc"] = np.select([fin.goals_a > fin.goals_b, fin.goals_a == fin.goals_b], ["A", "D"], default="B")
    # map predictions to outcomes via match_id -> teams (from targets)
    tg = pd.read_csv(ROOT / "data/processed/forecast_targets_2026.csv")
    mid2pair = {r.match_id: frozenset((canonical_team_name(r.team_a), canonical_team_name(r.team_b))) for r in tg.itertuples()}
    out_by_pair = dict(zip(fin.pair, fin.oc))
    preds["pair"] = preds.match_id.map(mid2pair)
    preds["outcome"] = preds.pair.map(out_by_pair)
    scored = preds[preds.outcome.notna()].copy()
    print(f"score: predictions={len(preds)} | scored (finished)={len(scored)}")
    recs, cal = [], []
    for model, g in scored.groupby("model_version"):
        P = g[["p_team_a_win", "p_draw", "p_team_b_win"]].to_numpy()
        rep = metric_report(g.outcome.to_numpy(), P)
        recs.append({"model": model, "n": len(g), "rps": rep["rps"], "log_loss": rep["log_loss"],
                     "draw_brier": rep["draw_brier"],
                     "draw_cal_error": draw_calibration_error(g.outcome.to_numpy(), P[:, 1])})
    pd.DataFrame(recs).to_csv(OUT / "live_2026_shadow_metrics.csv", index=False)
    pd.DataFrame(cal).to_csv(OUT / "live_2026_shadow_calibration.csv", index=False)
    if recs:
        print(pd.DataFrame(recs).to_string(index=False))
    else:
        print("  (no finished predicted matches yet; metrics populate as MD2/MD3 complete)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "freeze"
    (freeze if mode == "freeze" else score)()
