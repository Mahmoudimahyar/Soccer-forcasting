"""JOB14 -- FINAL DECISION LEDGER. research_only / paper-only (never auto-promotes anything).

Applies the 8 preregistered promotion rules (dynamic_eval.evaluate_candidate_rule) to each candidate vs its
reference, on the leakage-safe pre-2026 international LOCO folds + forward-chain folds, and records a verdict
per candidate:

    reference_only | rejected | data_insufficient | research_candidate_for_future_shadow_review

Candidates evaluated (canonical IDs):
  full-corpus W/D/L : p1,p2,p3,p4,p5 vs r2 ; r1 vs r0
  xG subset W/D/L   : x1,x2,x3 vs r2  (rule 7 xG-integrity enforced; xg_subset_nonzero attached)

NO 2026 result is ever used. A passing candidate is labelled research_candidate_for_future_shadow_review
ONLY -- it is paper-only and is NEVER promoted into the runtime/B1/approved models by this job. The decision
ledger is the artifact; promotion is a separate human-gated step outside this research plane.

complete when the LOCO artifact is available and verdicts are produced for all candidates.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _mj_common as M  # noqa: E402
sys.path.insert(0, str(M.RJ))
import _job  # noqa: E402
sys.path.insert(0, str(M.SRC))
import _common as C  # noqa: E402
from wcdrawlab.research import dynamic_eval as DE, dynamic_models as DM  # noqa: E402


def _full_loco(rows, factory, xg_subset=False, n_xg_matches=None, xg_nonzero=None):
    """Re-run a LOCO with full per-fold model dicts retained for the rule evaluator."""
    loco = DE.loco_wdl(rows, factory)
    if xg_subset:
        loco["xg_subset_nonzero"] = bool(xg_nonzero)
        loco["n_xg_matches"] = n_xg_matches
    return loco


def main():
    rd = _job.run_dir()
    try:
        wdl = M.load_wdl_rows()
    except M.DataInsufficient as e:
        M.write_artifact(rd, "mj_job14_decision_ledger.json",
                         M.job_envelope("JOB14", "data_insufficient", reason=str(e), start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason=str(e))
        return

    wdl_loco = _full_loco(wdl, DM.wdl_predictors)
    wdl_fwd = DE.forward_chain_wdl(wdl, DM.wdl_predictors)

    verdicts = {}
    # ONLY genuine in-play candidates are evaluated for promotion, ALL against the in-play reference r2.
    # R0/R1/R2 are reference-tier baselines (handled below as reference_only) — never candidates. Evaluating
    # r1 against the trivial static anchor r0 would falsely flag the baseline as a "candidate" (fixed 2026-06-27).
    full_pairs = [
        ("research.wdl.player_team_state_p5", "research.wdl.remaining_time_poisson_r2"),
        ("research.wdl.player_composition_p4", "research.wdl.remaining_time_poisson_r2"),
        ("research.wdl.player_substitution_delta_p3", "research.wdl.remaining_time_poisson_r2"),
        ("research.wdl.player_on_pitch_p2", "research.wdl.remaining_time_poisson_r2"),
        ("research.wdl.player_starting_xi_p1", "research.wdl.remaining_time_poisson_r2"),
    ]
    for cand, ref in full_pairs:
        verdicts[cand] = DE.evaluate_candidate_rule(wdl_loco, wdl_fwd, cand, ref)

    # xG subset candidates
    xg_block = {}
    try:
        xrows = M.load_xg_rows()
        n_xg_matches = len(set(r["match_id"] for r in xrows))
        xg_nonzero = any(abs(r.get("cum_xg_diff", 0.0)) > 0 for r in xrows)
        xg_loco = _full_loco(xrows, DM.xg_wdl_predictors, xg_subset=True,
                             n_xg_matches=n_xg_matches, xg_nonzero=xg_nonzero)
        xg_fwd = DE.forward_chain_wdl(xrows, DM.xg_wdl_predictors)
        for cand in ("research.wdl.xg_calibrated_hybrid_x3", "research.wdl.xg_player_state_x2",
                     "research.wdl.xg_event_state_x1"):
            xg_block[cand] = DE.evaluate_candidate_rule(
                xg_loco, xg_fwd, cand, "research.wdl.remaining_time_poisson_r2",
                xg_subset=True, min_matches=30)
    except M.DataInsufficient as e:
        xg_block["note"] = str(e)
    verdicts.update({k: v for k, v in xg_block.items() if isinstance(v, dict) and "verdict" in v})

    # R0/R1/R2 are reference-tier baselines, never promotable candidates -> reference_only.
    for ref_model in ("research.wdl.static_b1_anchor_r0", "research.wdl.time_score_baseline_r1",
                      "research.wdl.remaining_time_poisson_r2"):
        verdicts[ref_model] = {"reference": "n/a (reference baseline)", "verdict": "reference_only",
                               "reason": "reference-tier baseline; not evaluated for promotion", "rules": {}}

    # --- canonical Phase-8 decision ledger with REAL pooled metrics (data/reference/) ---
    def _pool(fwd, model):
        vals = [f["models"][model] for f in fwd.get("folds", []) if model in f.get("models", {})]
        if not vals:
            return {}
        n = len(vals)
        return {"rps": round(sum(v["rps"] for v in vals) / n, 6),
                "logloss": round(sum(v["logloss"] for v in vals) / n, 6),
                "brier_draw": round(sum(v["brier_draw"] for v in vals) / n, 6), "n_folds": n}
    canon = []
    for mid, v in verdicts.items():
        pooled = _pool(wdl_fwd, mid) or (_pool(xg_fwd, mid) if "xg_fwd" in dir() else {})
        canon.append({"model_id": mid, "dataset_version": "dynamic_state_v1",
                      "source_manifest_version": "api_football_result_v1",
                      "rps": pooled.get("rps"), "logloss": pooled.get("logloss"),
                      "brier_draw": pooled.get("brier_draw"), "n_folds": pooled.get("n_folds"),
                      "reference": v["reference"], "final_status": v["verdict"], "reason": v["reason"],
                      "promotion": "paper-only; never auto-promoted to runtime/B1/approved_models"})
    import csv as _csv
    ref_dir = M.ROOT / "data/reference"; ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "model_decision_ledger.json").write_text(__import__("json").dumps(canon, indent=2), encoding="utf-8")
    with (ref_dir / "model_decision_ledger.csv").open("w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=list(canon[0].keys())); w.writeheader(); w.writerows(canon)

    # compact ledger (verdict + reason + headline rules) + the canonical anchor note
    ledger = {cand: {"reference": v["reference"], "verdict": v["verdict"], "reason": v["reason"],
                     "rule1": v["rules"].get("rule1_improves_reference"),
                     "rule3_bootstrap": v["rules"].get("rule3_bootstrap_favors_candidate"),
                     "rule4_calibration": v["rules"].get("rule4_calibration_not_degraded")}
              for cand, v in verdicts.items()}

    env = M.job_envelope("JOB14", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         anchor="research.wdl.static_b1_anchor_r0 is the B1-equivalent static anchor; "
                                "r2 remaining-time Poisson is the in-play reference",
                         promotion_policy="paper-only; passing => research_candidate_for_future_shadow_review; "
                                          "NEVER auto-promoted to runtime/B1/approved models",
                         verdicts=verdicts, ledger=ledger)
    M.write_artifact(rd, "mj_job14_decision_ledger.json", env)
    M.write_artifact(rd, "candidate_verdicts.json",
                     {"run_id": M.RUN_ID, "model_version": M.MODEL_VERSION,
                      "verdicts": {k: v["verdict"] for k, v in verdicts.items()},
                      "ledger": ledger, "paper_only": True})
    counts = {}
    for v in verdicts.values():
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    _job.emit("complete",
              reason=f"decision ledger: {counts} (paper-only; no auto-promotion)",
              state_updates={"verdict_counts": counts,
                             "candidate_verdicts": {k: v["verdict"] for k, v in verdicts.items()}})


if __name__ == "__main__":
    main()
