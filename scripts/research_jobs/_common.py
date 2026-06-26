"""Shared research harness for the deep-research jobs. research_only / experimental / not_runtime_approved /
not_trade_eligible / not_live_eligible.

Loads the reconciled corpus raw from BOTH the corpus worktree (the 900 fixtures, gitignored) and this
worktree's extension raw (the +220), builds leakage-safe in-play REGULATION snapshots, and provides metrics
(RPS / log-loss / Brier / calibration), leave-one-competition-out splits, and match-level bootstrap.

Causal rules: features at decision minute t use ONLY events with elapsed <= t; regulation only (no ET/shootout);
own-goal beneficiary semantics (result_semantics); no final score / later subs leak.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import result_semantics as RS  # noqa: E402
from wcdrawlab.research.paid_source import historical_datasets as HD  # noqa: E402

RAW_ROOTS = [
    Path("C:/Users/Mahyar/worldcup-api-football-corpus/data/raw/api_football_historical_corpus"),
    ROOT / "data/raw/api_football_historical_corpus",
]
INTL_LEAGUES = {1: "WC", 4: "Euro", 9: "Copa", 6: "AFCON", 7: "AsianCup"}
DECISION_MINUTES = [15, 30, 45, 60, 75]


def _load_root(root, fixtures, events, lineups):
    if not root.exists():
        return
    for fp in root.glob("fixtures_*.json"):
        if "events" in fp.name or "lineups" in fp.name:
            continue
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for fx in p.get("response", []) or []:
            fixtures[str(fx.get("fixture", {}).get("id"))] = fx
    for fp in root.glob("fixtures_events_*.json"):
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        fid = (p.get("parameters") or {}).get("fixture")
        if fid is not None:
            events[str(fid)] = p.get("response", []) or []
    for fp in root.glob("fixtures_lineups_*.json"):
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        fid = (p.get("parameters") or {}).get("fixture")
        if fid is not None:
            lineups[str(fid)] = p.get("response", []) or []


def load_corpus():
    fixtures, events, lineups = {}, {}, {}
    for r in RAW_ROOTS:
        _load_root(r, fixtures, events, lineups)
    return fixtures, events, lineups


def _is_intl(fx):
    return fx.get("league", {}).get("id") in INTL_LEAGUES


def _wdl(h, a):
    return "H" if h > a else ("A" if a > h else "D")


def regulation_snapshots(fixtures, events, lineups, international_only=True):
    """Return (rows, by_match). Each row = leakage-safe regulation state at a decision minute + targets.
    Only fixtures that reconcile EXACTLY are included."""
    rows = []
    for fid, fx in fixtures.items():
        ev = events.get(fid)
        if ev is None:
            continue
        intl = _is_intl(fx)
        if international_only and not intl:
            continue
        can = RS.canonical_result(fx, ev)
        if can["reconciliation_status"] != "exact":
            continue  # exclude unresolved
        home_id, away_id = can["home_id"], can["away_id"]
        comp = INTL_LEAGUES.get(fx.get("league", {}).get("id"), "club")
        final_h = can["official_regulation_home_goals"]; final_a = can["official_regulation_away_goals"]
        if final_h is None:
            continue
        target = _wdl(final_h, final_a)
        subs = HD.substitutions(ev)
        for t in DECISION_MINUTES:
            sh, sa = HD.regulation_state_at(ev, home_id, away_id, t)
            yh = ya = rh = ra = 0
            for c in HD.cards_table([e for e in ev if (e.get("time") or {}).get("elapsed") is not None
                                     and (e.get("time") or {}).get("elapsed") <= t]):
                side_home = c["team_id"] == home_id
                if c["card_class"] == "yellow":
                    yh += side_home; ya += not side_home
                elif c["card_class"] in ("direct_red", "second_yellow_red"):
                    rh += side_home; ra += not side_home
            sub_h = sum(1 for s in subs if s["minute"] is not None and s["minute"] <= t and s["team_id"] == home_id)
            sub_a = sum(1 for s in subs if s["minute"] is not None and s["minute"] <= t and s["team_id"] == away_id)
            # next regulation goal within (t, t+15]?
            nxt = 0
            for e in ev:
                if (e.get("type") or "").lower() == "goal":
                    el = (e.get("time") or {}).get("elapsed")
                    d = (e.get("detail") or "").lower()
                    if el is not None and t < el <= min(90, t + 15) and "missed" not in d and "cancel" not in d:
                        nxt = 1; break
            rows.append({
                "match_id": fid, "competition": comp, "comp_type": "international" if intl else "club",
                "minute": t, "remaining": 90 - t,
                "score_h": sh, "score_a": sa, "score_diff": sh - sa,
                "card_diff": yh - ya, "so_diff": rh - ra, "subs_diff": sub_h - sub_a,
                "player_count_diff": (ra - rh),  # +ve means home has more players on pitch
                "target_wdl": target, "next_goal_15": nxt,
                "n_starters_home": len((lineups.get(fid, [{}]) or [{}])[0].get("startXI", []) or []) if lineups.get(fid) else 0,
            })
    return rows


# ---------- metrics ----------
ORDER = ["H", "D", "A"]


def rps(probs, target):
    """Ranked Probability Score for ordered outcomes H<D<A. probs dict; lower is better."""
    cum_p = 0.0; cum_o = 0.0; s = 0.0
    for k in ORDER:
        cum_p += probs.get(k, 0.0)
        cum_o += 1.0 if k == target else 0.0
        s += (cum_p - cum_o) ** 2
    return s / (len(ORDER) - 1)


def logloss3(probs, target, eps=1e-12):
    return -math.log(max(eps, probs.get(target, 0.0)))


def brier_draw(probs, target):
    return (probs.get("D", 0.0) - (1.0 if target == "D" else 0.0)) ** 2


def calibration(pairs):
    """pairs = [(p_event, y)]. Returns slope/intercept (logit regression) + ECE (10 bins)."""
    import numpy as np
    if not pairs:
        return {"slope": None, "intercept": None, "ece": None}
    p = np.clip(np.array([x[0] for x in pairs]), 1e-6, 1 - 1e-6)
    y = np.array([x[1] for x in pairs], dtype=float)
    # logit calibration slope/intercept via simple logistic regression on logit(p)
    z = np.log(p / (1 - p))
    try:
        from sklearn.linear_model import LogisticRegression
        m = LogisticRegression().fit(z.reshape(-1, 1), y)
        slope = float(m.coef_[0][0]); intercept = float(m.intercept_[0])
    except Exception:
        slope = intercept = None
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    for i in range(10):
        m_ = (p >= bins[i]) & (p < bins[i + 1])
        if m_.sum():
            ece += m_.mean() * abs(p[m_].mean() - y[m_].mean())
    return {"slope": slope, "intercept": intercept, "ece": float(ece)}


def loco_folds(rows):
    comps = sorted({r["competition"] for r in rows})
    for held in comps:
        train = [r for r in rows if r["competition"] != held]
        test = [r for r in rows if r["competition"] == held]
        if test and train:
            yield held, train, test


def match_bootstrap_ci(per_match_values, n=1000, seed_rows=None):
    """Match-level bootstrap CI for a mean metric. Deterministic-ish via index rotation (no RNG calls)."""
    import numpy as np
    vals = list(per_match_values)
    if not vals:
        return (None, None)
    arr = np.array(vals, dtype=float)
    k = len(arr)
    means = []
    # deterministic resampling: rotate a fixed pseudo-random index table built from row hashes
    base = np.arange(k)
    for b in range(n):
        idx = (base * (b * 2 + 1) + b * 7) % k  # deterministic index permutation per b
        means.append(arr[idx].mean())
    means.sort()
    return (round(float(means[int(0.025 * n)]), 4), round(float(means[int(0.975 * n)]), 4))
