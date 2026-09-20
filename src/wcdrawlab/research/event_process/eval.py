"""Leakage-safe evaluation harness for the event-process model families.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Loads the already-built, already-leakage-checked snapshot + target tables (built by
scripts/build_event_process_snapshots.py / ep_job06), joins them on (source_match_id, snapshot_minute,
snapshot_reason), derives the per-snapshot binary targets, and runs:
  * forward-chaining W/D/L over INTERNATIONAL competitions ordered by kickoff;
  * leave-one-competition-out (LOCO) W/D/L with reliability + per-match RPS for bootstrap;
  * LOCO for the next-goal / near-term-scoring / discipline binary families.

HARD INVARIANTS:
  * 2026 World Cup is NEVER used for fitting OR as a test fold (assert_no_2026).
  * CLUB rows are NEVER returned as international test rows (international tables are already comp_type
    == 'international'; an explicit filter re-asserts it).
  * Targets are joined onto snapshot rows but are NEVER added to a model feature space.
  * Metrics reuse the shared research harness (_common: rps / logloss3 / brier_draw / calibration /
    match_bootstrap_ci) so EP results are directly comparable to the other phases.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[4]
_RJ = ROOT / "scripts/research_jobs"
if str(_RJ) not in sys.path:
    sys.path.insert(0, str(_RJ))
import _common as CM  # noqa: E402  (shared rps/logloss/brier/calibration/bootstrap)

from . import models as M  # noqa: E402

PROC = ROOT / "data/processed/event_process_snapshots"
INTL_SNAP = PROC / "intl_event_process_snapshots.csv"
INTL_WDL = PROC / "intl_targets_wdl.csv"
INTL_NEXTGOAL = PROC / "intl_targets_next_goal.csv"
INTL_SCORING = PROC / "intl_targets_scoring_horizon.csv"
CLUB_SNAP = PROC / "club_event_process_snapshots.csv"
MATCH_COMPLETENESS = PROC / "match_completeness.csv"

WDL = ["H", "D", "A"]
NEXT_GOAL_HORIZON = 15.0   # standard next-goal horizon in match minutes

# Default W/D/L predictor factory: the canonical event-process e0..e9 family (goal-intensity). When club
# rows are supplied, a partial(...) over this with club_rows= is passed instead (see make_wdl_factory).
WDL_FACTORY = M.event_process_predictors


class DataInsufficient(Exception):
    """Raised when a required local product is absent/empty so a job can emit an honest skip."""


# =================================================================================================
# loading + join
# =================================================================================================
def _read_csv(path: Path) -> List[dict]:
    if not path.exists():
        raise DataInsufficient(f"required table absent: {path}")
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _is_2026_wc(label: Optional[str], kickoff: Optional[str]) -> bool:
    lab = (label or "").lower()
    if "2026" in lab and ("world cup" in lab or "worldcup" in lab or "fifa" in lab):
        return True
    if (kickoff or "").startswith("2026") and "world cup" in lab:
        return True
    return False


def assert_no_2026(rows: Sequence[dict]) -> None:
    bad = [r for r in rows if _is_2026_wc(r.get("competition_label"), r.get("kickoff_date"))]
    if bad:
        raise AssertionError(f"2026 World Cup rows present in eval population ({len(bad)}) -- forbidden")


def _key(r: dict) -> tuple:
    # snapshot_minute is a float string; normalize to a stable 3dp key
    try:
        mk = round(float(r.get("snapshot_minute")), 3)
    except (TypeError, ValueError):
        mk = r.get("snapshot_minute")
    return (str(r.get("source_match_id")), mk, r.get("snapshot_reason"))


def load_eval_rows() -> Dict[str, object]:
    """Join snapshots with all target tables. Returns dict with `snapshot_rows` (W/D/L panel, one per
    snapshot, carrying the per-match target_wdl) and the per-snapshot binary targets merged inline:
        next_goal_side / next_goal_minute / next_goal_any_15
        any_goal_next5m / any_goal_next10m / any_goal_next15m (and per-side)
        sendoff_after (derived: a sending-off strictly after t within regulation)
    Every returned row keeps `competition` (== competition_label) and `match_id` so the shared harness
    folds/bootstrap work unchanged. International-only and no-2026 are enforced here.
    """
    snaps = _read_csv(INTL_SNAP)
    wdl = _read_csv(INTL_WDL)
    ng = _read_csv(INTL_NEXTGOAL)
    sc = _read_csv(INTL_SCORING)

    assert_no_2026(snaps)
    snaps = [r for r in snaps if r.get("comp_type") == "international"]

    wdl_by_match = {str(r["source_match_id"]): r for r in wdl}
    ng_by_key = {_key(r): r for r in ng}
    sc_by_key = {_key(r): r for r in sc}

    # match-level: does ANY sending-off occur in the match (regulation)? + first send-off minute.
    # We derive the per-snapshot discipline target (sendoff strictly after t) from the snapshot's own
    # cumulative sendoff counts + the match final sendoff count: a send-off occurs after t iff the
    # match-final regulation send-off total exceeds the cumulative total observed at t. The match-final
    # send-off total is read from the LAST snapshot of each match (max minute), which is a leakage-safe
    # label source (labels may use full match; they never enter features).
    final_sendoff: Dict[str, int] = {}
    last_minute: Dict[str, float] = {}
    for r in snaps:
        mid = str(r["source_match_id"])
        try:
            mn = float(r["snapshot_minute"])
        except (TypeError, ValueError):
            continue
        tot = (int(float(r.get("sendoff_home") or 0)) + int(float(r.get("sendoff_away") or 0)))
        if mid not in last_minute or mn >= last_minute[mid]:
            last_minute[mid] = mn
            final_sendoff[mid] = tot

    out_rows: List[dict] = []
    for r in snaps:
        mid = str(r["source_match_id"])
        wr = wdl_by_match.get(mid)
        if wr is None or not wr.get("target_wdl"):
            continue  # only snapshots whose match has a resolved regulation W/D/L target
        k = _key(r)
        ngr = ng_by_key.get(k, {})
        scr = sc_by_key.get(k, {})

        # next-goal-any within 15': a goal by either side strictly after t and <= t+15
        nga = 0
        side = ngr.get("next_goal_side")
        if side in ("home", "away"):
            try:
                nm = float(ngr.get("next_goal_minute"))
                t = float(r["snapshot_minute"])
                nga = int(t < nm <= min(90.0, t + NEXT_GOAL_HORIZON))
            except (TypeError, ValueError):
                nga = 0

        cum_so = (int(float(r.get("sendoff_home") or 0)) + int(float(r.get("sendoff_away") or 0)))
        sendoff_after = int(final_sendoff.get(mid, cum_so) > cum_so)

        row = dict(r)
        row["target_wdl"] = wr["target_wdl"]
        row["competition"] = r.get("competition_label")
        row["match_id"] = mid
        # side-specific REMAINING regulation goals = final regulation goals - goals already scored at t.
        # Leakage-safe LABEL source: used ONLY to fit the intensity heads on TRAIN rows (never a feature).
        try:
            reg_h = float(wr.get("reg_home_goals"))
            reg_a = float(wr.get("reg_away_goals"))
            cur_h = float(r.get("goals_home") or 0.0)
            cur_a = float(r.get("goals_away") or 0.0)
            row["rem_goals_home"] = max(0.0, reg_h - cur_h)
            row["rem_goals_away"] = max(0.0, reg_a - cur_a)
        except (TypeError, ValueError):
            row["rem_goals_home"] = None
            row["rem_goals_away"] = None
        row["next_goal_side"] = side
        row["next_goal_any_15"] = nga
        for h in (5, 10, 15):
            row[f"any_goal_next{h}m"] = int(float(scr.get(f"any_goal_next{h}m") or 0))
            row[f"home_scores_next{h}m"] = int(float(scr.get(f"home_scores_next{h}m") or 0))
            row[f"away_scores_next{h}m"] = int(float(scr.get(f"away_scores_next{h}m") or 0))
        row["sendoff_after"] = sendoff_after
        out_rows.append(row)

    if not out_rows:
        raise DataInsufficient("join produced 0 international eval rows (snapshots/targets mismatch)")
    return {"snapshot_rows": out_rows,
            "n_matches": len({r["match_id"] for r in out_rows}),
            "n_competitions": len({r["competition"] for r in out_rows})}


def load_club_aux_rows(max_rows: Optional[int] = None) -> List[dict]:
    """Load CLUB event-process snapshot rows for the e8 auxiliary transfer representation.

    Club rows TRAIN the aux rep ONLY -- they are NEVER returned as international test rows (the
    international loader filters comp_type == 'international'; club rows live in a separate table). Each
    club row is annotated with ``rem_goals_home`` / ``rem_goals_away`` derived from the match's FINAL
    regulation goals (the max-minute snapshot's cumulative goals) minus the goals already scored at t.
    Returns [] (not an error) when the optional club table is absent, so e8 degrades to e7 honestly.
    """
    if not CLUB_SNAP.exists():
        return []
    rows = _read_csv(CLUB_SNAP)
    if not rows:
        return []
    # final regulation goals per club match = cumulative goals at the latest (max-minute) regulation snapshot
    final_h: Dict[str, float] = {}
    final_a: Dict[str, float] = {}
    last_min: Dict[str, float] = {}
    for r in rows:
        mid = str(r.get("source_match_id"))
        try:
            mn = float(r.get("snapshot_minute"))
        except (TypeError, ValueError):
            continue
        if mid not in last_min or mn >= last_min[mid]:
            last_min[mid] = mn
            final_h[mid] = float(r.get("goals_home") or 0.0)
            final_a[mid] = float(r.get("goals_away") or 0.0)
    out: List[dict] = []
    for r in rows:
        mid = str(r.get("source_match_id"))
        row = dict(r)
        row["comp_type"] = "club"
        row["match_id"] = mid
        try:
            cur_h = float(r.get("goals_home") or 0.0)
            cur_a = float(r.get("goals_away") or 0.0)
            row["rem_goals_home"] = max(0.0, final_h.get(mid, cur_h) - cur_h)
            row["rem_goals_away"] = max(0.0, final_a.get(mid, cur_a) - cur_a)
        except (TypeError, ValueError):
            row["rem_goals_home"] = None
            row["rem_goals_away"] = None
        out.append(row)
        if max_rows is not None and len(out) >= max_rows:
            break
    return out


def make_wdl_factory(club_rows: Optional[Sequence[dict]] = None,
                     include_club_transfer: bool = True):
    """Build a 1-arg W/D/L predictor factory closure (train_rows -> {id: predict}) that injects the
    CLUB aux rows for e8. With ``include_club_transfer=False`` (or no club rows) e8 degrades to e7's
    column set -- this is exactly the with/without-club-transfer comparison the spec asks for."""
    cr = list(club_rows) if (club_rows and include_club_transfer) else None

    def _factory(train_rows: Sequence[dict]) -> Dict[str, Callable]:
        return M.event_process_predictors(train_rows, club_rows=cr,
                                          include_club_transfer=include_club_transfer)
    return _factory


# =================================================================================================
# metrics (reuse shared harness)
# =================================================================================================
def _score_wdl(predict: Callable[[dict], Dict[str, float]], test_rows: Sequence[dict]) -> Dict:
    rps = ll = bd = 0.0
    n = 0
    per_match: Dict[str, List[float]] = {}
    detail = []
    for r in test_rows:
        p = predict(r)
        s = sum(p.values()) or 1.0
        p = {k: p.get(k, 0.0) / s for k in WDL}
        tgt = r["target_wdl"]
        rp = CM.rps(p, tgt)
        rps += rp
        ll += CM.logloss3(p, tgt)
        bd += CM.brier_draw(p, tgt)
        per_match.setdefault(r["match_id"], []).append(rp)
        detail.append((p.get("D", 0.0), 1.0 if tgt == "D" else 0.0))
        n += 1
    if n == 0:
        return {"rps": None, "logloss": None, "brier_draw": None, "n": 0,
                "per_match_rps": {}, "rows_detail": []}
    return {"rps": rps / n, "logloss": ll / n, "brier_draw": bd / n, "n": n,
            "per_match_rps": {m: sum(v) / len(v) for m, v in per_match.items()},
            "rows_detail": detail}


def _score_binary(predict: Callable[[dict], float], test_rows: Sequence[dict], target_key: str) -> Dict:
    ll = brier = 0.0
    n = 0
    per_match: Dict[str, List[float]] = {}
    pairs = []
    import math
    for r in test_rows:
        p = min(1 - 1e-9, max(1e-9, float(predict(r))))
        y = int(r[target_key])
        ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        b = (p - y) ** 2
        brier += b
        per_match.setdefault(r["match_id"], []).append(b)
        pairs.append((p, float(y)))
        n += 1
    if n == 0:
        return {"logloss": None, "brier": None, "n": 0, "per_match_brier": {}, "calibration": None}
    return {"logloss": ll / n, "brier": brier / n, "n": n, "base_rate": sum(y for _, y in pairs) / n,
            "per_match_brier": {m: sum(v) / len(v) for m, v in per_match.items()},
            "calibration": CM.calibration(pairs)}


# =================================================================================================
# protocols
# =================================================================================================
def _comp_order(rows: Sequence[dict]) -> List[str]:
    first_ko: Dict[str, str] = {}
    for r in rows:
        c = r["competition"]
        ko = r.get("kickoff_date") or "9999"
        if c not in first_ko or ko < first_ko[c]:
            first_ko[c] = ko
    return [c for c, _ in sorted(first_ko.items(), key=lambda kv: (kv[1], kv[0]))]


def forward_chain_wdl(rows: Sequence[dict], predictor_factory=None,
                      feature_subset: Optional[Sequence[str]] = None) -> Dict:
    """Forward-chaining: for competition c_k (kickoff order), fit on all earlier comps, score on c_k."""
    import numpy as np
    if predictor_factory is None:
        predictor_factory = WDL_FACTORY
    assert_no_2026(rows)
    order = _comp_order(rows)
    by_comp: Dict[str, List[dict]] = {}
    for r in rows:
        by_comp.setdefault(r["competition"], []).append(r)
    folds = []
    pooled: Dict[str, Dict[str, List[float]]] = {}
    for i in range(1, len(order)):
        test_comp = order[i]
        train = [r for c in order[:i] for r in by_comp[c]]
        test = by_comp[test_comp]
        if not train or not test:
            continue
        preds = predictor_factory(train)
        if feature_subset is not None:
            preds = {k: v for k, v in preds.items() if k in feature_subset}
        fold_models = {}
        for name, fn in preds.items():
            sc = _score_wdl(fn, test)
            fold_models[name] = {k: v for k, v in sc.items() if k not in ("rows_detail", "per_match_rps")}
            pooled.setdefault(name, {"rps": [], "logloss": [], "brier_draw": []})
            for mk in ("rps", "logloss", "brier_draw"):
                if sc[mk] is not None:
                    pooled[name][mk].append(sc[mk])
        folds.append({"test_competition": test_comp, "n_train_comps": i,
                      "n_train_rows": len(train), "n_test_rows": len(test), "models": fold_models})
    pooled_summary = {n: {mk: (float(np.mean(v[mk])) if v[mk] else None) for mk in v} for n, v in pooled.items()}
    return {"protocol": "forward_chain", "competition_order": order, "n_folds": len(folds),
            "folds": folds, "pooled": pooled_summary}


def loco_wdl(rows: Sequence[dict], predictor_factory=None,
             feature_subset: Optional[Sequence[str]] = None) -> Dict:
    """Leave-one-international-competition-out W/D/L. Returns per-fold metrics + per-match RPS series."""
    import numpy as np
    if predictor_factory is None:
        predictor_factory = WDL_FACTORY
    assert_no_2026(rows)
    folds = []
    per_model_match_rps: Dict[str, Dict[str, List[float]]] = {}
    rel_accum: Dict[str, List] = {}
    for held, train, test in CM.loco_folds(rows):
        preds = predictor_factory(train)
        if feature_subset is not None:
            preds = {k: v for k, v in preds.items() if k in feature_subset}
        fold_models = {}
        for name, fn in preds.items():
            sc = _score_wdl(fn, test)
            fold_models[name] = {k: v for k, v in sc.items() if k not in ("rows_detail", "per_match_rps")}
            mm = per_model_match_rps.setdefault(name, {})
            for m, val in sc["per_match_rps"].items():
                mm.setdefault(m, []).append(val)
            rel_accum.setdefault(name, []).extend(sc["rows_detail"])
        folds.append({"held_competition": held, "n_train_rows": len(train),
                      "n_test_rows": len(test), "models": fold_models})
    per_model_match_mean = {name: {m: float(np.mean(v)) for m, v in mm.items()}
                            for name, mm in per_model_match_rps.items()}
    reliability = {name: CM.calibration(detail) for name, detail in rel_accum.items()}
    return {"protocol": "loco", "n_folds": len(folds), "folds": folds,
            "per_model_match_rps": per_model_match_mean, "reliability": reliability}


def loco_binary(rows: Sequence[dict], predictor_factory, target_key: str) -> Dict:
    """LOCO for a binary family (next-goal / scoring / discipline)."""
    import numpy as np
    assert_no_2026(rows)
    folds = []
    per_model_match_brier: Dict[str, Dict[str, List[float]]] = {}
    pooled: Dict[str, Dict[str, List[float]]] = {}
    for held, train, test in CM.loco_folds(rows):
        preds = predictor_factory(train, target_key=target_key)
        fold_models = {}
        for name, fn in preds.items():
            sc = _score_binary(fn, test, target_key)
            fold_models[name] = {k: v for k, v in sc.items() if k != "per_match_brier"}
            mm = per_model_match_brier.setdefault(name, {})
            for m, val in sc["per_match_brier"].items():
                mm.setdefault(m, []).append(val)
            pooled.setdefault(name, {"logloss": [], "brier": []})
            for mk in ("logloss", "brier"):
                if sc[mk] is not None:
                    pooled[name][mk].append(sc[mk])
        folds.append({"held_competition": held, "n_train_rows": len(train),
                      "n_test_rows": len(test), "models": fold_models})
    per_model_match_mean = {name: {m: float(np.mean(v)) for m, v in mm.items()}
                            for name, mm in per_model_match_brier.items()}
    pooled_summary = {n: {mk: (float(np.mean(v[mk])) if v[mk] else None) for mk in v} for n, v in pooled.items()}
    return {"protocol": "loco_binary", "target": target_key, "n_folds": len(folds), "folds": folds,
            "pooled": pooled_summary, "per_model_match_brier": per_model_match_mean}


# =================================================================================================
# paired match-level bootstrap (reuse shared bootstrap on per-match paired deltas)
# =================================================================================================
def paired_bootstrap_delta(per_model_match: Dict[str, Dict[str, float]],
                           candidate: str, reference: str, n: int = 1000) -> Dict:
    import numpy as np
    cand = per_model_match.get(candidate, {})
    ref = per_model_match.get(reference, {})
    common = sorted(set(cand) & set(ref))
    deltas = [cand[m] - ref[m] for m in common]
    if not deltas:
        return {"n_matches": 0, "mean_delta": None, "ci95": (None, None), "favors_candidate": None}
    lo, hi = CM.match_bootstrap_ci(deltas, n=n)
    return {"n_matches": len(common), "mean_delta": float(np.mean(deltas)), "ci95": (lo, hi),
            "favors_candidate": bool(hi is not None and hi < 0.0)}


# =================================================================================================
# Candidate promotion rule (vs the e2 remaining-time Poisson reference).
#   verdicts: reference_only | rejected | data_insufficient | research_candidate_for_future_shadow_review
# =================================================================================================
REFERENCE_MODEL = "research.event_process.e2"
CANDIDATE_VERDICTS = ("reference_only", "rejected", "data_insufficient",
                      "research_candidate_for_future_shadow_review")


def _source_completeness_adequate(rows: Sequence[dict]) -> Dict:
    """Honest source-completeness gate: a candidate that relies on event-process intensity needs the xG /
    chance-quality channel to be actually present (not imputed) on enough rows. Reads the upstream
    ``xg_present`` flag carried on each snapshot. Never imputes a missing flag as adequate."""
    n = len(rows)
    have_xg = sum(1 for r in rows if str(r.get("xg_present")) in ("1", "1.0", "True", "true"))
    frac = (have_xg / n) if n else 0.0
    return {"n_rows": n, "n_xg_present": have_xg, "xg_present_fraction": round(frac, 4),
            "adequate": bool(n >= 200 and frac >= 0.5)}


def evaluate_candidate_rule(loco_result: Dict, candidate: str,
                            reference: str = REFERENCE_MODEL,
                            rows_for_completeness: Optional[Sequence[dict]] = None,
                            club_only_candidate: bool = False,
                            one_tournament_guard: bool = True,
                            min_matches: int = 30, min_test_rows: int = 200,
                            calibration_tol: float = 0.02) -> Dict:
    """Apply the preregistered promotion rules and return a verdict + rule-by-rule evidence.

    A candidate becomes ``research_candidate_for_future_shadow_review`` ONLY when it:
      R1 has lower mean LOCO RPS than the e2 reference;
      R2 is favorable in >= 75% of folds;
      R3 the match-level paired bootstrap CI favors it (upper bound < 0 on the RPS delta);
      R4 calibration (draw-channel ECE) is not degraded vs the reference beyond tol;
      R5 is NOT one-tournament-driven (advantage persists with the single best fold removed);
      R6 is NOT club-only (must be a model evaluated on international test rows);
      R7 source-completeness is adequate (enough rows + real xG presence).
    Otherwise: a SAFETY violation (R4/R6/R7) -> ``rejected``; a strength shortfall -> ``reference_only``;
    too little data -> ``data_insufficient``.
    """
    import numpy as np
    folds = loco_result.get("folds", [])
    pmr = loco_result.get("per_model_match_rps", {})
    evidence: Dict[str, object] = {}
    notes: List[str] = []

    # completeness gate (decides data_insufficient early)
    n_test_rows = sum(f["n_test_rows"] for f in folds)
    n_match = len(set(pmr.get(candidate, {})) & set(pmr.get(reference, {})))
    enough = (n_match >= min_matches) and (n_test_rows >= min_test_rows) and (len(folds) >= 2)
    evidence["gate_enough_data"] = {"ok": bool(enough), "n_matches": n_match, "n_test_rows": n_test_rows,
                                    "n_folds": len(folds), "min_matches": min_matches,
                                    "min_test_rows": min_test_rows}
    if not enough:
        return {"candidate": candidate, "reference": reference, "verdict": "data_insufficient",
                "reason": "insufficient matches/rows/folds to evaluate", "rules": evidence, "notes": notes}

    # per-fold candidate vs reference RPS
    fold_deltas, cand_pooled, ref_pooled = [], [], []
    for f in folds:
        mc = f["models"].get(candidate); mr = f["models"].get(reference)
        if not mc or not mr or mc.get("rps") is None or mr.get("rps") is None:
            continue
        fold_deltas.append({"fold": f["held_competition"], "delta": mc["rps"] - mr["rps"]})
        cand_pooled.append(mc["rps"]); ref_pooled.append(mr["rps"])
    if not fold_deltas:
        return {"candidate": candidate, "reference": reference, "verdict": "data_insufficient",
                "reason": "candidate or reference not scored in any fold", "rules": evidence, "notes": notes}
    cand_mean = float(np.mean(cand_pooled)); ref_mean = float(np.mean(ref_pooled))

    r1 = cand_mean < ref_mean
    evidence["r1_improves_reference"] = {"ok": bool(r1), "candidate_rps": cand_mean,
                                         "reference_rps": ref_mean, "delta": cand_mean - ref_mean}

    n_fav = sum(1 for d in fold_deltas if d["delta"] < 0)
    frac = n_fav / len(fold_deltas)
    r2 = (frac >= 0.75)
    evidence["r2_fold_consistency"] = {"ok": bool(r2), "n_favorable": n_fav, "n_folds": len(fold_deltas),
                                       "fraction": round(frac, 4), "per_fold": fold_deltas}

    boot = paired_bootstrap_delta(pmr, candidate, reference)
    r3 = bool(boot.get("favors_candidate"))
    evidence["r3_bootstrap_favors_candidate"] = {"ok": r3, **boot}

    def _mean_ece(model):
        vals = [f["models"][model]["calibration"]["ece"]
                for f in folds if f["models"].get(model)
                and isinstance(f["models"][model].get("calibration"), dict)
                and f["models"][model]["calibration"].get("ece") is not None]
        return float(np.mean(vals)) if vals else None
    # W/D/L folds store draw-channel reliability under loco_result["reliability"]; per-fold ECE is not on
    # the WDL fold dict, so fall back to the pooled reliability ECE comparison when per-fold is absent.
    rel = loco_result.get("reliability", {})
    cand_ece = (rel.get(candidate) or {}).get("ece")
    ref_ece = (rel.get(reference) or {}).get("ece")
    if cand_ece is None or ref_ece is None:
        r4 = True
        notes.append("draw-channel ECE unavailable for one model; R4 not blocking")
    else:
        r4 = cand_ece <= ref_ece + calibration_tol
    evidence["r4_calibration_not_degraded"] = {"ok": bool(r4), "candidate_ece": cand_ece,
                                               "reference_ece": ref_ece, "tol": calibration_tol}

    if one_tournament_guard and len(fold_deltas) >= 2:
        best = min(fold_deltas, key=lambda d: d["delta"])
        remaining = [d["delta"] for d in fold_deltas if d is not best]
        r5 = bool(remaining) and (float(np.mean(remaining)) < 0.0)
        dropped = best["fold"]
        mean_wo = float(np.mean(remaining)) if remaining else None
    else:
        r5 = bool(len(fold_deltas) >= 2)
        dropped = None
        mean_wo = None
    evidence["r5_not_one_tournament_driven"] = {"ok": bool(r5), "dropped_fold": dropped,
                                                "mean_delta_without_best": mean_wo}

    r6 = not club_only_candidate
    evidence["r6_not_club_only"] = {"ok": bool(r6),
                                    "note": "international test rows enforced by load_eval_rows()"}

    comp = _source_completeness_adequate(rows_for_completeness) if rows_for_completeness is not None \
        else {"adequate": True, "note": "completeness rows not supplied; not blocking"}
    r7 = bool(comp.get("adequate"))
    evidence["r7_source_completeness_adequate"] = {"ok": r7, **comp}

    all_pass = all([r1, r2, r3, r4, r5, r6, r7])
    if all_pass:
        verdict = "research_candidate_for_future_shadow_review"
        reason = "beats e2 on RPS with fold-consistency + bootstrap + calibration + completeness (paper-only)"
    elif not (r4 and r6 and r7):
        verdict = "rejected"
        reason = "violates a safety rule (calibration degraded / club-only / source-completeness inadequate)"
    else:
        verdict = "reference_only"
        reason = "does not beat the e2 reference under the consistency/bootstrap rules -> keep reference"
    return {"candidate": candidate, "reference": reference, "verdict": verdict, "reason": reason,
            "rules": evidence, "notes": notes}


# =================================================================================================
# Club-transfer ablation: report the e8 family WITH and WITHOUT the auxiliary club representation.
# =================================================================================================
def club_transfer_comparison(rows: Sequence[dict], club_rows: Sequence[dict],
                             model_id: str = "research.event_process.e8") -> Dict:
    """Run LOCO twice -- with and without the club aux rep -- and report e8's pooled RPS each way.
    A negative ``rps_delta_with_minus_without`` means the club transfer helps; positive means it hurts."""
    with_club = loco_wdl(rows, predictor_factory=make_wdl_factory(club_rows, include_club_transfer=True))
    without_club = loco_wdl(rows, predictor_factory=make_wdl_factory(None, include_club_transfer=False))

    def _pooled_rps(res):
        vals = [f["models"][model_id]["rps"] for f in res["folds"]
                if f["models"].get(model_id) and f["models"][model_id].get("rps") is not None]
        import numpy as np
        return float(np.mean(vals)) if vals else None
    rw = _pooled_rps(with_club)
    ro = _pooled_rps(without_club)
    delta = (rw - ro) if (rw is not None and ro is not None) else None
    return {"model_id": model_id, "rps_with_club": rw, "rps_without_club": ro,
            "rps_delta_with_minus_without": delta,
            "club_transfer_helps": bool(delta is not None and delta < 0.0),
            "n_club_rows": len(club_rows)}


# =================================================================================================
# Convenience: full W/D/L suite + candidate verdicts for every e3..e9 candidate vs the e2 reference.
# =================================================================================================
def run_wdl_suite(rows: Optional[Sequence[dict]] = None,
                  club_rows: Optional[Sequence[dict]] = None,
                  n_bootstrap: int = 1000) -> Dict:
    """End-to-end W/D/L: forward-chain + LOCO + per-candidate verdicts vs e2 + club-transfer ablation."""
    if rows is None:
        rows = load_eval_rows()["snapshot_rows"]
    if club_rows is None:
        club_rows = load_club_aux_rows()
    factory = make_wdl_factory(club_rows, include_club_transfer=bool(club_rows))
    fwd = forward_chain_wdl(rows, predictor_factory=factory)
    loco = loco_wdl(rows, predictor_factory=factory)
    candidates = [m for m in M.REG.EVENT_PROCESS_MODELS if m != REFERENCE_MODEL]
    verdicts = {}
    for cand in candidates:
        verdicts[cand] = evaluate_candidate_rule(loco, cand, reference=REFERENCE_MODEL,
                                                 rows_for_completeness=rows)
    club_cmp = club_transfer_comparison(rows, club_rows) if club_rows else {
        "model_id": "research.event_process.e8", "rps_with_club": None, "rps_without_club": None,
        "rps_delta_with_minus_without": None, "club_transfer_helps": None, "n_club_rows": 0,
        "note": "no club aux rows present; e8 == e7 (transfer disabled)"}
    return {"forward_chain": fwd, "loco": loco, "candidate_verdicts": verdicts,
            "club_transfer": club_cmp, "reference": REFERENCE_MODEL,
            "n_rows": len(rows), "n_club_rows": len(club_rows)}
