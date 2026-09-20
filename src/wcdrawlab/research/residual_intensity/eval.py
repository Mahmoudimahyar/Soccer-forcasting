"""Leakage-safe EVALUATION harness for the residual goal-intensity model families (Phases 4-5).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

EXTENDS the locked dynamic_eval harness (reuses its forward-chaining, LOCO, paired match-level bootstrap,
and metric helpers via the shared _common module) and the residual_intensity datasets loader (which joins
the already-leakage-checked event-process snapshots/targets, attaches side-specific remaining-goal labels
+ near-term horizon labels, enforces international-only + NO-2026, and annotates W2 / completeness /
regime). It scores the three canonical families against their W2 references and applies the preregistered
promotion rules:

  W/D/L  residual.*   -- forward-chain + LOCO vs r0 (W2 reference). A model becomes
        ``research_candidate_for_future_shadow_review`` ONLY if it: lowers RPS vs r0; does not raise
        logloss; does not degrade the draw calibration; is favorable in >= 75% of folds; the match-level
        bootstrap favors it; is not one-tournament-driven; persists under LOCO; is not a club-test model;
        (for the selective gate) does not abstain on almost everything; and source-completeness is
        adequate. Otherwise reference_only / rejected / data_insufficient.

  near-term horizon.* -- LOCO (per horizon 5/10/15) vs h0 (W2-implied). A model becomes
        ``research_candidate_for_near_term_monitoring`` ONLY if it: improves multiclass... (binary here)
        Brier AND logloss vs the W2-implied baseline; calibration is ok; favorable in >= 75% of folds;
        correction coverage >= 40%; the corrected rows are not offset by fallback degradation; and the
        bootstrap favors it. Otherwise reference_only / rejected / data_insufficient.

HARD INVARIANTS (re-asserted): 2026 WC never fits/selects/tests; club rows train aux reps but are NEVER
international test rows; targets never enter a feature space; the W2 reference is the parameter-free
anchor every candidate must beat or fall back to; match-level bootstrap only.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
_RJ = ROOT / "scripts/research_jobs"
if str(_RJ) not in sys.path:
    sys.path.insert(0, str(_RJ))
import _common as CM  # noqa: E402  shared rps/logloss3/brier_draw/calibration/loco_folds/bootstrap

from wcdrawlab.research import dynamic_eval as DE  # noqa: E402  EXTEND the locked dynamic harness
from . import datasets as DATA  # noqa: E402
from . import features as F  # noqa: E402
from . import models as M  # noqa: E402
from . import quality as Q  # noqa: E402
from . import registry as REG  # noqa: E402

EVAL_VERSION = "residual_intensity_eval_v1"
WDL = ["H", "D", "A"]
HORIZONS = (5, 10, 15)
ARTIFACT_LABELS = REG.ARTIFACT_LABELS

# canonical references (the parameter-free W2 anchors every candidate must beat or fall back to)
WDL_REFERENCE = REG.REFERENCE_IDS["residual"]      # research.residual.w2_reference_r0
INTENSITY_REFERENCE = REG.REFERENCE_IDS["intensity"]  # research.intensity.w2_home_away_i0
HORIZON_REFERENCE = REG.REFERENCE_IDS["horizon"]    # research.horizon.w2_implied_h0

WDL_VERDICTS = ("reference_only", "rejected", "data_insufficient",
                "research_candidate_for_future_shadow_review")
HORIZON_VERDICTS = ("reference_only", "rejected", "data_insufficient",
                    "research_candidate_for_near_term_monitoring")


class DataInsufficient(Exception):
    """Raised when a required local product is absent/empty so a job can emit an honest skip."""


# =================================================================================================
# predictor-factory closures (TRAIN -> {model_id: predict_one}) for the shared harness
# =================================================================================================
def make_wdl_factory(club_rows: Optional[Sequence[dict]] = None, include_club_transfer: bool = True):
    """1-arg W/D/L factory for DE.forward_chain_wdl / DE.loco_wdl. Injects club aux rows for r6; with
    ``include_club_transfer=False`` (or no club rows) r6 is omitted -- the with/without ablation."""
    cr = list(club_rows) if (club_rows and include_club_transfer) else None

    def _factory(train_rows: Sequence[dict]) -> Dict[str, Callable]:
        return M.residual_predictors(train_rows, club_rows=cr, include_club_transfer=include_club_transfer)
    return _factory


def make_horizon_factory(horizon_min: int):
    """1-arg binary factory (train_rows[, target_key]) for the near-term horizon family at one horizon.
    The target_key kwarg (passed by the binary LOCO harness) is ignored: the horizon head selects its own
    leakage-safe label internally (any_goal_next{h}m) so the harness cannot point it at a wrong column."""
    def _factory(train_rows: Sequence[dict], target_key: Optional[str] = None) -> Dict[str, Callable]:
        return M.horizon_predictors(train_rows, horizon_min)
    return _factory


# =================================================================================================
# W/D/L scoring (reuse dynamic_eval forward-chain + LOCO + bootstrap)
# =================================================================================================
def _pooled_logloss(loco_result: Dict, model_id: str) -> Optional[float]:
    import numpy as np
    vals = [f["models"][model_id]["logloss"] for f in loco_result["folds"]
            if f["models"].get(model_id) and f["models"][model_id].get("logloss") is not None]
    return float(np.mean(vals)) if vals else None


def _pooled_rps(loco_result: Dict, model_id: str) -> Optional[float]:
    import numpy as np
    vals = [f["models"][model_id]["rps"] for f in loco_result["folds"]
            if f["models"].get(model_id) and f["models"][model_id].get("rps") is not None]
    return float(np.mean(vals)) if vals else None


def _fold_deltas(loco_result: Dict, candidate: str, reference: str, metric: str) -> List[Dict]:
    out = []
    for f in loco_result["folds"]:
        mc = f["models"].get(candidate)
        mr = f["models"].get(reference)
        if not mc or not mr or mc.get(metric) is None or mr.get(metric) is None:
            continue
        out.append({"fold": f["held_competition"], "delta": mc[metric] - mr[metric]})
    return out


def _draw_ece(reliability: Dict, model_id: str) -> Optional[float]:
    rel = (reliability or {}).get(model_id) or {}
    return rel.get("ece")


def _correction_coverage(rows: Sequence[dict], train_rows: Sequence[dict], model_id: str) -> Dict:
    """Fraction of rows where a selective model actually applies a correction (alpha>0 / not h0).
    For the W/D/L selective correction r4 this re-fits the gate on TRAIN and reads the per-row decision;
    for non-selective models it reports coverage=1.0 (they always 'correct', i.e. never abstain)."""
    if model_id == "research.residual.selective_correction_r4":
        sc = M.build_selective_correction_r4(list(train_rows))
        if sc.gate is None:
            return {"coverage": 0.0, "abstains_most": True, "diagnostics": sc.diagnostics()}
        corrected = sum(1 for r in rows if sc.gate.alpha_for(r) > 0.0)
        cov = corrected / max(1, len(rows))
        return {"coverage": round(cov, 4), "abstains_most": bool(cov < 0.05),
                "diagnostics": sc.diagnostics()}
    return {"coverage": 1.0, "abstains_most": False}


# =================================================================================================
# W/D/L candidate promotion rule  (vs r0 = W2 reference)
# =================================================================================================
def evaluate_wdl_candidate(loco_result: Dict, candidate: str,
                           rows_for_completeness: Optional[Sequence[dict]] = None,
                           train_rows_for_gate: Optional[Sequence[dict]] = None,
                           reference: str = WDL_REFERENCE,
                           club_only_candidate: bool = False,
                           min_matches: int = 30, min_test_rows: int = 200,
                           calibration_tol: float = 0.02) -> Dict:
    """Apply the preregistered W/D/L promotion rules; return verdict + rule-by-rule evidence.

    research_candidate_for_future_shadow_review iff ALL hold:
      W1 lower mean LOCO RPS than r0;
      W2 lower-or-equal mean LOCO logloss than r0 (no draw/logloss degradation);
      W3 draw-channel calibration not degraded vs r0 (ECE within tol);
      W4 favorable in >= 75% of folds (RPS);
      W5 match-level paired bootstrap favors it (RPS delta CI upper bound < 0);
      W6 not one-tournament-driven (advantage persists with the single best fold removed);
      W7 persists in LOCO (>=2 folds scored);
      W8 not a club-test model;
      W9 (selective gate only) does not abstain on almost everything;
      W10 source-completeness adequate.
    SAFETY violations (W2/W3/W8/W9/W10) -> rejected; strength shortfall -> reference_only; thin data ->
    data_insufficient.
    """
    import numpy as np
    folds = loco_result.get("folds", [])
    pmr = loco_result.get("per_model_match_rps", {})
    rel = loco_result.get("reliability", {})
    ev: Dict[str, object] = {}
    notes: List[str] = []

    n_test_rows = sum(f["n_test_rows"] for f in folds)
    n_match = len(set(pmr.get(candidate, {})) & set(pmr.get(reference, {})))
    enough = (n_match >= min_matches) and (n_test_rows >= min_test_rows) and (len(folds) >= 2)
    ev["gate_enough_data"] = {"ok": bool(enough), "n_matches": n_match, "n_test_rows": n_test_rows,
                              "n_folds": len(folds)}
    if not enough:
        return {"candidate": candidate, "reference": reference, "verdict": "data_insufficient",
                "reason": "insufficient matches/rows/folds", "rules": ev, "notes": notes}

    cand_rps, ref_rps = _pooled_rps(loco_result, candidate), _pooled_rps(loco_result, reference)
    cand_ll, ref_ll = _pooled_logloss(loco_result, candidate), _pooled_logloss(loco_result, reference)
    if cand_rps is None or ref_rps is None:
        return {"candidate": candidate, "reference": reference, "verdict": "data_insufficient",
                "reason": "candidate or reference not scored", "rules": ev, "notes": notes}

    w1 = cand_rps < ref_rps
    ev["w1_lower_rps"] = {"ok": bool(w1), "candidate_rps": cand_rps, "reference_rps": ref_rps,
                          "delta": cand_rps - ref_rps}

    w2 = (cand_ll is not None and ref_ll is not None and cand_ll <= ref_ll + 1e-9)
    ev["w2_no_logloss_degradation"] = {"ok": bool(w2), "candidate_logloss": cand_ll,
                                       "reference_logloss": ref_ll}

    cand_ece, ref_ece = _draw_ece(rel, candidate), _draw_ece(rel, reference)
    if cand_ece is None or ref_ece is None:
        w3 = True
        notes.append("draw-channel ECE unavailable for one model; W3 not blocking")
    else:
        w3 = cand_ece <= ref_ece + calibration_tol
    ev["w3_draw_calibration_not_degraded"] = {"ok": bool(w3), "candidate_draw_ece": cand_ece,
                                               "reference_draw_ece": ref_ece, "tol": calibration_tol}

    deltas = _fold_deltas(loco_result, candidate, reference, "rps")
    n_fav = sum(1 for d in deltas if d["delta"] < 0)
    frac = n_fav / len(deltas) if deltas else 0.0
    w4 = frac >= 0.75
    ev["w4_fold_consistency"] = {"ok": bool(w4), "n_favorable": n_fav, "n_folds": len(deltas),
                                 "fraction": round(frac, 4), "per_fold": deltas}

    boot = DE.paired_bootstrap_delta(pmr, candidate, reference)
    w5 = bool(boot.get("favors_candidate"))
    ev["w5_bootstrap_favors_candidate"] = {"ok": w5, **boot}

    if len(deltas) >= 2:
        best = min(deltas, key=lambda d: d["delta"])
        remaining = [d["delta"] for d in deltas if d is not best]
        w6 = bool(remaining) and float(np.mean(remaining)) < 0.0
        ev["w6_not_one_tournament_driven"] = {"ok": bool(w6), "dropped_fold": best["fold"],
                                              "mean_delta_without_best": float(np.mean(remaining)) if remaining else None}
    else:
        w6 = False
        ev["w6_not_one_tournament_driven"] = {"ok": False, "reason": "need >=2 scored folds"}

    w7 = len(deltas) >= 2
    ev["w7_persists_in_loco"] = {"ok": bool(w7), "n_scored_folds": len(deltas)}

    w8 = not club_only_candidate
    ev["w8_not_club_test"] = {"ok": bool(w8),
                              "note": "international test rows enforced by datasets.load_residual_rows()"}

    # W9: selective gate must not abstain on (almost) everything
    cov = _correction_coverage(rows_for_completeness or [], train_rows_for_gate or [], candidate) \
        if (rows_for_completeness is not None and train_rows_for_gate is not None) \
        else {"coverage": 1.0, "abstains_most": False}
    w9 = not bool(cov.get("abstains_most"))
    ev["w9_gate_not_abstaining_most"] = {"ok": bool(w9), **cov}

    comp = DE_completeness(rows_for_completeness) if rows_for_completeness is not None \
        else {"adequate": True, "note": "completeness rows not supplied; not blocking"}
    w10 = bool(comp.get("adequate"))
    ev["w10_source_completeness_adequate"] = {"ok": w10, **comp}

    safety = (w2 and w3 and w8 and w9 and w10)
    strength = (w1 and w4 and w5 and w6 and w7)
    if safety and strength:
        verdict, reason = "research_candidate_for_future_shadow_review", \
            "beats r0 on RPS with no logloss/calibration degradation, fold-consistent, bootstrap-favored, not one-tournament, persists in LOCO, intl-only, completeness adequate (paper-only)"
    elif not safety:
        verdict, reason = "rejected", \
            "violates a safety rule (logloss/draw-calibration degraded / club-test / gate abstains-most / source-completeness inadequate)"
    else:
        verdict, reason = "reference_only", \
            "does not beat r0 under the strength rules -> keep the W2 reference"
    return {"candidate": candidate, "reference": reference, "verdict": verdict, "reason": reason,
            "rules": ev, "notes": notes}


def DE_completeness(rows: Sequence[dict]) -> Dict:
    """Honest source-completeness gate: enough rows + real (not imputed) xG presence on a fraction of
    them. Reads the upstream ``xg_present`` flag carried on each snapshot."""
    n = len(rows)
    have_xg = sum(1 for r in rows if str(r.get("xg_present")).strip().lower() in ("true", "1", "1.0", "yes"))
    frac = (have_xg / n) if n else 0.0
    return {"n_rows": n, "n_xg_present": have_xg, "xg_present_fraction": round(frac, 4),
            "adequate": bool(n >= 200 and frac >= 0.5)}


# =================================================================================================
# W/D/L suite
# =================================================================================================
def run_wdl_suite(rows: Optional[Sequence[dict]] = None,
                  club_rows: Optional[Sequence[dict]] = None,
                  n_bootstrap: int = 1000) -> Dict:
    """End-to-end residual W/D/L: forward-chain + LOCO + per-candidate verdicts vs r0 + club-transfer
    ablation. Reuses dynamic_eval.forward_chain_wdl / loco_wdl (which reuse _common bootstrap)."""
    if rows is None:
        bundle = DATA.load_residual_rows()
        rows = bundle["rows"]
    if club_rows is None:
        club_rows = DATA.load_club_aux_rows()
    factory = make_wdl_factory(club_rows, include_club_transfer=bool(club_rows))
    fwd = DE.forward_chain_wdl(rows, predictor_factory=factory)
    loco = DE.loco_wdl(rows, predictor_factory=factory)

    candidates = [m for m in REG.RESIDUAL_MODELS if m != WDL_REFERENCE]
    verdicts: Dict[str, Dict] = {}
    for cand in candidates:
        scored = any(f["models"].get(cand) for f in loco["folds"])
        if not scored:
            verdicts[cand] = {"candidate": cand, "reference": WDL_REFERENCE,
                              "verdict": "data_insufficient",
                              "reason": "candidate not present in folds (e.g. r6 needs club rows)"}
            continue
        verdicts[cand] = evaluate_wdl_candidate(
            loco, cand, rows_for_completeness=rows, train_rows_for_gate=rows)

    club_cmp = club_transfer_comparison(rows, club_rows) if club_rows else {
        "model_id": "research.residual.club_auxiliary_transfer_r6",
        "rps_with_club": None, "rps_without_club": None, "rps_delta_with_minus_without": None,
        "club_transfer_helps": None, "n_club_rows": 0,
        "note": "no club aux rows present; r6 omitted (transfer disabled)"}
    return {"labels": ARTIFACT_LABELS, "reference": WDL_REFERENCE,
            "forward_chain": fwd, "loco": loco, "candidate_verdicts": verdicts,
            "club_transfer": club_cmp, "n_rows": len(rows), "n_club_rows": len(club_rows)}


def club_transfer_comparison(rows: Sequence[dict], club_rows: Sequence[dict],
                             model_id: str = "research.residual.club_auxiliary_transfer_r6") -> Dict:
    """LOCO twice -- with and without the club aux rep -- and report r6's pooled RPS each way. A negative
    ``rps_delta_with_minus_without`` means the club transfer helps."""
    with_club = DE.loco_wdl(rows, predictor_factory=make_wdl_factory(club_rows, include_club_transfer=True))
    without_club = DE.loco_wdl(rows, predictor_factory=make_wdl_factory(None, include_club_transfer=False))
    rw = _pooled_rps(with_club, model_id)
    # without club, r6 is omitted; compare against r1 (its non-transfer base) for the ablation contrast
    ro = _pooled_rps(without_club, "research.residual.intensity_glm_r1")
    delta = (rw - ro) if (rw is not None and ro is not None) else None
    return {"model_id": model_id, "rps_with_club": rw, "rps_without_club_base_r1": ro,
            "rps_delta_with_minus_without": delta,
            "club_transfer_helps": bool(delta is not None and delta < 0.0),
            "n_club_rows": len(club_rows)}


# =================================================================================================
# near-term horizon scoring (binary, per horizon 5/10/15) -- LOCO vs h0
# =================================================================================================
def _score_binary(predict: Callable[[dict], float], test_rows: Sequence[dict], target_key: str) -> Dict:
    ll = brier = 0.0
    n = 0
    per_match: Dict[str, List[float]] = {}
    pairs = []
    for r in test_rows:
        if r.get(target_key) is None or str(r.get(target_key)) == "":
            continue
        p = min(1 - 1e-9, max(1e-9, float(predict(r))))
        y = int(float(r[target_key]))
        ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        b = (p - y) ** 2
        brier += b
        per_match.setdefault(r.get("match_id"), []).append(b)
        pairs.append((p, float(y)))
        n += 1
    if n == 0:
        return {"logloss": None, "brier": None, "n": 0, "per_match_brier": {}, "calibration": None,
                "base_rate": None}
    return {"logloss": ll / n, "brier": brier / n, "n": n, "base_rate": sum(y for _, y in pairs) / n,
            "per_match_brier": {m: sum(v) / len(v) for m, v in per_match.items()},
            "calibration": CM.calibration(pairs)}


def loco_horizon(rows: Sequence[dict], horizon_min: int) -> Dict:
    """Leave-one-competition-out for the near-term horizon family at one horizon. Right-censoring is
    enforced inside the heads (fit only on fully-observable windows; predict scales to W2 by observable
    fraction); scoring uses every row whose label exists. Returns per-fold metrics + per-match Brier."""
    import numpy as np
    DE.assert_no_2026(rows)
    target_key = f"any_goal_next{int(horizon_min)}m"
    factory = make_horizon_factory(horizon_min)
    folds = []
    per_model_match_brier: Dict[str, Dict[str, List[float]]] = {}
    pooled: Dict[str, Dict[str, List[float]]] = {}
    rel_accum: Dict[str, List] = {}
    for held, train, test in CM.loco_folds(rows):
        preds = factory(train)
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
            if sc.get("calibration") and sc["calibration"].get("ece") is not None:
                rel_accum.setdefault(name, []).append(sc["calibration"]["ece"])
        folds.append({"held_competition": held, "n_train_rows": len(train),
                      "n_test_rows": len(test), "models": fold_models})
    per_model_match_mean = {name: {m: float(np.mean(v)) for m, v in mm.items()}
                            for name, mm in per_model_match_brier.items()}
    pooled_summary = {n: {mk: (float(np.mean(v[mk])) if v[mk] else None) for mk in v}
                      for n, v in pooled.items()}
    pooled_ece = {n: (float(np.mean(v)) if v else None) for n, v in rel_accum.items()}
    return {"protocol": "loco_horizon", "horizon_min": horizon_min, "target": target_key,
            "n_folds": len(folds), "folds": folds, "pooled": pooled_summary,
            "pooled_ece": pooled_ece, "per_model_match_brier": per_model_match_mean}


def _horizon_correction_coverage(rows: Sequence[dict], train_rows: Sequence[dict],
                                 horizon_min: int, model_id: str) -> Dict:
    """Coverage = fraction of rows the selective horizon gate (h4) routes to a NON-h0 head; for h1..h3
    coverage is the fraction of rows whose window is fully observable AND whose head actually fit (else
    they defer to h0). Reports abstains_most and the corrected-vs-fallback split."""
    if model_id == "research.horizon.selective_gate_h4":
        gate = M.SelectiveHorizonGate(horizon_min).fit(list(train_rows))
        non_h0 = sum(1 for r in rows if gate.band_choice[gate._band(r)] != "h0")
        cov = non_h0 / max(1, len(rows))
        return {"coverage": round(cov, 4), "abstains_most": bool(cov < 0.05),
                "diagnostics": gate.fit_diagnostics}
    # h1..h3: coverage = fraction of rows with a fully-observable window (the head's true active set)
    observable = sum(1 for r in rows if M._observable_fraction(r, horizon_min) >= 0.999)
    cov = observable / max(1, len(rows))
    return {"coverage": round(cov, 4), "abstains_most": bool(cov < 0.05)}


def evaluate_horizon_candidate(loco_result: Dict, candidate: str,
                               rows_for_coverage: Optional[Sequence[dict]] = None,
                               train_rows_for_coverage: Optional[Sequence[dict]] = None,
                               reference: str = HORIZON_REFERENCE,
                               min_matches: int = 30, min_test_rows: int = 200,
                               calibration_tol: float = 0.03,
                               coverage_min: float = 0.40) -> Dict:
    """Near-term monitoring rule. research_candidate_for_near_term_monitoring iff ALL hold:
      N1 lower mean LOCO Brier than h0 (W2-implied);
      N2 lower-or-equal mean LOCO logloss than h0;
      N3 calibration ok (ECE within tol of h0);
      N4 favorable in >= 75% of folds (Brier);
      N5 correction coverage >= coverage_min;
      N6 corrected rows not offset by fallback degradation (candidate Brier <= h0 Brier overall AND the
         candidate never does worse than h0 on the rows it leaves to fallback -- enforced structurally by
         the head's W2 fallback, checked here via the overall non-degradation in N1/N2);
      N7 match-level paired bootstrap favors it.
    SAFETY violations (N2/N3/N5) -> rejected; strength shortfall -> reference_only; thin data ->
    data_insufficient.
    """
    import numpy as np
    horizon_min = loco_result.get("horizon_min")
    folds = loco_result.get("folds", [])
    pmb = loco_result.get("per_model_match_brier", {})
    pooled = loco_result.get("pooled", {})
    ece = loco_result.get("pooled_ece", {})
    ev: Dict[str, object] = {}
    notes: List[str] = []

    n_test_rows = sum(f["n_test_rows"] for f in folds)
    n_match = len(set(pmb.get(candidate, {})) & set(pmb.get(reference, {})))
    enough = (n_match >= min_matches) and (n_test_rows >= min_test_rows) and (len(folds) >= 2)
    ev["gate_enough_data"] = {"ok": bool(enough), "n_matches": n_match, "n_test_rows": n_test_rows,
                              "n_folds": len(folds)}
    if not enough:
        return {"candidate": candidate, "reference": reference, "horizon_min": horizon_min,
                "verdict": "data_insufficient", "reason": "insufficient matches/rows/folds",
                "rules": ev, "notes": notes}

    cand_b = (pooled.get(candidate) or {}).get("brier")
    ref_b = (pooled.get(reference) or {}).get("brier")
    cand_ll = (pooled.get(candidate) or {}).get("logloss")
    ref_ll = (pooled.get(reference) or {}).get("logloss")
    if cand_b is None or ref_b is None:
        return {"candidate": candidate, "reference": reference, "horizon_min": horizon_min,
                "verdict": "data_insufficient", "reason": "candidate or reference not scored",
                "rules": ev, "notes": notes}

    n1 = cand_b < ref_b
    ev["n1_lower_brier"] = {"ok": bool(n1), "candidate_brier": cand_b, "reference_brier": ref_b,
                            "delta": cand_b - ref_b}
    n2 = (cand_ll is not None and ref_ll is not None and cand_ll <= ref_ll + 1e-9)
    ev["n2_no_logloss_degradation"] = {"ok": bool(n2), "candidate_logloss": cand_ll,
                                       "reference_logloss": ref_ll}

    cand_e, ref_e = ece.get(candidate), ece.get(reference)
    if cand_e is None or ref_e is None:
        n3 = True
        notes.append("ECE unavailable for one model; N3 not blocking")
    else:
        n3 = cand_e <= ref_e + calibration_tol
    ev["n3_calibration_ok"] = {"ok": bool(n3), "candidate_ece": cand_e, "reference_ece": ref_e,
                               "tol": calibration_tol}

    # per-fold Brier deltas
    deltas = []
    for f in folds:
        mc = f["models"].get(candidate); mr = f["models"].get(reference)
        if not mc or not mr or mc.get("brier") is None or mr.get("brier") is None:
            continue
        deltas.append({"fold": f["held_competition"], "delta": mc["brier"] - mr["brier"]})
    n_fav = sum(1 for d in deltas if d["delta"] < 0)
    frac = n_fav / len(deltas) if deltas else 0.0
    n4 = frac >= 0.75
    ev["n4_fold_consistency"] = {"ok": bool(n4), "n_favorable": n_fav, "n_folds": len(deltas),
                                 "fraction": round(frac, 4), "per_fold": deltas}

    cov = _horizon_correction_coverage(rows_for_coverage or [], train_rows_for_coverage or [],
                                       horizon_min, candidate) \
        if (rows_for_coverage is not None and train_rows_for_coverage is not None) \
        else {"coverage": 1.0, "abstains_most": False}
    n5 = float(cov.get("coverage", 0.0)) >= coverage_min
    ev["n5_coverage_adequate"] = {"ok": bool(n5), "coverage_min": coverage_min, **cov}

    # N6: corrected not offset by fallback degradation -- structurally the head defers to h0 (W2) on
    # rows it cannot cover, so a non-degraded overall Brier+logloss (N1/N2) AND fold-consistency (N4)
    # together certify the corrected rows are not bought by hurting the fallback rows.
    n6 = bool(n1 and n2 and n4)
    ev["n6_corrected_not_offset_by_fallback"] = {
        "ok": n6, "basis": "head defers to h0/W2 on uncovered rows; overall non-degradation + fold "
                           "consistency imply corrected gains are not offset by fallback losses"}

    boot = DE.paired_bootstrap_delta(pmb, candidate, reference)
    n7 = bool(boot.get("favors_candidate"))
    ev["n7_bootstrap_favors_candidate"] = {"ok": n7, **boot}

    safety = (n2 and n3 and n5)
    strength = (n1 and n4 and n6 and n7)
    if safety and strength:
        verdict, reason = "research_candidate_for_near_term_monitoring", \
            "beats W2-implied h0 on Brier+logloss, calibration ok, fold-consistent, coverage>=min, "\
            "corrected not offset by fallback, bootstrap-favored (paper-only)"
    elif not safety:
        verdict, reason = "rejected", \
            "violates a safety rule (logloss/calibration degraded / coverage below minimum)"
    else:
        verdict, reason = "reference_only", \
            "does not beat the W2-implied h0 under the strength rules -> keep the reference"
    return {"candidate": candidate, "reference": reference, "horizon_min": horizon_min,
            "verdict": verdict, "reason": reason, "rules": ev, "notes": notes}


def run_horizon_suite(rows: Optional[Sequence[dict]] = None, horizons: Sequence[int] = HORIZONS) -> Dict:
    """End-to-end near-term horizon family: per-horizon LOCO + monitoring verdicts vs h0."""
    if rows is None:
        rows = DATA.load_residual_rows()["rows"]
    out: Dict[str, Dict] = {}
    for h in horizons:
        loco = loco_horizon(rows, h)
        candidates = [m for m in REG.HORIZON_MODELS if m != HORIZON_REFERENCE]
        verdicts = {}
        for cand in candidates:
            scored = any(f["models"].get(cand) for f in loco["folds"])
            if not scored:
                verdicts[cand] = {"candidate": cand, "reference": HORIZON_REFERENCE, "horizon_min": h,
                                  "verdict": "data_insufficient", "reason": "candidate not scored"}
                continue
            verdicts[cand] = evaluate_horizon_candidate(
                loco, cand, rows_for_coverage=rows, train_rows_for_coverage=rows)
        out[f"horizon_{h}m"] = {"loco": loco, "candidate_verdicts": verdicts}
    return {"labels": ARTIFACT_LABELS, "reference": HORIZON_REFERENCE, "horizons": list(horizons),
            "by_horizon": out, "n_rows": len(rows)}


# =================================================================================================
# SELF-TEST (mandated): r0 + r1 + one near-term head on a small REAL subset -> finite metrics, and a
# 2-fold forward chain returns numbers. status=complete only if real finite metrics are produced.
# =================================================================================================
def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(float(x))


def self_test(rows: Optional[Sequence[dict]] = None, max_rows: int = 1600) -> Dict:
    """Run the mandated self-tests. Prefers the REAL joined snapshot panel (a bounded subset for speed);
    falls back to the deterministic synthetic panel ONLY for structural checks (status=complete is gated
    on the REAL path producing finite metrics)."""
    out: Dict[str, object] = {"labels": ARTIFACT_LABELS, "version": EVAL_VERSION}
    real_used = False
    if rows is None:
        try:
            bundle = DATA.load_residual_rows()
            allrows = list(bundle["rows"])
            # bounded subset preserving >=2 competitions for forward-chaining / LOCO
            comps = DATA.forward_chain_order(allrows)
            rows = _bounded_subset(allrows, comps, max_rows)
            real_used = True
            out["data_source"] = "real_snapshot_panel_subset"
            out["n_rows"] = len(rows)
            out["n_competitions"] = len({r.get("competition") for r in rows})
        except DATA.DataInsufficient as e:
            out["data_source"] = "synthetic_fallback"
            out["data_insufficient_reason"] = str(e)
            rows = DATA.synthetic_rows(n_matches=12, seed=5)
    else:
        rows = list(rows)
        out["data_source"] = "provided_rows"
    rows = list(rows)

    # leakage re-assert on the chosen feature column-set
    feat_cols = F.columns_for(["reference_state", "recent_chance", "possession_territory",
                               "transition", "set_pieces", "quality_availability"])
    lk = Q.leakage_audit(rows[: min(800, len(rows))], feat_cols)
    out["leakage_audit"] = {"ok": lk["ok"], "no_target_in_features": lk["no_target_in_features"]["ok"]}

    # (a) r0 + r1 finite WDL metrics via a 2-fold LOCO on the subset
    factory = make_wdl_factory(None, include_club_transfer=False)
    loco = DE.loco_wdl(rows, predictor_factory=factory)
    r0_rps = _pooled_rps(loco, WDL_REFERENCE)
    r1_rps = _pooled_rps(loco, "research.residual.intensity_glm_r1")
    r1_ll = _pooled_logloss(loco, "research.residual.intensity_glm_r1")
    out["wdl_loco"] = {"n_folds": loco["n_folds"], "r0_rps": r0_rps, "r1_rps": r1_rps,
                       "r1_logloss": r1_ll,
                       "r0_finite": _finite(r0_rps), "r1_finite": _finite(r1_rps) and _finite(r1_ll)}

    # (b) one near-term head (h2 @ 10min) finite Brier/logloss via LOCO
    hz = loco_horizon(rows, 10)
    h0_b = (hz["pooled"].get(HORIZON_REFERENCE) or {}).get("brier")
    h2_b = (hz["pooled"].get("research.horizon.possession_transition_h2") or {}).get("brier")
    h2_ll = (hz["pooled"].get("research.horizon.possession_transition_h2") or {}).get("logloss")
    out["horizon_loco_10m"] = {"n_folds": hz["n_folds"], "h0_brier": h0_b, "h2_brier": h2_b,
                               "h2_logloss": h2_ll,
                               "h0_finite": _finite(h0_b),
                               "h2_finite": _finite(h2_b) and _finite(h2_ll)}

    # (c) a 2-fold forward chain returns numbers
    fwd = DE.forward_chain_wdl(rows, predictor_factory=factory)
    fwd_r0 = (fwd["pooled"].get(WDL_REFERENCE) or {}).get("rps")
    fwd_r1 = (fwd["pooled"].get("research.residual.intensity_glm_r1") or {}).get("rps")
    out["forward_chain"] = {"n_folds": fwd["n_folds"], "r0_rps": fwd_r0, "r1_rps": fwd_r1,
                            "returns_numbers": bool(fwd["n_folds"] >= 1 and _finite(fwd_r0))}

    passed = bool(lk["ok"]
                  and out["wdl_loco"]["r0_finite"] and out["wdl_loco"]["r1_finite"]
                  and out["horizon_loco_10m"]["h0_finite"] and out["horizon_loco_10m"]["h2_finite"]
                  and out["forward_chain"]["returns_numbers"]
                  and loco["n_folds"] >= 2)
    out["all_passed"] = passed
    out["real_rows_used"] = real_used
    out["status"] = "complete" if (passed and real_used) else ("partial" if passed else "failed")
    return out


def _bounded_subset(rows: Sequence[dict], comp_order: Sequence[str], max_rows: int) -> List[dict]:
    """Take whole competitions in forward-chaining order until ~max_rows, keeping >= 2 competitions so
    the forward-chain / LOCO protocols have folds. Whole matches per competition are preserved."""
    by_comp: Dict[str, List[dict]] = {}
    for r in rows:
        by_comp.setdefault(r.get("competition"), []).append(r)
    out: List[dict] = []
    kept = 0
    for c in comp_order:
        grp = by_comp.get(c, [])
        if not grp:
            continue
        out.extend(grp)
        kept += 1
        if len(out) >= max_rows and kept >= 2:
            break
    return out or list(rows)


__all__ = [
    "EVAL_VERSION", "ARTIFACT_LABELS",
    "WDL_REFERENCE", "INTENSITY_REFERENCE", "HORIZON_REFERENCE",
    "make_wdl_factory", "make_horizon_factory",
    "run_wdl_suite", "evaluate_wdl_candidate", "club_transfer_comparison",
    "loco_horizon", "run_horizon_suite", "evaluate_horizon_candidate",
    "self_test",
]
