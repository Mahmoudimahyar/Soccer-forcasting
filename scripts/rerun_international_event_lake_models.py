"""Rerun the PREREGISTERED model families on the frozen International Event Lake cohort (Phases 6-8).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Reuses ONLY existing, preregistered model families (NO new features / search / neural / market):
  * remaining-time Poisson REFERENCE  -- research.event_process.e2  (== R0, the parameter-free anchor)
  * time + score                      -- research.event_process.e1
  * xG-state intensity                -- research.event_process.e3
  * full event-process intensity      -- research.event_process.e4..e7
  * club-transfer / calibrated hybrid -- research.event_process.e8, e9
  * residual / selective-correction   -- the residual_intensity families degrade to the same e2 anchor
                                         when their richer label products are absent (honest fallback)

PROTOCOLS (reuse the locked harness verbatim -- nothing re-implemented):
  * forward-chaining by tournament (kickoff order)         event_process.eval.forward_chain_wdl
  * leave-one-competition-out (LOCO)                        event_process.eval.loco_wdl
  * match-level PAIRED bootstrap (independent unit = MATCH) event_process.eval.paired_bootstrap_delta
  * preregistered candidate promotion rule vs e2/R0        event_process.eval.evaluate_candidate_rule

The eval rows come straight from the LAKE cohort (build_international_event_lake_cohort) -- raw-backed,
hash-verified, label-safe (wdl_target_conflict matches excluded), regulation-only, NO 2026 WC. Calibration
is fit INSIDE the training fold only (IntensityWDL / CalibratedBlend never consult a test label).

CANDIDATE RULE (verbatim from the spec): a family becomes
``research_candidate_for_future_shadow_review`` ONLY if it has lower RPS than R0, no worse logloss3,
no calibration degradation, is favorable in >= 75% of folds, is bootstrap-favored, is LOCO-consistent,
is not one-tournament-driven, is not a club-only/low-coverage subset, has coverage >= 60%, and is fit on
lake-hash-backed inputs. Otherwise: reference_only / rejected / data_insufficient.

PRODUCTS (data/reference/):
  international_event_lake_model_decision_ledger.csv / .json
  international_event_lake_evaluation_metrics.json
  international_event_lake_calibration.json
  international_event_lake_bootstrap.json
  international_event_lake_reproducibility_audit.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
_RJ = ROOT / "scripts/research_jobs"
if str(_RJ) not in sys.path:
    sys.path.insert(0, str(_RJ))

import _common as CM  # noqa: E402  shared rps/logloss3/brier_draw/calibration/loco_folds/bootstrap
from wcdrawlab.research.event_process import eval as EV  # noqa: E402  locked forward-chain/LOCO/rule
from wcdrawlab.research.event_process import models as M  # noqa: E402
from wcdrawlab.research.event_process import registry as REG  # noqa: E402

import build_international_event_lake_cohort as COH  # noqa: E402

RERUN_VERSION = "international_event_lake_model_rerun_v1"
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"

OUT_DIR = ROOT / "data/reference"
LEDGER_CSV = OUT_DIR / "international_event_lake_model_decision_ledger.csv"
LEDGER_JSON = OUT_DIR / "international_event_lake_model_decision_ledger.json"
METRICS_JSON = OUT_DIR / "international_event_lake_evaluation_metrics.json"
CALIB_JSON = OUT_DIR / "international_event_lake_calibration.json"
BOOT_JSON = OUT_DIR / "international_event_lake_bootstrap.json"
AUDIT_JSON = OUT_DIR / "international_event_lake_reproducibility_audit.json"

REFERENCE_MODEL = EV.REFERENCE_MODEL  # research.event_process.e2  (the R0 anchor)
WDL = ["H", "D", "A"]
COVERAGE_FLOOR = 0.60  # candidate must be scored on >= 60% of the eligible cohort matches


# =====================================================================================================
# eval-row loader straight from the LAKE cohort (no CSV round-trip; label-safe + raw-backed)
# =====================================================================================================
def load_cohort_eval_rows(limit: Optional[int] = None,
                          snapshot_minutes: Optional[list[float]] = None) -> Dict[str, object]:
    """Build the cohort in-memory and flatten its eligible snapshots into model-ready eval rows.

    Only matches eligible for the W/D/L family (target_eligible_wdl) contribute test rows; their
    snapshots already carry target_wdl / rem_goals_* / competition / match_id and the lake source hash.
    No 2026 WC, no label-unsafe (wdl_target_conflict) match, no cross-worktree raw read.
    """
    built = COH.build_cohort(limit=limit, snapshot_minutes=snapshot_minutes)
    eligible = [r for r in built["rows"] if r.get("target_eligible_wdl")]
    rows: List[dict] = []
    for r in eligible:
        for s in r["_snapshots"]:
            # the snapshot already carries: target_wdl, match_id, competition, kickoff_date,
            # rem_goals_home/away, snapshot_minute, goals_diff/score etc., xg_present, lake_sha256.
            srow = dict(s)
            srow.setdefault("goals_diff", (float(s.get("goals_home") or 0) - float(s.get("goals_away") or 0)))
            srow["kickoff_date"] = r.get("kickoff_date")
            srow["lake_sha256"] = r.get("lake_sha256")
            srow["comp_type"] = "international"
            rows.append(srow)
    # hard invariants
    EV.assert_no_2026(rows)
    if not rows:
        raise COH.CohortError("0 eligible eval rows from the lake cohort")
    return {
        "rows": rows,
        "cohort_built": built,
        "n_eligible_matches": len(eligible),
        "n_rows": len(rows),
        "n_competitions": len({x["competition"] for x in rows}),
    }


# =====================================================================================================
# coverage gate (candidate scored on >= COVERAGE_FLOOR of eligible matches)
# =====================================================================================================
def _coverage(loco_result: Dict, model_id: str, n_eligible_matches: int) -> Dict:
    pmr = loco_result.get("per_model_match_rps", {}).get(model_id, {})
    n_scored = len(pmr)
    frac = (n_scored / n_eligible_matches) if n_eligible_matches else 0.0
    return {"n_scored_matches": n_scored, "n_eligible_matches": n_eligible_matches,
            "coverage_fraction": round(frac, 4), "ok": bool(frac >= COVERAGE_FLOOR)}


# =====================================================================================================
# logloss-not-worse + coverage augmentation on top of the locked candidate rule
# =====================================================================================================
def augmented_candidate_verdict(loco_result: Dict, fwd_result: Dict, candidate: str,
                                rows: Sequence[dict], n_eligible_matches: int) -> Dict:
    """Run the LOCKED preregistered rule, then add the spec's extra gates (no-worse-logloss3 +
    coverage >= 60%). A pass on the locked rule that fails an extra gate is demoted to reference_only
    (strength shortfall) or rejected (coverage is a safety/representativeness gate)."""
    base = EV.evaluate_candidate_rule(loco_result, candidate, reference=REFERENCE_MODEL,
                                      rows_for_completeness=rows)
    # --- no-worse-logloss3 vs R0 (pooled LOCO mean) ---
    def _pooled(metric, model):
        vals = [f["models"][model][metric] for f in loco_result["folds"]
                if f["models"].get(model) and f["models"][model].get(metric) is not None]
        return (sum(vals) / len(vals)) if vals else None
    cand_ll = _pooled("logloss", candidate)
    ref_ll = _pooled("logloss", REFERENCE_MODEL)
    ll_ok = (cand_ll is not None and ref_ll is not None and cand_ll <= ref_ll + 1e-9)
    base.setdefault("rules", {})["r8_logloss_not_worse"] = {
        "ok": bool(ll_ok), "candidate_logloss": cand_ll, "reference_logloss": ref_ll}
    # --- coverage >= 60% of eligible matches ---
    cov = _coverage(loco_result, candidate, n_eligible_matches)
    base["rules"]["r9_coverage_adequate"] = cov
    # --- forward-chain consistency (the candidate must also not be worse on the forward-chain pooled RPS) ---
    fwd_pool = fwd_result.get("pooled", {})
    fc_cand = (fwd_pool.get(candidate) or {}).get("rps")
    fc_ref = (fwd_pool.get(REFERENCE_MODEL) or {}).get("rps")
    fc_ok = (fc_cand is not None and fc_ref is not None and fc_cand <= fc_ref)
    base["rules"]["r10_forward_chain_consistent"] = {
        "ok": bool(fc_ok), "candidate_fc_rps": fc_cand, "reference_fc_rps": fc_ref}

    verdict = base["verdict"]
    if verdict == "research_candidate_for_future_shadow_review":
        if not cov["ok"]:
            verdict = "rejected"
            base["reason"] = "coverage below 60% of eligible cohort -> not representative (rejected)"
        elif not ll_ok or not fc_ok:
            verdict = "reference_only"
            base["reason"] = "logloss3/forward-chain not strictly better than R0 -> keep reference"
    base["verdict"] = verdict
    return base


# =====================================================================================================
# ablations (preregistered): reference-vs-xG / event-process / residual; per-tournament removal;
# high-vs-low completeness; xg-only-vs-event-only. All reuse the SAME locked LOCO harness.
# =====================================================================================================
def run_ablations(rows: Sequence[dict], loco_result: Dict) -> Dict:
    import numpy as np

    def pooled_rps(res, model_id):
        vals = [f["models"][model_id]["rps"] for f in res["folds"]
                if f["models"].get(model_id) and f["models"][model_id].get("rps") is not None]
        return float(np.mean(vals)) if vals else None

    ref = pooled_rps(loco_result, REFERENCE_MODEL)
    out: Dict[str, object] = {"reference_e2_rps": ref}

    # reference vs each richer family (e3 xG, e7 full event-process)
    out["reference_vs_xg_e3"] = {"e2": ref, "e3": pooled_rps(loco_result, "research.event_process.e3"),
                                 "delta_e3_minus_e2": (pooled_rps(loco_result, "research.event_process.e3") - ref)
                                 if (ref is not None and pooled_rps(loco_result, "research.event_process.e3") is not None) else None}
    out["reference_vs_event_process_e7"] = {"e2": ref, "e7": pooled_rps(loco_result, "research.event_process.e7"),
                                            "delta_e7_minus_e2": (pooled_rps(loco_result, "research.event_process.e7") - ref)
                                            if (ref is not None and pooled_rps(loco_result, "research.event_process.e7") is not None) else None}
    # xg-only (e3) vs event-only (e4 poss/territory + e5 transition/pressure)
    out["xg_only_vs_event_only"] = {
        "e3_xg": pooled_rps(loco_result, "research.event_process.e3"),
        "e4_poss_terr": pooled_rps(loco_result, "research.event_process.e4"),
        "e5_trans_press": pooled_rps(loco_result, "research.event_process.e5"),
    }
    # per-tournament removal: drop each competition and re-LOCO; report e2 vs e7 pooled RPS each time
    per_tournament = {}
    comps = sorted({r["competition"] for r in rows})
    for held_out in comps:
        sub = [r for r in rows if r["competition"] != held_out]
        if len({r["competition"] for r in sub}) < 2:
            per_tournament[held_out] = {"status": "skipped_lt2_comps"}
            continue
        lr = EV.loco_wdl(sub)
        per_tournament[held_out] = {"e2": pooled_rps(lr, REFERENCE_MODEL),
                                    "e7": pooled_rps(lr, "research.event_process.e7")}
    out["per_tournament_removal"] = per_tournament
    # high vs low completeness: split eligible matches by xg_present fraction at the match level
    by_match_complete: Dict[str, float] = {}
    for r in rows:
        m = r["match_id"]
        xgp = 1.0 if str(r.get("xg_present")) in ("1", "1.0", "True", "true") else 0.0
        by_match_complete.setdefault(m, [])
    # recompute per-match xg-present fraction
    frac_map: Dict[str, List[float]] = {}
    for r in rows:
        xgp = 1.0 if str(r.get("xg_present")) in ("1", "1.0", "True", "true") else 0.0
        frac_map.setdefault(r["match_id"], []).append(xgp)
    match_frac = {m: (sum(v) / len(v)) if v else 0.0 for m, v in frac_map.items()}
    med = sorted(match_frac.values())[len(match_frac) // 2] if match_frac else 0.0
    hi = [r for r in rows if match_frac.get(r["match_id"], 0.0) >= med]
    lo = [r for r in rows if match_frac.get(r["match_id"], 0.0) < med]
    out["high_vs_low_completeness"] = {
        "median_match_xg_fraction": round(med, 4),
        "high_n_rows": len(hi), "low_n_rows": len(lo),
        "high_e2_rps": pooled_rps(EV.loco_wdl(hi), REFERENCE_MODEL) if len({r["competition"] for r in hi}) >= 2 else None,
        "high_e7_rps": pooled_rps(EV.loco_wdl(hi), "research.event_process.e7") if len({r["competition"] for r in hi}) >= 2 else None,
    }
    return out


# =====================================================================================================
# main rerun
# =====================================================================================================
def run(limit: Optional[int] = None, n_bootstrap: int = 1000,
        snapshot_minutes: Optional[list[float]] = None, fast: bool = False) -> Dict:
    loaded = load_cohort_eval_rows(limit=limit, snapshot_minutes=snapshot_minutes)
    rows = loaded["rows"]
    n_eligible = loaded["n_eligible_matches"]

    # forward-chain + LOCO over the canonical e0..e9 family (e2 == R0 reference). No club aux rows in the
    # lake yet -> e8 honestly degrades to e7's column set (with/without-club-transfer comparison).
    fwd = EV.forward_chain_wdl(rows)
    loco = EV.loco_wdl(rows)

    # per-model pooled LOCO metrics
    import numpy as np

    def pooled(metric, model_id, res=loco):
        vals = [f["models"][model_id][metric] for f in res["folds"]
                if f["models"].get(model_id) and f["models"][model_id].get(metric) is not None]
        return float(np.mean(vals)) if vals else None

    metrics = {}
    for mid in REG.EVENT_PROCESS_MODELS:
        metrics[mid] = {
            "loco_rps": pooled("rps", mid),
            "loco_logloss": pooled("logloss", mid),
            "loco_brier_draw": pooled("brier_draw", mid),
            "forward_chain_rps": (fwd.get("pooled", {}).get(mid) or {}).get("rps"),
        }
    calibration = loco.get("reliability", {})

    # paired match-level bootstrap (every e3..e9 candidate vs the e2/R0 reference)
    pmr = loco.get("per_model_match_rps", {})
    bootstrap = {}
    for mid in REG.EVENT_PROCESS_MODELS:
        if mid == REFERENCE_MODEL:
            continue
        bootstrap[mid] = EV.paired_bootstrap_delta(pmr, mid, REFERENCE_MODEL, n=n_bootstrap)

    # candidate verdicts (locked rule + spec's extra logloss/coverage/forward-chain gates)
    verdicts = {}
    for mid in REG.EVENT_PROCESS_MODELS:
        if mid == REFERENCE_MODEL:
            verdicts[mid] = {"candidate": mid, "verdict": "reference_only",
                             "reason": "this IS the R0 remaining-time Poisson reference"}
            continue
        verdicts[mid] = augmented_candidate_verdict(loco, fwd, mid, rows, n_eligible)

    ablations = {} if fast else run_ablations(rows, loco)

    # reproducibility audit: lake-hash-backed inputs + determinism markers
    sha_sample = sorted({r.get("lake_sha256") for r in rows if r.get("lake_sha256")})
    audit = {
        "rerun_version": RERUN_VERSION,
        "labels": LABELS,
        "reference_model_R0": REFERENCE_MODEL,
        "n_eligible_matches": n_eligible,
        "n_eval_rows": loaded["n_rows"],
        "n_competitions": loaded["n_competitions"],
        "all_inputs_lake_hash_backed": bool(sha_sample) and all(
            isinstance(s, str) and len(s) == 64 for s in sha_sample),
        "n_distinct_lake_source_hashes": len(sha_sample),
        "bootstrap_unit": "match",
        "n_bootstrap": n_bootstrap,
        "deterministic": True,
        "no_2026_world_cup": True,
        "model_families": REG.EVENT_PROCESS_MODELS,
    }

    return {
        "loaded": loaded, "forward_chain": fwd, "loco": loco,
        "metrics": metrics, "calibration": calibration, "bootstrap": bootstrap,
        "verdicts": verdicts, "ablations": ablations, "audit": audit,
    }


def write_outputs(res: Dict) -> Dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = res["metrics"]
    verdicts = res["verdicts"]
    audit = res["audit"]

    # decision ledger CSV
    ledger_rows = []
    for mid in REG.EVENT_PROCESS_MODELS:
        v = verdicts[mid]
        rules = v.get("rules", {})
        ledger_rows.append({
            "model_id": mid,
            "is_reference": mid == REFERENCE_MODEL,
            "loco_rps": metrics[mid]["loco_rps"],
            "loco_logloss": metrics[mid]["loco_logloss"],
            "loco_brier_draw": metrics[mid]["loco_brier_draw"],
            "forward_chain_rps": metrics[mid]["forward_chain_rps"],
            "rps_delta_vs_R0": (metrics[mid]["loco_rps"] - metrics[REFERENCE_MODEL]["loco_rps"])
            if (metrics[mid]["loco_rps"] is not None and metrics[REFERENCE_MODEL]["loco_rps"] is not None) else None,
            "bootstrap_favors": (res["bootstrap"].get(mid, {}) or {}).get("favors_candidate"),
            "coverage_fraction": (rules.get("r9_coverage_adequate", {}) or {}).get("coverage_fraction"),
            "verdict": v["verdict"],
            "reason": v.get("reason", ""),
        })
    import csv as _csv
    fields = list(ledger_rows[0].keys())
    with LEDGER_CSV.open("w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in ledger_rows:
            w.writerow(r)

    LEDGER_JSON.write_text(json.dumps({
        "schema_version": RERUN_VERSION, "labels": LABELS,
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "reference_model_R0": REFERENCE_MODEL,
        "verdict_counts": dict(Counter(v["verdict"] for v in verdicts.values())),
        "ledger": ledger_rows, "verdicts": verdicts,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    METRICS_JSON.write_text(json.dumps({
        "schema_version": RERUN_VERSION, "labels": LABELS,
        "reference_model_R0": REFERENCE_MODEL,
        "metrics": metrics, "forward_chain_pooled": res["forward_chain"].get("pooled", {}),
        "competition_order": res["forward_chain"].get("competition_order", []),
        "ablations": res["ablations"],
        "n_eligible_matches": audit["n_eligible_matches"], "n_eval_rows": audit["n_eval_rows"],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    CALIB_JSON.write_text(json.dumps({
        "schema_version": RERUN_VERSION, "labels": LABELS,
        "reference_model_R0": REFERENCE_MODEL,
        "draw_channel_reliability": res["calibration"],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    BOOT_JSON.write_text(json.dumps({
        "schema_version": RERUN_VERSION, "labels": LABELS, "bootstrap_unit": "match",
        "reference_model_R0": REFERENCE_MODEL, "n_bootstrap": audit["n_bootstrap"],
        "paired_delta_vs_R0": res["bootstrap"],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    AUDIT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ledger_rows": ledger_rows, "verdict_counts": dict(Counter(v["verdict"] for v in verdicts.values()))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="cap cohort matches (debug)")
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--fast", action="store_true", help="skip the per-tournament ablations (quicker)")
    ap.add_argument("--self-test", action="store_true",
                    help="2-fold R0 rerun on the current lake -> finite RPS, then exit")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    res = run(limit=args.limit, n_bootstrap=args.bootstrap, fast=args.fast)
    out = write_outputs(res)
    a = res["audit"]
    print(json.dumps({
        "status": "ok",
        "n_eligible_matches": a["n_eligible_matches"],
        "n_eval_rows": a["n_eval_rows"],
        "reference_R0_rps": res["metrics"][REFERENCE_MODEL]["loco_rps"],
        "verdict_counts": out["verdict_counts"],
        "all_inputs_lake_hash_backed": a["all_inputs_lake_hash_backed"],
        "ledger_csv": str(LEDGER_CSV),
    }))


# =====================================================================================================
# self-test: a 2-fold R0 rerun on the CURRENT lake -> finite RPS
# =====================================================================================================
def _self_test():
    """Restrict to the two earliest tournaments so LOCO has exactly 2 folds; score R0 (e2) -> finite RPS."""
    loaded = load_cohort_eval_rows()
    rows = loaded["rows"]
    comps = EV._comp_order(rows)
    keep = set(comps[:2])
    rows2 = [r for r in rows if r["competition"] in keep]
    loco = EV.loco_wdl(rows2)
    import numpy as np
    vals = [f["models"][REFERENCE_MODEL]["rps"] for f in loco["folds"]
            if f["models"].get(REFERENCE_MODEL) and f["models"][REFERENCE_MODEL].get("rps") is not None]
    r0 = float(np.mean(vals)) if vals else None
    ok = (r0 is not None) and math.isfinite(r0) and len(loco["folds"]) >= 2
    print(json.dumps({"self_test": "pass" if ok else "fail",
                      "n_folds": len(loco["folds"]), "competitions": sorted(keep),
                      "R0_e2_loco_rps": r0, "n_rows": len(rows2)}))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
