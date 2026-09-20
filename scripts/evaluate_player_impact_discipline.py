"""Evaluate the player-impact DISCIPLINE families (C0 base-rate; C1 +discipline history, gated on
>=150 positive examples) leave-one-competition-out over international competitions, match-level bootstrap CIs.
research_only / experimental.

The discipline target is a leakage-safe binary "a CARD is shown in the next 15 regulation minutes (t, t+15]",
derived directly from the corpus using ONLY events with elapsed <= t for features and elapsed in (t, t+15]
for the target. C1 is fit only when the TRAIN folds collectively carry >=150 positives (preregistered gate);
otherwise C1 is SKIPPED and only C0 is reported.

Models are fit INSIDE each training fold only (regularization chosen on train). Discipline-history feature
columns degrade gracefully (unknown indicator) when absent.

Usage:
    python scripts/evaluate_player_impact_discipline.py --run-dir <dir> [--snapshots <discipline_rows.json>]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research_jobs"))

import _common as C  # noqa: E402
from wcdrawlab.research import player_impact_models as PIM  # noqa: E402
from wcdrawlab.research.paid_source import result_semantics as RS  # noqa: E402
from wcdrawlab.research.paid_source import historical_datasets as HD  # noqa: E402

TARGET = "discipline_event"
DECISION_MINUTES = C.DECISION_MINUTES
INTL = C.INTL_LEAGUES


def _cards_up_to(events, t):
    return HD.cards_table([e for e in events
                           if (e.get("time") or {}).get("elapsed") is not None
                           and (e.get("time") or {}).get("elapsed") <= t])


def _card_in_window(events, lo, hi):
    """1 if any card event with lo < elapsed <= hi (regulation only)."""
    for e in events:
        if (e.get("type") or "").lower() != "card":
            continue
        el = (e.get("time") or {}).get("elapsed")
        if el is not None and lo < el <= min(90, hi):
            return 1
    return 0


def build_discipline_rows() -> list:
    """Leakage-safe per-(match, minute) discipline rows for international competitions only.

    Features at minute t use only events elapsed<=t; the target uses (t, t+15]. Prior-discipline-history
    feature columns (team_card_rate_prior / opp_card_rate_prior / fouls_diff) are attached when derivable
    from the corpus and otherwise omitted (the model imputes + flags them as unknown)."""
    fixtures, events_all, lineups = C.load_corpus()
    rows = []
    for fid, fx in fixtures.items():
        if fx.get("league", {}).get("id") not in INTL:
            continue
        ev = events_all.get(fid)
        if ev is None:
            continue
        can = RS.canonical_result(fx, ev)
        if can["reconciliation_status"] != "exact":
            continue
        home_id, away_id = can["home_id"], can["away_id"]
        comp = INTL.get(fx.get("league", {}).get("id"))
        for t in DECISION_MINUTES:
            cards = _cards_up_to(ev, t)
            yh = ya = rh = ra = 0
            for c in cards:
                side_home = c["team_id"] == home_id
                if c["card_class"] == "yellow":
                    yh += side_home; ya += not side_home
                elif c["card_class"] in ("direct_red", "second_yellow_red"):
                    rh += side_home; ra += not side_home
            row = {
                "match_id": fid, "competition": comp, "comp_type": "international",
                "minute": t, "remaining": 90 - t,
                "card_diff": yh - ya, "so_diff": rh - ra,
                # discipline-history features derivable from in-match accumulation so far (leakage-safe);
                # richer prior-history columns are supplied per-row by player_history when available.
                "team_card_rate_prior": (yh + rh) / max(1, t),
                "opp_card_rate_prior": (ya + ra) / max(1, t),
                TARGET: _card_in_window(ev, t, t + 15),
            }
            rows.append(row)
    return rows


def load_rows(snapshots: Path | None) -> list:
    if snapshots and Path(snapshots).exists():
        return json.loads(Path(snapshots).read_text(encoding="utf-8"))
    return build_discipline_rows()


def evaluate(rows: list) -> dict:
    total_pos = int(sum(int(r[TARGET]) for r in rows))
    base_rate = total_pos / max(1, len(rows))
    # decide gate once on the full pool (also re-checked per train fold inside the model factory)
    names = ["C0", "C1"]
    agg = {m: {"brier": [], "ll": [], "cal": [], "by_match": defaultdict(list)} for m in names}
    c1_fit_folds = 0
    n_folds = 0
    for held, train, test in C.loco_folds(rows):
        n_folds += 1
        built = PIM.discipline_predictors(train, target_key=TARGET)
        preds = built["predictors"]
        if built["C1_gate_open"]:
            c1_fit_folds += 1
        for name in names:
            if name not in preds:
                continue
            fn = preds[name]
            for r in test:
                p = min(max(float(fn(r)), 1e-9), 1 - 1e-9)
                y = int(r[TARGET])
                br = (p - y) ** 2
                ll = -(y * math.log(p) + (1 - y) * math.log(1 - p))
                agg[name]["brier"].append(br)
                agg[name]["ll"].append(ll)
                agg[name]["cal"].append((p, y))
                agg[name]["by_match"][r["match_id"]].append(br)
    out = {}
    for name in names:
        d = agg[name]
        n = len(d["brier"])
        if n == 0:
            out[name] = {"status": "SKIPPED_below_gate" if name == "C1" else "no_rows", "n_rows": 0}
            continue
        per_match = [sum(v) / len(v) for v in d["by_match"].values()]
        out[name] = {
            "n_rows": n,
            "n_matches": len(per_match),
            "brier": round(sum(d["brier"]) / n, 4),
            "logloss": round(sum(d["ll"]) / n, 4),
            "calibration": C.calibration(d["cal"]),
            "brier_match_ci95": C.match_bootstrap_ci(per_match),
        }
    scored = [k for k in names if out[k].get("n_rows")]
    leader = min(scored, key=lambda k: out[k]["brier"]) if scored else None
    return {"family": "player_impact_discipline", "model_version": PIM.MODEL_VERSION,
            "base_rate": round(base_rate, 4), "n_positives_total": total_pos,
            "gate_threshold": PIM.DISCIPLINE_POSITIVE_GATE,
            "C1_fit_in_n_folds": c1_fit_folds, "n_folds": n_folds,
            "models": out, "leader_by_brier": leader, "research_only": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--snapshots", default=None)
    args = ap.parse_args()
    rd = Path(args.run_dir)
    rd.mkdir(parents=True, exist_ok=True)
    rows = load_rows(Path(args.snapshots) if args.snapshots else None)
    comps = sorted({r["competition"] for r in rows})
    if len(comps) < 2:
        res = {"status": "skipped", "reason": f"need >=2 international competitions for LOCO (have {comps})",
               "family": "player_impact_discipline", "research_only": True}
    else:
        res = evaluate(rows)
        res["status"] = "complete"
        res["competitions"] = comps
    (rd / "player_impact_discipline.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({"status": res.get("status"), "leader_by_brier": res.get("leader_by_brier"),
                      "n_positives_total": res.get("n_positives_total"),
                      "out": str(rd / "player_impact_discipline.json")}))


if __name__ == "__main__":
    main()
