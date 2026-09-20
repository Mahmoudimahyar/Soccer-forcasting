"""RG_JOB09 -- selective-gate coverage / fallback audit for residual.selective_correction_r4.

The selective correction blends an event-process correction onto the W2 reference by a per-row alpha that
is chosen IN-TRAIN (honest CV) and ALWAYS permits alpha=0 (pure W2 fallback). This job audits, under
LOCO, the gate's behaviour OUT-OF-SAMPLE:

  * the in-train gate parameters (t_low, t_full, alpha_low, alpha_full) and whether the gate degenerated
    to pure fallback (alpha=0 everywhere) -- the honest "no correction earned" outcome;
  * correction COVERAGE on the held-out fold: fraction of test rows landing in each decision band
    (fallback_to_w2 / apply_low_weight_correction / apply_full_correction);
  * CORRECTED-vs-FALLBACK performance: pooled RPS over rows the gate corrected (alpha>0) vs rows it left
    on pure W2, and the corrected rows' RPS under r4 vs the same rows under pure r0 (did correcting help
    where it fired?).

research_only / experimental. No network/API. Honest data_insufficient if the panel is absent.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rg

WDL = ["H", "D", "A"]


def main():
    try:
        bundle = _rg.load_rows()
    except Exception as e:
        from wcdrawlab.research.residual_intensity import datasets as DS
        if isinstance(e, DS.DataInsufficient):
            _rg.emit("data_insufficient", reason=f"panel unavailable: {e}")
            return
        _rg.emit("failed", reason=f"load error: {e!r}")
        return

    import wcdrawlab.research.residual_intensity as RI
    from wcdrawlab.research.residual_intensity import datasets as DS

    rows = list(bundle["rows"])

    fold_audits = []
    bands_total = {"fallback_to_w2": 0, "apply_low_weight_correction": 0, "apply_full_correction": 0}
    corrected_r4 = corrected_r0 = 0.0
    fallback_n = corrected_n = 0
    fallback_rps = 0.0
    n_folds = 0
    degenerate_folds = 0
    for held, train, test in DS.loco_folds(rows):
        n_folds += 1
        sc = RI.build_selective_correction_r4(train)
        gate = sc.gate
        diag = sc.diagnostics()
        if diag.get("degenerate_fallback"):
            degenerate_folds += 1
        bands = {"fallback_to_w2": 0, "apply_low_weight_correction": 0, "apply_full_correction": 0}
        f_rps = 0.0
        f_n = 0
        c_r4 = c_r0 = 0.0
        c_n = 0
        for r in test:
            y = r.get("target_wdl")
            if y not in WDL:
                continue
            dec = gate.decision(r) if gate is not None else "fallback_to_w2"
            bands[dec] = bands.get(dec, 0) + 1
            alpha = gate.alpha_for(r) if gate is not None else 0.0
            p_r4 = sc.predict_one(r)
            p_r0 = RI.w2_reference_r0(r)
            if alpha > 0:
                c_r4 += _rg.rps_wdl(p_r4, y); c_r0 += _rg.rps_wdl(p_r0, y); c_n += 1
            else:
                f_rps += _rg.rps_wdl(p_r4, y); f_n += 1
        for k in bands_total:
            bands_total[k] += bands.get(k, 0)
        corrected_r4 += c_r4; corrected_r0 += c_r0; corrected_n += c_n
        fallback_rps += f_rps; fallback_n += f_n
        fold_audits.append({
            "competition": held, "gate_params": {k: diag.get(k) for k in
                ("t_low", "t_full", "alpha_low", "alpha_full", "degenerate_fallback",
                 "correction_coverage_train")},
            "test_decision_bands": bands,
            "corrected_rows": c_n, "fallback_rows": f_n,
            "corrected_rps_r4": round(c_r4 / c_n, 5) if c_n else None,
            "corrected_rps_r0_same_rows": round(c_r0 / c_n, 5) if c_n else None,
        })

    n_scored = sum(bands_total.values())
    summary = {
        "n_folds": n_folds, "degenerate_fallback_folds": degenerate_folds,
        "alpha0_fallback_reachable": True,
        "oos_decision_band_fractions": {k: (round(v / n_scored, 4) if n_scored else 0.0)
                                        for k, v in bands_total.items()},
        "oos_correction_coverage": round(corrected_n / n_scored, 4) if n_scored else 0.0,
        "corrected_rows_total": corrected_n, "fallback_rows_total": fallback_n,
        "corrected_rps_r4": round(corrected_r4 / corrected_n, 5) if corrected_n else None,
        "corrected_rps_r0_same_rows": round(corrected_r0 / corrected_n, 5) if corrected_n else None,
        "correction_helped_where_fired": (corrected_n > 0 and (corrected_r4 / corrected_n) <
                                          (corrected_r0 / corrected_n)) if corrected_n else None,
        "fallback_rps_r4_equals_r0": round(fallback_rps / fallback_n, 5) if fallback_n else None,
    }
    _rg.write_json("rg_selective_gate_audit.json", {
        "model": "research.residual.selective_correction_r4",
        "summary": summary, "folds": fold_audits,
        "n_rows": len(rows), "n_matches": bundle["n_matches"],
        "utc": _rg.utc(), "labels": _rg.LABELS,
    })
    _rg.emit("complete",
             reason=f"selective-gate audit: folds={n_folds}, degenerate_fallback={degenerate_folds}/{n_folds}, "
                    f"oos_correction_coverage={summary['oos_correction_coverage']}, "
                    f"correction_helped_where_fired={summary['correction_helped_where_fired']} "
                    f"(alpha=0 fallback always reachable)",
             state_updates={"gate_degenerate_folds": degenerate_folds, "gate_n_folds": n_folds,
                            "gate_oos_coverage": summary["oos_correction_coverage"]})


main()
